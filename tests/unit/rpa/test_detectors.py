"""
tests/unit/rpa/test_detectors.py — Unit tests for Vision/Detectors.py.

All tests use literal Scene/SceneNode/Seam/Surface objects — no cv2, no
Qt, no display required.  Every spec-required test name is present here,
with the eight Phase-7 detectors registered as strict xfail stubs so a
secretly-passing stub becomes a hard failure.

:spec: docs/features/rpa-design-vision/feature_steps.md §4
"""

import pytest

pytestmark = pytest.mark.unit

from Code.Rpa.Types import Rect
from Code.Rpa.Vision.Scene import (
    BASIS_FILL,
    BASIS_INK,
    BASIS_PERCEIVED,
    BASIS_WIDGET,
    Corner,
    Fill,
    Finding,
    Gap,
    Hypothesis,
    Ink,
    PeerCluster,
    Scene,
    SceneNode,
    Seam,
    Surface,
)
from Code.Rpa.Vision.Detectors import (
    DETECTORS,
    invisible_fill,
    orphan_style_rule,
    peer_adjacency,
    run_all,
    spacing_uniformity,
    surface_broken,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _node(
    node_id: str,
    x: int = 0,
    y: int = 0,
    w: int = 40,
    h: int = 25,
    fill: Fill | None = None,
    ink: Ink | None = None,
    corners: tuple[Corner, ...] = (),
    measured: frozenset | None = None,
    cls: str = "",
    style_rules: tuple[dict, ...] = (),
) -> SceneNode:
    """Build a minimal test SceneNode."""
    if measured is None:
        m: frozenset = frozenset()
        if fill is not None:
            m = m | frozenset(["fill"])
        if ink is not None:
            m = m | frozenset(["ink"])
        if corners:
            m = m | frozenset(["corners"])
        measured = m
    return SceneNode(
        node_id=node_id,
        rect=Rect(x, y, w, h),
        fill=fill,
        ink=ink,
        corners=corners,
        measured=measured,
        cls=cls,
        style_rules=style_rules,
    )


def _flat_fill(hex_color: str, bg: str, visible: bool, delta: int = 0) -> Fill:
    return Fill(
        rect=Rect(0, 0, 40, 25),
        kind="flat",
        hex_color=hex_color,
        visible=visible,
        visible_delta=delta,
        background_hex=bg,
    )


def _gradient_fill(
    hex_start: str,
    hex_end: str,
    bg: str,
    visible: bool,
    delta: int,
) -> Fill:
    return Fill(
        rect=Rect(0, 0, 40, 25),
        kind="gradient_v",
        hex_start=hex_start,
        hex_end=hex_end,
        visible=visible,
        visible_delta=delta,
        background_hex=bg,
    )


def _scene(*nodes: SceneNode, seams=(), surfaces=(), clusters=()) -> Scene:
    """Build a scene from positional nodes (first becomes root's child list)."""
    if not nodes:
        return Scene()
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 1280, 860),
        children=tuple(nodes),
        measured=frozenset(),
    )
    return Scene(
        scene_id="test",
        region=Rect(0, 0, 1280, 860),
        root=root,
        seams=tuple(seams),
        surfaces=tuple(surfaces),
        clusters=tuple(clusters),
    )


# ---------------------------------------------------------------------------
# invisible_fill
# ---------------------------------------------------------------------------

def test_invisible_fill_fires_on_flat_palette_window():
    """invisible_fill fires when a flat fill colour matches its local background."""
    # Flat fill #252526 on background #252526 — invisible
    node = _node(
        "tab_board",
        fill=_flat_fill("#252526", "#252526", visible=False, delta=0),
        measured=frozenset(["fill"]),
    )
    scene = _scene(node)
    findings = invisible_fill(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "invisible_fill"
    assert f.verdict == "violated"
    assert "tab_board" in f.node_ids
    assert f.measurements["fill_kind"] == "flat"
    assert f.measurements["visible_delta"] == "0"


def test_invisible_fill_fires_on_gradient_straddling_background():
    """invisible_fill fires on a gradient whose midpoint straddles its background.

    The pane caption gradient #252526→#363636 on background #2d2d2d: the midpoint
    is ~#2d2d2d (invisible) even though the endpoints differ slightly.  The MAX
    delta rule produces visible_delta ≤ 9.
    """
    # Caption gradient that straddles the background
    node = _node(
        "caption_players",
        fill=_gradient_fill(
            "#252526", "#363636", bg="#2d2d2d", visible=False, delta=9
        ),
        measured=frozenset(["fill"]),
    )
    scene = _scene(node)
    findings = invisible_fill(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "invisible_fill"
    assert f.verdict == "violated"
    assert f.measurements["fill_kind"] == "gradient_v"
    # Hypothesis mentions gradient straddling
    assert any("straddle" in h.mechanism for h in f.hypotheses)


def test_invisible_fill_mean_rule_would_pass_gradient():
    """Companion: if we tested only the mean colour, the gradient caption would pass.

    The mean of #252526 and #363636 is approximately #2e2e2e, which is visually
    indistinguishable from the #2d2d2d background (delta ≈ 1).  The max rule fires;
    the mean rule would not.  This test pins the max-vs-mean decision.
    """
    from Code.Rpa.Vision.Measure import fill_is_visible
    import math

    hex_start = "#252526"
    hex_end = "#363636"
    bg = "#2d2d2d"

    def _rgb(h: str):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _mean_hex(a: str, b: str) -> str:
        r1, g1, b1 = _rgb(a)
        r2, g2, b2 = _rgb(b)
        return f"#{(r1+r2)//2:02x}{(g1+g2)//2:02x}{(b1+b2)//2:02x}"

    mean = _mean_hex(hex_start, hex_end)

    # Mean rule would pass (delta < 12)
    mean_visible = fill_is_visible(mean, bg, delta=12)
    assert not mean_visible, f"Mean {mean} on {bg} should be invisible; mean rule would pass"

    # Max endpoint rule fires: at least one endpoint has delta ≥ 12
    end_visible = fill_is_visible(hex_end, bg, delta=12)
    assert end_visible, f"Endpoint {hex_end} on {bg} should be visible"


def test_invisible_fill_does_not_fire_on_visible_fill():
    """invisible_fill stays silent when a fill is clearly visible."""
    node = _node(
        "tab_file",
        fill=_flat_fill("#007acc", "#252526", visible=True, delta=110),
        measured=frozenset(["fill"]),
    )
    scene = _scene(node)
    findings = invisible_fill(scene, {})
    assert findings == []


def test_invisible_fill_does_not_fire_when_fill_not_measured():
    """invisible_fill stays silent when fill measurement was not attempted."""
    node = _node("tab_x", fill=None, measured=frozenset())
    scene = _scene(node)
    assert invisible_fill(scene, {}) == []


# ---------------------------------------------------------------------------
# spacing_uniformity
# ---------------------------------------------------------------------------

def _make_notation_tab_cluster() -> tuple[list[SceneNode], PeerCluster]:
    """5 notation tabs, 2 px apart, uniform widget gaps, invisible fills."""
    tab_w = 80
    tab_h = 30
    gap = 2
    nodes = []
    for i in range(5):
        x = i * (tab_w + gap)
        ink_x = x + 10
        nodes.append(_node(
            f"ntab{i}",
            x=x, y=0, w=tab_w, h=tab_h,
            fill=Fill(
                rect=Rect(x, 0, tab_w, tab_h),
                kind="flat",
                hex_color="#252526",
                visible=False,
                visible_delta=0,
                background_hex="#252526",
            ),
            ink=Ink(rect=Rect(ink_x, 5, 60, 20)),
            measured=frozenset(["fill", "ink"]),
        ))
    cluster = PeerCluster(
        cluster_id="notation_tab",
        signature=("tab", "tabbar", 0, 30, "#252"),
        members=tuple(n.node_id for n in nodes),
        parents=tuple("tabbar" for _ in nodes),
    )
    return nodes, cluster


def test_spacing_uniformity_passes_notation_tabs():
    """spacing_uniformity reports 'uniform' for the 5-tab notation strip.

    Widget gaps are 2,2,2,2 — perfectly uniform.  Fills are invisible, so
    perceived gaps fall through to ink-to-ink, which is also uniform.
    The wrongness here is not unevenness but that the gaps SHOW ancestor
    background — that is what peer_adjacency catches, not spacing_uniformity.
    """
    nodes, cluster = _make_notation_tab_cluster()
    scene = _scene(*nodes, clusters=[cluster])
    findings = spacing_uniformity(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "spacing_uniformity"
    assert f.verdict == "uniform", (
        f"Expected uniform; got {f.verdict!r}. per_basis={f.per_basis}"
    )


def _make_ribbon_tab_cluster() -> tuple[list[SceneNode], PeerCluster]:
    """6 ribbon tabs: File + Home have visible fills; Board..View do not.

    Layout produces widget gaps all 0, perceived gaps non-uniform (≈2:1 spread).
    """
    # Tab rects (widget, no gaps)
    widths = [46, 60, 58, 72, 64, 52]
    labels = ["file", "home", "board", "analysis", "engine", "view"]
    ink_offsets = [13, 12, 12, 10, 12, 12]  # ink leading offset within tab
    ink_widths  = [19, 33, 33, 46, 37, 28]  # ink widths

    nodes = []
    x = 0
    for i, (w, lbl, ink_off, ink_w) in enumerate(zip(widths, labels, ink_offsets, ink_widths)):
        if i == 0:  # File — visible blue fill
            fill = Fill(
                rect=Rect(x, 0, w, 25),
                kind="flat",
                hex_color="#007acc",
                visible=True,
                visible_delta=110,
                background_hex="#252526",
            )
        elif i == 1:  # Home — visible white fill
            fill = Fill(
                rect=Rect(x, 0, w, 25),
                kind="flat",
                hex_color="#ffffff",
                visible=True,
                visible_delta=200,
                background_hex="#252526",
            )
        else:  # Board..View — invisible palette.window()
            fill = Fill(
                rect=Rect(x, 0, w, 25),
                kind="flat",
                hex_color="#252526",
                visible=False,
                visible_delta=0,
                background_hex="#252526",
            )
        nodes.append(_node(
            f"rtab_{lbl}",
            x=x, y=0, w=w, h=25,
            fill=fill,
            ink=Ink(rect=Rect(x + ink_off, 5, ink_w, 15)),
            measured=frozenset(["fill", "ink"]),
        ))
        x += w

    cluster = PeerCluster(
        cluster_id="ribbon_tab",
        signature=("tab", "tabbar", 0, 24, "#007"),
        members=tuple(n.node_id for n in nodes),
        parents=tuple("tabbar" for _ in nodes),
    )
    return nodes, cluster


def test_spacing_uniformity_fails_ribbon_perceived():
    """spacing_uniformity fires on the 6-tab ribbon with non-uniform perceived gaps.

    Widget gaps are all 0 (tabs abut); only File and Home have visible fills.
    Their neighbours read ~13 px from the fill edge while transparent-fill
    tabs read ink-to-ink (~24 px) — roughly a 2× spread.
    """
    nodes, cluster = _make_ribbon_tab_cluster()
    scene = _scene(*nodes, clusters=[cluster])
    findings = spacing_uniformity(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "spacing_uniformity"
    assert f.verdict == "non_uniform", (
        f"Expected non_uniform; got {f.verdict!r}. per_basis={f.per_basis}"
    )
    assert f.per_basis.get(BASIS_PERCEIVED) == "non_uniform"
    assert f.per_basis.get(BASIS_WIDGET) == "uniform"


# ---------------------------------------------------------------------------
# peer_adjacency
# ---------------------------------------------------------------------------

def _make_ancestor_seam_scene() -> Scene:
    """5 notation tabs with 2px ancestor-colour seams between them."""
    nodes, cluster = _make_notation_tab_cluster()
    seams = []
    nids = [n.node_id for n in nodes]
    for i in range(len(nids) - 1):
        seams.append(Seam(
            before_id=nids[i],
            after_id=nids[i + 1],
            axis="x",
            px=2,
            shows_hex="#1e1e1e",
            shows_owner="ancestor",
            closed=True,
            border_hex="#363636",
        ))
    return _scene(*nodes, seams=seams, clusters=[cluster])


def _make_parent_seam_scene() -> Scene:
    """Same tabs but seams show parent colour — a designed margin, not a hole."""
    nodes, cluster = _make_notation_tab_cluster()
    seams = []
    nids = [n.node_id for n in nodes]
    for i in range(len(nids) - 1):
        seams.append(Seam(
            before_id=nids[i],
            after_id=nids[i + 1],
            axis="x",
            px=2,
            shows_hex="#252526",
            shows_owner="parent",
            closed=False,
            border_hex="",
        ))
    return _scene(*nodes, seams=seams, clusters=[cluster])


def test_peer_adjacency_fires_on_ancestor_seam():
    """peer_adjacency fires when seams show ancestor background colour."""
    scene = _make_ancestor_seam_scene()
    findings = peer_adjacency(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "peer_adjacency"
    assert f.verdict == "violated"
    assert f.measurements["shows_owner"] == "ancestor"
    assert "#1e1e1e" in f.measurements["shows_hex"]


def test_peer_adjacency_silent_on_parent_seam():
    """peer_adjacency stays silent when seams show the immediate parent colour.

    A 2 px gap in the parent's own colour is a designed margin, not a defect.
    """
    scene = _make_parent_seam_scene()
    findings = peer_adjacency(scene, {})
    assert findings == []


def test_peer_adjacency_spacing_uniformity_silent_same_scene():
    """Paired regression guard: the ancestor-seam scene makes spacing_uniformity
    pass while peer_adjacency fires.

    This pins the wrong-predicate lesson: uniformity cannot express
    "should be zero", and peer_adjacency catches what uniformity passes.
    """
    scene = _make_ancestor_seam_scene()

    su_findings = spacing_uniformity(scene, {})
    pa_findings = peer_adjacency(scene, {})

    # spacing_uniformity must report uniform (NOT non_uniform)
    assert su_findings, "spacing_uniformity should emit a finding (uniform)"
    assert su_findings[0].verdict == "uniform", (
        f"spacing_uniformity verdict should be 'uniform'; "
        f"got {su_findings[0].verdict!r}"
    )

    # peer_adjacency must fire
    assert len(pa_findings) == 1
    assert pa_findings[0].verdict == "violated"


def test_peer_adjacency_silent_when_no_seams():
    """peer_adjacency returns empty when the scene has no pre-computed seams."""
    nodes, cluster = _make_notation_tab_cluster()
    scene = _scene(*nodes, clusters=[cluster])  # no seams
    assert peer_adjacency(scene, {}) == []


# ---------------------------------------------------------------------------
# surface_broken
# ---------------------------------------------------------------------------

def _make_broken_surface_scene() -> Scene:
    """Tab-page surface with 4 breaks: 2 corners + seam_closed + fill_mismatch."""
    # Tab node — selected; its top corners are intentional rounding (shows parent),
    # so they do NOT constitute a break.  The tab's bottom edge is the problem seam.
    tab = SceneNode(
        node_id="tab0",
        rect=Rect(717, 485, 79, 31),
        fill=Fill(
            rect=Rect(717, 485, 79, 31),
            kind="flat",
            hex_color="#272728",
            visible=True,
            visible_delta=5,
            background_hex="#252526",
        ),
        corners=(
            Corner(which="tl", radius_px=4, shows_hex="#252526", shows_owner="parent"),
            Corner(which="tr", radius_px=4, shows_hex="#252526", shows_owner="parent"),
        ),
        measured=frozenset(["fill", "corners"]),
    )
    # Content node — QTextEdit with 8px radius
    content = SceneNode(
        node_id="notation_content",
        rect=Rect(716, 516, 564, 344),
        fill=Fill(
            rect=Rect(716, 516, 564, 344),
            kind="flat",
            hex_color="#252526",
            visible=True,
            visible_delta=30,
            background_hex="#1e1e1e",
        ),
        corners=(
            Corner(which="tl", radius_px=8, shows_hex="#1e1e1e", shows_owner="ancestor"),
            Corner(which="tr", radius_px=8, shows_hex="#1e1e1e", shows_owner="ancestor"),
        ),
        measured=frozenset(["fill", "corners"]),
        borders={
            "top": (1, "#363636"),
            "left": (1, "#363636"),
            "right": (1, "#363636"),
            "bottom": (1, "#363636"),
        },
    )
    # Joining seam between tab0 and content — closed (tab's bottom border intact)
    joining_seam = Seam(
        before_id="tab0",
        after_id="notation_content",
        axis="y",
        px=0,
        shows_hex="#363636",
        shows_owner="parent",
        closed=True,
        border_hex="#363636",
    )
    # Surface with joining seam
    surface = Surface(
        surface_id="tab_page",
        member_ids=("tab0", "notation_content"),
        role="tab_page",
        joined_at=joining_seam,
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 1280, 860),
        children=(tab, content),
        measured=frozenset(),
    )
    return Scene(
        scene_id="notation",
        region=Rect(716, 485, 564, 375),
        root=root,
        seams=(joining_seam,),
        surfaces=(surface,),
    )


def test_surface_broken_fires_four_breaks():
    """surface_broken finds exactly four breaks on the notation tab-page surface.

    Breaks: corner_tl (content), corner_tr (content), seam_closed, fill_mismatch.
    """
    scene = _make_broken_surface_scene()
    findings = surface_broken(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "surface_broken"
    assert f.verdict == "violated"
    breaks_str = f.measurements["breaks"]
    # Parse the breaks list from its string representation
    import ast
    breaks = ast.literal_eval(breaks_str)
    assert len(breaks) == 4, f"Expected 4 breaks, got {len(breaks)}: {breaks}"


def test_surface_broken_corner_listed_first():
    """surface_broken lists corner breaks first — they are the most visible defect.

    The corner notch directly beneath the selected tab is the main visual problem.
    """
    scene = _make_broken_surface_scene()
    findings = surface_broken(scene, {})
    assert findings
    first_break = findings[0].measurements["first_break"]
    assert first_break.startswith("corner_"), (
        f"Expected first break to be a corner, got {first_break!r}"
    )


def test_surface_broken_indeterminate_not_ok_when_corners_not_measured():
    """surface_broken emits 'indeterminate' when corners were not measured.

    An unmeasured property must not read as one that passed.  When corners were
    never measured, we cannot confirm the surface has no corner defects — the
    finding is indeterminate rather than ok.
    """
    # Surface with a clean seam (open) but corners NOT in measured
    tab = SceneNode(
        node_id="tab_clean",
        rect=Rect(0, 0, 79, 31),
        fill=Fill(
            rect=Rect(0, 0, 79, 31),
            kind="flat",
            hex_color="#007acc",
            visible=True,
            visible_delta=110,
            background_hex="#252526",
        ),
        corners=(),
        # "corners" deliberately NOT in measured
        measured=frozenset(["fill"]),
    )
    # Content fill is visibly different from tab fill (delta ~30) so fill_mismatch
    # does NOT fire — the only unknown is whether corners are OK.
    content = SceneNode(
        node_id="content_clean",
        rect=Rect(0, 31, 79, 100),
        fill=Fill(
            rect=Rect(0, 31, 79, 100),
            kind="flat",
            hex_color="#1e2d3d",
            visible=True,
            visible_delta=50,
            background_hex="#252526",
        ),
        corners=(),
        measured=frozenset(["fill"]),
    )
    # Clean seam (open, not closed)
    open_seam = Seam(
        before_id="tab_clean",
        after_id="content_clean",
        axis="y",
        px=0,
        closed=False,
    )
    surface = Surface(
        surface_id="tab_page_clean",
        member_ids=("tab_clean", "content_clean"),
        role="tab_page",
        joined_at=open_seam,
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 100, 200),
        children=(tab, content),
        measured=frozenset(),
    )
    scene = Scene(
        root=root,
        surfaces=(surface,),
        seams=(open_seam,),
    )
    findings = surface_broken(scene, {})
    assert len(findings) == 1, (
        f"Expected 1 indeterminate finding; got {len(findings)}"
    )
    f = findings[0]
    assert f.kind == "surface_broken"
    assert f.verdict == "indeterminate", (
        f"Expected 'indeterminate'; got {f.verdict!r}"
    )


def test_surface_broken_zero_breaks_clean_surface():
    """surface_broken emits no finding when all measurements pass.

    Corners measured, no corner breaks, seam open, fills match → clean surface.
    """
    tab = SceneNode(
        node_id="tab_ok",
        rect=Rect(0, 0, 79, 31),
        fill=Fill(
            rect=Rect(0, 0, 79, 31),
            kind="flat",
            hex_color="#007acc",
            visible=True,
            visible_delta=110,
            background_hex="#252526",
        ),
        corners=(
            Corner(which="tl", radius_px=0, shows_hex="", shows_owner="parent"),
            Corner(which="tr", radius_px=0, shows_hex="", shows_owner="parent"),
        ),
        measured=frozenset(["fill", "corners"]),
    )
    content = SceneNode(
        node_id="content_ok",
        rect=Rect(0, 31, 79, 100),
        fill=Fill(
            rect=Rect(0, 31, 79, 100),
            kind="flat",
            hex_color="#007acc",
            visible=True,
            visible_delta=110,
            background_hex="#252526",
        ),
        corners=(
            Corner(which="tl", radius_px=0, shows_hex="", shows_owner="parent"),
        ),
        measured=frozenset(["fill", "corners"]),
    )
    # Open seam — tab flows into content
    open_seam = Seam(
        before_id="tab_ok",
        after_id="content_ok",
        axis="y",
        px=0,
        closed=False,
    )
    surface = Surface(
        surface_id="tab_page_ok",
        member_ids=("tab_ok", "content_ok"),
        role="tab_page",
        joined_at=open_seam,
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 100, 200),
        children=(tab, content),
        measured=frozenset(),
    )
    scene = Scene(
        root=root,
        surfaces=(surface,),
        seams=(open_seam,),
    )
    findings = surface_broken(scene, {})
    assert findings == [], f"Expected no findings; got {findings}"


# ---------------------------------------------------------------------------
# orphan_style_rule
# ---------------------------------------------------------------------------

def _make_tabbar_scene() -> Scene:
    """Minimal notation scene: QTabBar + QTextEdit, no QTabWidget."""
    tabbar = SceneNode(
        node_id="ntabbar",
        rect=Rect(716, 485, 564, 31),
        cls="QTabBar",
        measured=frozenset(),
    )
    content = SceneNode(
        node_id="ntcontent",
        rect=Rect(716, 516, 564, 344),
        cls="QTextEdit",
        measured=frozenset(),
        style_rules=(
            {
                "selector": "QTabWidget::pane",
                "effective": "loaded_unmatched",
                "file": "Resources/Styles/Caissa.qss",
                "line": 214,
            },
        ),
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 1280, 860),
        children=(tabbar, content),
        measured=frozenset(),
    )
    return Scene(root=root)


def test_orphan_style_rule_fires_on_qtabwidget_pane():
    """orphan_style_rule fires when QTabWidget::pane is in the stylesheet but
    no QTabWidget exists anywhere in the widget tree.

    This is the live bug in Caissa: the tab-pane merge rule is dead code.
    """
    scene = _make_tabbar_scene()
    findings = orphan_style_rule(scene, {})
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "orphan_style_rule"
    assert f.verdict == "violated"
    assert "QTabWidget::pane" in f.measurements["selector"]
    assert f.measurements["widget_type"] == "QTabWidget"


def test_orphan_style_rule_silent_on_qtabbar_tab():
    """orphan_style_rule stays silent on QTabBar::tab when QTabBar IS in the tree."""
    tabbar = SceneNode(
        node_id="ntabbar2",
        rect=Rect(0, 0, 564, 31),
        cls="QTabBar",
        measured=frozenset(),
        style_rules=(
            {
                "selector": "QTabBar::tab",
                "effective": "effective",  # NOT loaded_unmatched
                "file": "Resources/Styles/Caissa.qss",
                "line": 224,
            },
        ),
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 1280, 860),
        children=(tabbar,),
        measured=frozenset(),
    )
    scene = Scene(root=root)
    findings = orphan_style_rule(scene, {})
    assert findings == []


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------

def test_run_all_emits_basis_disagreement():
    """run_all emits basis_disagreement when spacing_uniformity finds a split.

    Widget basis says uniform (all-0 gaps); perceived basis says non-uniform
    (2:1 spread).  run_all must emit both the spacing_uniformity finding AND a
    basis_disagreement finding with caused_by="spacing_uniformity".
    """
    nodes, cluster = _make_ribbon_tab_cluster()
    scene = _scene(*nodes, clusters=[cluster])
    findings = run_all(scene)

    kinds = [f.kind for f in findings]
    assert "spacing_uniformity" in kinds
    assert "basis_disagreement" in kinds

    bd = next(f for f in findings if f.kind == "basis_disagreement")
    assert bd.caused_by == "spacing_uniformity"
    assert bd.verdict == "non_uniform"


def test_run_all_ranks_by_severity_then_node_count():
    """run_all ranks error > warn > info, then by node count descending."""
    # Use the ribbon scene (has spacing_uniformity non_uniform + basis_disagreement)
    nodes, cluster = _make_ribbon_tab_cluster()
    scene = _scene(*nodes, clusters=[cluster])
    findings = run_all(scene)
    assert findings, "Expected at least one finding"
    for i in range(len(findings) - 1):
        a = findings[i]
        b = findings[i + 1]
        sev_order = {"error": 0, "warn": 1, "info": 2}
        sa = sev_order.get(a.severity, 9)
        sb = sev_order.get(b.severity, 9)
        if sa == sb:
            # Same severity — higher node count comes first
            assert len(a.node_ids) >= len(b.node_ids), (
                f"Ranking error: {a.kind} ({len(a.node_ids)} nodes) "
                f"before {b.kind} ({len(b.node_ids)} nodes) at same severity"
            )
        else:
            assert sa <= sb, (
                f"Severity ordering error: {a.kind} ({a.severity}) "
                f"before {b.kind} ({b.severity})"
            )


def test_run_all_only_filter():
    """run_all respects the only= filter."""
    nodes, cluster = _make_ribbon_tab_cluster()
    scene = _scene(*nodes, clusters=[cluster])
    findings = run_all(scene, only=["invisible_fill"])
    # No invisible fills in this scene (all fills are legitimate)
    assert all(f.kind in ("invisible_fill", "basis_disagreement") for f in findings)


def test_detectors_registry_has_five_entries():
    """The Phase 2b registry has exactly 5 detectors."""
    expected = {
        "invisible_fill",
        "spacing_uniformity",
        "peer_adjacency",
        "surface_broken",
        "orphan_style_rule",
    }
    assert set(DETECTORS.keys()) == expected


# ---------------------------------------------------------------------------
# Phase 7 detector stubs — deferred, strict xfail
# Each becomes a hard failure the moment it passes, preventing silent promotion.
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_fill_extent_silent_on_full_width_captions():
    """fill_extent must NOT fire on full-width captions (width CONSTANT = pane width).

    This is the regression guard for the wrong diagnosis: the pane captions ARE
    full-width.  If fill_extent fires on them, it has reproduced the error.
    """
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_contrast_fires():
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_missing_child_fires():
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_text_duplication_fires():
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_peer_divergence_fires():
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_edge_alignment_fires():
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_containment_fires():
    raise AssertionError("Phase 7 — not yet implemented")


@pytest.mark.xfail(strict=True, reason="Requires Phase 7 — driven by a real query")
def test_theme_blindness_fires():
    raise AssertionError("Phase 7 — not yet implemented")
