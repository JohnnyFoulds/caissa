"""
tests/unit/rpa/test_scene.py — unit tests for Vision/Scene.py and Vision/Measure.py.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

import json
import math
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Scene / SceneNode basics
# ---------------------------------------------------------------------------

def test_scene_to_dict_is_json_serialisable():
    """Scene.to_dict() produces output that json.dumps handles without error."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Fill
    from Code.Rpa.Types import Rect

    node = SceneNode(
        node_id="tab[0]",
        rect=Rect(0, 0, 46, 25),
        cls="QTabBar",
        fill=Fill(rect=Rect(4, 5, 43, 21), kind="flat", hex_color="#007acc", visible=True,
                  visible_delta=80, background_hex="#252526"),
        measured=frozenset({"fill"}),
    )
    scene = Scene(
        scene_id="test",
        region=Rect(0, 0, 354, 25),
        root=node,
        dpr=2.0,
        theme="Caissa",
    )
    d = scene.to_dict()
    serialised = json.dumps(d)
    assert '"scene_id": "test"' in serialised
    assert '"hex_color": "#007acc"' in serialised


def test_scene_to_ascii_full_includes_not_measured():
    """to_ascii(full) prints 'not measured:' for inventory items not in node.measured."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode
    from Code.Rpa.Types import Rect

    node = SceneNode(
        node_id="btn",
        rect=Rect(10, 10, 50, 20),
        cls="QPushButton",
        measured=frozenset({"fill"}),  # ink, borders, corners, seams NOT measured
    )
    scene = Scene(scene_id="s", region=Rect(0, 0, 100, 50), root=node)
    txt = scene.to_ascii(verbosity="full")
    assert "not measured:" in txt


def test_scene_to_ascii_findings_verbosity_omits_nodes():
    """to_ascii(findings) omits the node table and shows only findings."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Finding
    from Code.Rpa.Types import Rect

    node = SceneNode(node_id="x", rect=Rect(0, 0, 10, 10), cls="QWidget")
    finding = Finding(
        kind="invisible_fill",
        verdict="violated",
        summary="fill is invisible",
        node_ids=("x",),
        severity="warn",
    )
    scene = Scene(
        scene_id="s", region=Rect(0, 0, 100, 50), root=node,
        findings=(finding,)
    )
    txt = scene.to_ascii(verbosity="findings")
    assert "invisible_fill" in txt
    assert "not measured" not in txt  # node table suppressed


def test_scene_from_observations_flat():
    """from_observations with 3 nodes makes first node root with 2 children."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode
    from Code.Rpa.Types import Rect

    nodes = [
        SceneNode(node_id="n0", rect=Rect(0, 0, 10, 10)),
        SceneNode(node_id="n1", rect=Rect(10, 0, 10, 10)),
        SceneNode(node_id="n2", rect=Rect(20, 0, 10, 10)),
    ]
    scene = Scene.from_observations(nodes, scene_id="flat")
    assert scene.root is not None
    assert scene.root.node_id == "n0"
    assert len(scene.root.children) == 2


def test_scene_finding_confirmed_by_pending_in_dict():
    """A finding with no confirmed_by serialises as '(pending)'."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Finding
    from Code.Rpa.Types import Rect

    finding = Finding(kind="invisible_fill", verdict="violated", summary="x",
                      confirmed_by="")
    scene = Scene(
        scene_id="s", region=Rect(0, 0, 100, 50),
        root=SceneNode(node_id="r", rect=Rect(0, 0, 10, 10)),
        findings=(finding,),
    )
    d = scene.to_dict()
    assert d["findings"][0]["confirmed_by"] == "(pending)"


# ---------------------------------------------------------------------------
# Measure — basic geometry
# ---------------------------------------------------------------------------

def test_gap_x_axis():
    """gap() returns the pixel distance between two rects on x."""
    from Code.Rpa.Vision.Measure import gap
    from Code.Rpa.Types import Rect

    a = Rect(0, 0, 46, 25)
    b = Rect(46, 0, 60, 25)
    assert gap(a, b, "x") == 0

    b2 = Rect(48, 0, 60, 25)
    assert gap(a, b2, "x") == 2


def test_to_logical_floors_origin_ceils_extent():
    """to_logical floors x/y and ceils right/bottom to never under-cover source."""
    from Code.Rpa.Vision.Measure import to_logical
    from Code.Rpa.Types import Rect

    phys = Rect(1, 1, 87, 51)
    logical = to_logical(phys, dpr=2.0)
    # x=floor(0.5)=0, y=0; right=ceil(44)=44, bottom=ceil(26)=26
    assert logical.x == 0
    assert logical.y == 0
    assert logical.w == 44
    assert logical.h == 26


def test_aligned_top_edge():
    """aligned() returns True when all top edges are within tolerance."""
    from Code.Rpa.Vision.Measure import aligned
    from Code.Rpa.Types import Rect

    rects = [Rect(0, 10, 50, 20), Rect(50, 11, 50, 20), Rect(100, 10, 50, 20)]
    assert aligned(rects, edge="top", tolerance_px=1) is True
    assert aligned(rects, edge="top", tolerance_px=0) is False


def test_uniformity_uniform_gaps():
    """uniformity() returns 'uniform' for constant values."""
    from Code.Rpa.Vision.Measure import uniformity

    verdict, spread = uniformity([2, 2, 2, 2])
    assert verdict == "uniform"
    assert spread == 0.0


def test_uniformity_non_uniform():
    """uniformity() returns 'non_uniform' for a 2.08x spread."""
    from Code.Rpa.Vision.Measure import uniformity

    verdict, spread = uniformity([12, 13, 24, 24, 25])
    assert verdict == "non_uniform"
    assert spread == 13.0


def test_uniformity_all_none():
    """uniformity() returns 'indeterminate' when all values are None."""
    from Code.Rpa.Vision.Measure import uniformity

    verdict, _ = uniformity([None, None, None])
    assert verdict == "indeterminate"


def test_uniformity_mixed_none():
    """uniformity() excludes None values and assesses the defined ones."""
    from Code.Rpa.Vision.Measure import uniformity

    verdict, _ = uniformity([2, None, 2, 2])
    assert verdict == "uniform"


# ---------------------------------------------------------------------------
# Measure — gaps / four bases
# ---------------------------------------------------------------------------

def _make_tab_nodes():
    """Return 6 synthetic tab SceneNodes matching the 6-tab ribbon fixture."""
    from Code.Rpa.Vision.Scene import SceneNode, Fill, Ink
    from Code.Rpa.Types import Rect

    data = [
        ("tab[0]", Rect(0, 0, 46, 25),
         Fill(rect=Rect(4, 5, 43, 21), hex_color="#007acc", visible=True,
              visible_delta=80, background_hex="#252526"),
         Ink(rect=Rect(13, 8, 19, 9), hex_dominant="#ffffff")),
        ("tab[1]", Rect(46, 0, 60, 25),
         Fill(rect=Rect(46, 0, 60, 25), hex_color="#ffffff", visible=True,
              visible_delta=50, background_hex="#252526"),
         Ink(rect=Rect(58, 8, 35, 9), hex_dominant="#005b99")),
        ("tab[2]", Rect(106, 0, 59, 25),
         Fill(rect=Rect(106, 0, 59, 25), hex_color="#252526", visible=False,
              visible_delta=0, background_hex="#252526"),
         Ink(rect=Rect(118, 8, 33, 9), hex_dominant="#d4d4d4")),
        ("tab[3]", Rect(165, 0, 72, 25),
         Fill(rect=Rect(165, 0, 72, 25), hex_color="#252526", visible=False,
              visible_delta=0, background_hex="#252526"),
         Ink(rect=Rect(175, 8, 50, 9), hex_dominant="#d4d4d4")),
        ("tab[4]", Rect(237, 0, 64, 25),
         Fill(rect=Rect(237, 0, 64, 25), hex_color="#252526", visible=False,
              visible_delta=0, background_hex="#252526"),
         Ink(rect=Rect(249, 8, 39, 9), hex_dominant="#d4d4d4")),
        ("tab[5]", Rect(301, 0, 53, 25),
         Fill(rect=Rect(301, 0, 53, 25), hex_color="#252526", visible=False,
              visible_delta=0, background_hex="#252526"),
         Ink(rect=Rect(313, 8, 28, 9), hex_dominant="#d4d4d4")),
    ]
    return [
        SceneNode(node_id=nid, rect=r, fill=f, ink=i,
                  measured=frozenset({"fill", "ink"}))
        for nid, r, f, i in data
    ]


def test_gaps_widget_basis_all_zero():
    """Widget gaps for abutting tabs are all 0 — the ticker that passes."""
    from Code.Rpa.Vision.Measure import gaps, BASIS_WIDGET

    nodes = _make_tab_nodes()
    result = gaps(nodes, axis="x", basis=BASIS_WIDGET)
    assert len(result) == 5
    assert all(g.px == 0 for g in result)


def test_gaps_fill_basis_invisible_tabs_undefined():
    """Fill gaps are undefined for tabs with invisible fills."""
    from Code.Rpa.Vision.Measure import gaps, BASIS_FILL

    nodes = _make_tab_nodes()
    result = gaps(nodes, axis="x", basis=BASIS_FILL)
    # First gap (File→Home) both visible → defined
    assert result[0].px is not None
    # Remaining gaps involve invisible fills → undefined
    for g in result[1:]:
        assert g.px is None
        assert "visible" in g.undefined_reason


def test_perceived_gaps_non_uniform():
    """Perceived gaps for the 6-tab fixture show a 2x spread (the design defect)."""
    from Code.Rpa.Vision.Measure import perceived_gaps, uniformity

    nodes = _make_tab_nodes()
    result = perceived_gaps(nodes, axis="x")
    assert len(result) == 5
    defined = [g.px for g in result if g.px is not None]
    assert len(defined) >= 4
    verdict, spread = uniformity(defined)
    # The spread must be clearly non-uniform (design-record §query-1)
    assert verdict == "non_uniform"
    assert spread >= 10


def test_gaps_all_bases_returns_four_keys():
    """gaps_all_bases returns a dict with all four basis keys."""
    from Code.Rpa.Vision.Measure import gaps_all_bases, BASIS_WIDGET, BASIS_FILL, BASIS_INK, BASIS_PERCEIVED

    nodes = _make_tab_nodes()
    result = gaps_all_bases(nodes, axis="x")
    assert set(result.keys()) == {BASIS_WIDGET, BASIS_FILL, BASIS_INK, BASIS_PERCEIVED}


# ---------------------------------------------------------------------------
# Measure — seams
# ---------------------------------------------------------------------------

def _make_notation_tab_nodes():
    """5 tab nodes with 2 px gaps showing ancestor colour — query 3 fixture."""
    from Code.Rpa.Vision.Scene import SceneNode, Fill
    from Code.Rpa.Types import Rect

    # Each tab is closed with a 1px #363636 border; 2px gaps between them
    nodes = []
    x = 717
    widths = [79, 76, 100, 119, 89]
    labels = ["Moves", "Comments", "Engine", "Eval", "Board"]
    for i, (w, label) in enumerate(zip(widths, labels)):
        nodes.append(SceneNode(
            node_id=f"ntab[{i}]",
            rect=Rect(x, 485, w, 31),
            cls="tab",
            label=label,
            fill=Fill(rect=Rect(x, 485, w, 31), hex_color="#252526",
                      visible=False, visible_delta=2,
                      background_hex="#252526"),
            borders={
                "top": (1, "#363636"),
                "bottom": (1, "#363636"),
                "left": (1, "#363636"),
                "right": (1, "#363636"),
            },
            measured=frozenset({"fill", "borders"}),
        ))
        x += w + 2  # 2 px gap showing #1e1e1e (window background = ancestor)
    return nodes


def test_seams_notation_tabs_all_two_px():
    """Seams between notation tabs measure 2 px (the margin-right: 2px)."""
    from Code.Rpa.Vision.Measure import seams

    nodes = _make_notation_tab_nodes()
    result = seams(nodes, axis="x")
    assert len(result) == 4
    assert all(s.px == 2 for s in result)


def test_spacing_uniformity_passes_notation_tabs():
    """Widget gaps of 2,2,2,2 are uniform — the wrong-predicate lesson from query 3."""
    from Code.Rpa.Vision.Measure import gaps, uniformity, BASIS_WIDGET

    nodes = _make_notation_tab_nodes()
    widget_gaps = gaps(nodes, axis="x", basis=BASIS_WIDGET)
    verdict, spread = uniformity([g.px for g in widget_gaps])
    assert verdict == "uniform", (
        "spacing_uniformity must PASS this scene — the peer_adjacency "
        "detector is what catches it, not spacing_uniformity"
    )


# ---------------------------------------------------------------------------
# Measure — surfaces
# ---------------------------------------------------------------------------

def test_surface_breaks_corner_first_then_seam():
    """surface_breaks lists corner breaks before seam breaks."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Surface, Seam, Fill, Corner
    from Code.Rpa.Vision.Measure import surface_breaks
    from Code.Rpa.Types import Rect

    tab_node = SceneNode(
        node_id="tab[0]",
        rect=Rect(717, 485, 79, 31),
        fill=Fill(hex_color="#272728", visible=False, visible_delta=2,
                  background_hex="#252526"),
        measured=frozenset({"fill", "corners"}),
        # No corners measured on the tab itself
    )
    content_node = SceneNode(
        node_id="notation_content",
        rect=Rect(716, 516, 564, 344),
        fill=Fill(hex_color="#252526", visible=False, visible_delta=0,
                  background_hex="#252526"),
        corners=(
            Corner(which="tl", radius_px=8, shows_hex="#1e1e1e",
                   shows_owner="ancestor"),
            Corner(which="tr", radius_px=8, shows_hex="#1e1e1e",
                   shows_owner="ancestor"),
        ),
        measured=frozenset({"fill", "corners"}),
    )
    joining_seam = Seam(
        before_id="tab[0]",
        after_id="notation_content",
        axis="y",
        px=0,
        shows_owner="unknown",
        closed=True,      # bottom border of tab closes against content top
        border_hex="#363636",
    )
    surface = Surface(
        surface_id="tab_page",
        member_ids=("tab[0]", "notation_content"),
        role="tab_page",
        joined_at=joining_seam,
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(716, 485, 564, 375),
        children=(tab_node, content_node),
    )
    scene = Scene(
        scene_id="notation",
        region=Rect(716, 485, 564, 375),
        root=root,
        surfaces=(surface,),
        seams=(joining_seam,),
    )

    breaks = surface_breaks(surface, scene)
    assert len(breaks) == 3, f"expected 3 breaks, got {breaks}"
    # Corner breaks must come first
    assert breaks[0].startswith("corner_tl"), f"first break should be corner_tl, got {breaks[0]}"
    assert "seam_closed" in breaks


def test_surface_no_breaks_when_open_seam_and_no_corners():
    """A surface with no radius corners and an open seam has zero breaks."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Surface, Seam, Fill, Corner
    from Code.Rpa.Vision.Measure import surface_breaks
    from Code.Rpa.Types import Rect

    tab_node = SceneNode(
        node_id="tab[0]",
        rect=Rect(0, 0, 50, 20),
        fill=Fill(hex_color="#272728", visible=True, visible_delta=15,
                  background_hex="#252526"),
        measured=frozenset({"fill", "corners"}),
        corners=(),  # measured and square
    )
    content_node = SceneNode(
        node_id="content",
        rect=Rect(0, 20, 50, 80),
        fill=Fill(hex_color="#272728", visible=True, visible_delta=15,
                  background_hex="#252526"),
        corners=(),  # square
        measured=frozenset({"fill", "corners"}),
    )
    open_seam = Seam(
        before_id="tab[0]",
        after_id="content",
        axis="y",
        px=0,
        closed=False,   # open — correct
        shows_owner="parent",
    )
    surface = Surface(
        surface_id="tab_page",
        member_ids=("tab[0]", "content"),
        role="tab_page",
        joined_at=open_seam,
    )
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 50, 100),
        children=(tab_node, content_node),
    )
    scene = Scene(
        scene_id="ok",
        region=Rect(0, 0, 50, 100),
        root=root,
        surfaces=(surface,),
        seams=(open_seam,),
    )
    breaks = surface_breaks(surface, scene)
    assert breaks == [], f"expected no breaks, got {breaks}"


def test_surface_indeterminate_when_corners_not_measured():
    """surface_breaks must NOT conclude on corners when 'corners' is not in measured."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Surface, Seam, Corner
    from Code.Rpa.Vision.Measure import surface_breaks
    from Code.Rpa.Types import Rect

    # corners field is empty AND not in measured — ambiguous (could be square)
    node = SceneNode(
        node_id="n",
        rect=Rect(0, 0, 50, 50),
        measured=frozenset({"fill"}),  # corners NOT measured
        corners=(),
    )
    content = SceneNode(
        node_id="c",
        rect=Rect(0, 50, 50, 50),
        measured=frozenset({"fill"}),
        corners=(),
    )
    open_seam = Seam(before_id="n", after_id="c", axis="y", px=0, closed=False)
    surface = Surface(
        surface_id="sp",
        member_ids=("n", "c"),
        role="tab_page",
        joined_at=open_seam,
    )
    root = SceneNode(node_id="root", rect=Rect(0, 0, 50, 100), children=(node, content))
    scene = Scene(scene_id="s", region=Rect(0, 0, 50, 100), root=root,
                  surfaces=(surface,), seams=(open_seam,))

    breaks = surface_breaks(surface, scene)
    # No corner breaks because corners were not measured
    corner_breaks = [b for b in breaks if b.startswith("corner_")]
    assert corner_breaks == [], (
        "must NOT infer 'square corners' from unmeasured corners — "
        "this is the exact failure mode that hid the notation-tab bug"
    )


# ---------------------------------------------------------------------------
# Measure — peer clustering
# ---------------------------------------------------------------------------

def test_peers_finds_pane_caption_cluster():
    """peers() groups 4 identical-height nodes into one cluster."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Fill
    from Code.Rpa.Vision.Measure import peers
    from Code.Rpa.Types import Rect

    captions = [
        SceneNode(
            node_id=f"cap[{i}]",
            rect=Rect(755, 200 + i * 100, 566, 20),
            role="widget",
            cls="QLabel",
            fill=Fill(rect=Rect(755, 200 + i * 100, 566, 20),
                      kind="gradient_v", hex_start="#252526", hex_end="#363636",
                      visible=False, background_hex="#2d2d2d"),
            measured=frozenset({"fill"}),
        )
        for i in range(4)
    ]
    root = SceneNode(
        node_id="root",
        rect=Rect(748, 200, 566, 720),
        children=tuple(captions),
    )
    scene = Scene(scene_id="panes", region=Rect(748, 200, 566, 720), root=root)

    clusters = peers(scene, min_size=2)
    assert len(clusters) >= 1
    sizes = {c.cluster_id: len(c.members) for c in clusters}
    assert max(sizes.values()) == 4


def test_compare_peers_fill_visible_constant_false():
    """compare_peers reports fill_visible as CONSTANT False for invisible captions."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Fill, PeerCluster
    from Code.Rpa.Vision.Measure import compare_peers
    from Code.Rpa.Types import Rect

    nodes = [
        SceneNode(
            node_id=f"cap[{i}]",
            rect=Rect(0, i * 100, 566, 20),
            fill=Fill(visible=False, background_hex="#2d2d2d"),
            measured=frozenset({"fill"}),
        )
        for i in range(4)
    ]
    root = SceneNode(
        node_id="root",
        rect=Rect(0, 0, 566, 420),
        children=tuple(nodes),
    )
    scene = Scene(scene_id="s", region=Rect(0, 0, 566, 420), root=root)
    cluster = PeerCluster(
        cluster_id="pane_caption",
        signature=(),
        members=tuple(n.node_id for n in nodes),
        parents=("root",) * 4,
    )
    attrs = compare_peers(cluster, scene)
    assert "fill_visible" in attrs
    assert attrs["fill_visible"].status == "CONSTANT"
    assert all(v is False for v in attrs["fill_visible"].values)


# ---------------------------------------------------------------------------
# Measure — perceptual helpers
# ---------------------------------------------------------------------------

def test_fill_is_visible_flat_accent():
    """fill_is_visible returns True for #007acc against #252526."""
    from Code.Rpa.Vision.Measure import fill_is_visible

    assert fill_is_visible("#007acc", "#252526") is True


def test_fill_is_visible_gradient_straddling_background():
    """A gradient straddling its background may have low delta at midpoint.

    Tests the mean vs max distinction: the midpoint of #252526->#363636 over
    #2d2d2d has a low delta, demonstrating the need for max-based visibility.
    """
    from Code.Rpa.Vision.Measure import fill_is_visible

    # Midpoint of the gradient (~#2d2d2e) vs background #2d2d2d — very low delta
    assert fill_is_visible("#2d2d2e", "#2d2d2d", delta=12) is False
    # But the endpoint #363636 vs #2d2d2d is clearly visible
    assert fill_is_visible("#363636", "#2d2d2d", delta=12) is True


def test_contrast_ratio_white_on_black():
    """contrast_ratio returns 21.0 for white on black."""
    from Code.Rpa.Vision.Measure import contrast_ratio

    ratio = contrast_ratio("#ffffff", "#000000")
    assert abs(ratio - 21.0) < 0.01


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def test_report_emit_writes_files(tmp_path):
    """Report.emit writes report.json and scene.txt to out_dir."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode
    from Code.Rpa.Vision.Report import emit
    from Code.Rpa.Types import Rect

    scene = Scene(
        scene_id="test",
        region=Rect(0, 0, 100, 50),
        root=SceneNode(node_id="r", rect=Rect(0, 0, 10, 10)),
    )
    result = emit(scene, out_dir=tmp_path)
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "scene.txt").exists()
    assert "report_json" in result


def test_report_diff_detects_added_and_removed():
    """Report.diff reports added/removed nodes by node_id join."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode
    from Code.Rpa.Vision.Report import diff
    from Code.Rpa.Types import Rect

    before = Scene(
        scene_id="before",
        region=Rect(0, 0, 100, 50),
        root=SceneNode(
            node_id="root",
            rect=Rect(0, 0, 100, 50),
            children=(
                SceneNode(node_id="a", rect=Rect(0, 0, 50, 50)),
                SceneNode(node_id="b", rect=Rect(50, 0, 50, 50)),
            ),
        ),
    )
    after = Scene(
        scene_id="after",
        region=Rect(0, 0, 100, 50),
        root=SceneNode(
            node_id="root",
            rect=Rect(0, 0, 100, 50),
            children=(
                SceneNode(node_id="a", rect=Rect(0, 0, 50, 50)),
                SceneNode(node_id="c", rect=Rect(50, 0, 50, 50)),  # b→c
            ),
        ),
    )
    result = diff(before, after)
    assert "b" in result["removed"]
    assert "c" in result["added"]


def test_two_sided_pass_requires_both_conditions():
    """two_sided_pass fails if finding remains OR new finding appears."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Finding
    from Code.Rpa.Vision.Report import two_sided_pass
    from Code.Rpa.Types import Rect

    root = SceneNode(node_id="r", rect=Rect(0, 0, 10, 10))
    finding_a = Finding(kind="invisible_fill", verdict="violated",
                        summary="x", node_ids=("r",), severity="warn")
    finding_b = Finding(kind="new_problem", verdict="violated",
                        summary="y", node_ids=("r",), severity="warn")

    before = Scene(scene_id="b", region=Rect(0, 0, 10, 10), root=root,
                   findings=(finding_a,))
    # Case 1: finding still present
    after_still_present = Scene(scene_id="a", region=Rect(0, 0, 10, 10), root=root,
                                findings=(finding_a,))
    passed, reason = two_sided_pass(before, after_still_present, "invisible_fill")
    assert not passed
    assert "still present" in reason

    # Case 2: finding gone but new one appeared
    after_new_problem = Scene(scene_id="a", region=Rect(0, 0, 10, 10), root=root,
                              findings=(finding_b,))
    passed, reason = two_sided_pass(before, after_new_problem, "invisible_fill")
    assert not passed
    assert "new findings" in reason

    # Case 3: finding gone, no new warn/error → pass
    after_clean = Scene(scene_id="a", region=Rect(0, 0, 10, 10), root=root,
                        findings=())
    passed, reason = two_sided_pass(before, after_clean, "invisible_fill")
    assert passed
    assert reason == ""


# ---------------------------------------------------------------------------
# Spec-required test name aliases (feature_steps.md §Phase 2 TDD gate)
# ---------------------------------------------------------------------------

def test_scene_node_measured_field_distinguishes_not_measured_from_absent():
    """measured=frozenset() vs measured={'fill'} are different states."""
    from Code.Rpa.Vision.Scene import SceneNode, Fill
    from Code.Rpa.Types import Rect

    unmeasured = SceneNode(node_id="a", rect=Rect(0, 0, 10, 10), measured=frozenset())
    measured_absent = SceneNode(
        node_id="b", rect=Rect(0, 0, 10, 10),
        fill=None, measured=frozenset({"fill"})
    )
    assert "fill" not in unmeasured.measured
    assert "fill" in measured_absent.measured
    assert measured_absent.fill is None  # measured, but fill was absent


def test_fill_gradient_visible_uses_max_not_mean():
    """fill_is_visible with the endpoint hex must pass; midpoint hex must fail."""
    from Code.Rpa.Vision.Measure import fill_is_visible

    # endpoint of #252526->#363636 gradient vs background #2d2d2d
    assert fill_is_visible("#363636", "#2d2d2d", delta=12) is True
    # midpoint (~#2d2d2e) is invisible
    assert fill_is_visible("#2d2d2e", "#2d2d2d", delta=12) is False


def test_fill_visible_false_for_palette_window_match():
    """palette().window() colour equal to background is not visible."""
    from Code.Rpa.Vision.Measure import fill_is_visible

    # palette().window() on dark theme ≈ #252526; same as background
    assert fill_is_visible("#252526", "#252526", delta=12) is False


def test_to_ascii_includes_not_measured_line():
    """to_ascii(full) includes 'not measured:' when inventory is incomplete."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode
    from Code.Rpa.Types import Rect

    node = SceneNode(
        node_id="x", rect=Rect(0, 0, 10, 10),
        measured=frozenset({"fill"}),  # corners, ink, borders, seams missing
    )
    scene = Scene(scene_id="s", region=Rect(0, 0, 10, 10), root=node)
    txt = scene.to_ascii(verbosity="full")
    assert "not measured:" in txt


def test_report_render_agent_format_ends_with_next():
    """render('agent') always ends with a NEXT: line."""
    from Code.Rpa.Vision.Scene import Scene, SceneNode, Finding
    from Code.Rpa.Vision.Report import render
    from Code.Rpa.Types import Rect

    finding = Finding(kind="invisible_fill", verdict="violated",
                      summary="fill invisible", node_ids=("tab[0]",), severity="warn")
    scene = Scene(
        scene_id="s",
        region=Rect(0, 0, 100, 50),
        root=SceneNode(node_id="r", rect=Rect(0, 0, 10, 10)),
        findings=(finding,),
    )
    output = render(scene, fmt="agent")
    assert output.strip().split("\n")[-1].startswith("NEXT:")
    assert len(output) <= 2048, "agent format must stay ≤ 2 KB"
