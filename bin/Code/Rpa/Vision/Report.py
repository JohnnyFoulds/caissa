"""
bin/Code/Rpa/Vision/Report.py — Report emission and diff utilities.

Pure stdlib + json.  Tier 1 (cv2-free).  All file I/O writes to *out_dir*;
callers control where that points.

:spec: docs/features/rpa-design-vision/feature_spec.md §4
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from Code.Rpa.Vision.Scene import Finding, Scene

logger = logging.getLogger(__name__)

# Severity ordering for ranking
_SEV_ORDER = {"error": 0, "warn": 1, "info": 2}


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

def emit(
    scene: Scene,
    out_dir: Path,
    verbosity: str = "full",
    annotate: bool = True,
) -> dict:
    """Write ``report.json`` and ``scene.txt`` to *out_dir*.

    ``report.json`` is always complete regardless of *verbosity*.
    ``scene.txt`` is rendered at *verbosity*.

    :param scene: The scene to emit.
    :param out_dir: Directory to write into; created if absent.
    :param verbosity: ``"findings"`` | ``"summary"`` | ``"full"``.
    :param annotate: Reserved for future ``Annotate`` integration (ignored here).
    :return: Dict with ``"report_json"``, ``"scene_txt"`` path strings; also
        ``"annotated_png": ""`` as a placeholder.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.json"
    scene_path = out_dir / "scene.txt"

    report_path.write_text(
        json.dumps(scene.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    scene_path.write_text(
        scene.to_ascii(verbosity=verbosity),
        encoding="utf-8",
    )

    return {
        "report_json": str(report_path),
        "scene_txt": str(scene_path),
        "annotated_png": "",
        "crops": [],
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(
    scene: Scene,
    fmt: str = "agent",
) -> str:
    """Render the scene for consumption by a specific audience.

    :param scene: The scene to render.
    :param fmt: ``"agent"`` — findings only, ≤2 KB, last line starts ``NEXT:``;
        ``"json"`` — full JSON;
        ``"human"`` — full worked-example layout.
    :return: Rendered string.
    """
    if fmt == "json":
        return json.dumps(scene.to_dict(), indent=2, ensure_ascii=False)
    if fmt == "human":
        return scene.to_ascii(verbosity="full")

    # "agent" — compact findings + NEXT line
    lines: list[str] = []
    if scene.warnings:
        lines.append(f"WARNINGS: {', '.join(scene.warnings)}")

    ranked = sorted(
        scene.findings,
        key=lambda f: (_SEV_ORDER.get(f.severity, 9), -len(f.node_ids)),
    )
    for f in ranked:
        node_info = f" nodes={len(f.node_ids)}" if f.node_ids else ""
        confirmed = f.confirmed_by or "(pending)"
        lines.append(f"[{f.severity}] {f.kind}{node_info}")
        lines.append(f"  {f.summary}")
        if f.hypotheses:
            top = f.hypotheses[0]
            lines.append(f"  hypothesis [{top.likelihood}]: {top.mechanism}")
        lines.append(f"  confirmed_by: {confirmed}")

    if not ranked:
        lines.append("(no findings)")

    # NEXT instruction
    if ranked:
        top_finding = ranked[0]
        nid = top_finding.node_ids[0] if top_finding.node_ids else ""
        if nid:
            lines.append(f"NEXT: tools/caissa-eyes explain {nid}")
        else:
            lines.append("NEXT: tools/caissa-eyes inspect --verbosity full")
    elif scene.warnings and "no_capture" in scene.warnings:
        lines.append("NEXT: start the app with tools/caissa or pass --image PATH")
    else:
        lines.append("NEXT: tools/caissa-eyes inspect --verbosity full")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def diff(before: Scene, after: Scene) -> dict:
    """Compute a structural diff between two scenes joined on ``node_id``.

    :param before: Scene before a change.
    :param after: Scene after a change.
    :return: Dict with ``"added"``, ``"removed"``, ``"moved"``, ``"recoloured"``,
        ``"findings_gone"``, ``"findings_new"`` lists.
    """

    def _node_map(scene: Scene) -> dict[str, dict]:
        """Build a flat {node_id: {'rect': ..., 'fill_hex': ...}} index."""
        result: dict[str, dict] = {}
        if scene.root is not None:
            _collect(scene.root, result)
        return result

    def _collect(node, result: dict) -> None:
        fill_hex = ""
        if node.fill is not None:
            fill_hex = node.fill.hex_color or node.fill.hex_start
        result[node.node_id] = {
            "rect": node.rect,
            "fill_hex": fill_hex,
            "fill_visible": node.fill.visible if node.fill else None,
        }
        for child in node.children:
            _collect(child, result)

    before_nodes = _node_map(before)
    after_nodes = _node_map(after)

    added = [nid for nid in after_nodes if nid not in before_nodes]
    removed = [nid for nid in before_nodes if nid not in after_nodes]

    moved = []
    recoloured = []
    for nid in before_nodes:
        if nid not in after_nodes:
            continue
        b = before_nodes[nid]
        a = after_nodes[nid]
        if b["rect"] != a["rect"]:
            moved.append({
                "node_id": nid,
                "before_rect": {"x": b["rect"].x, "y": b["rect"].y,
                                "w": b["rect"].w, "h": b["rect"].h},
                "after_rect": {"x": a["rect"].x, "y": a["rect"].y,
                               "w": a["rect"].w, "h": a["rect"].h},
            })
        if b["fill_hex"] != a["fill_hex"]:
            recoloured.append({
                "node_id": nid,
                "before_hex": b["fill_hex"],
                "after_hex": a["fill_hex"],
            })

    # Findings diff
    before_kinds = {(f.kind, f.node_ids) for f in before.findings}
    after_kinds = {(f.kind, f.node_ids) for f in after.findings}

    findings_gone = [
        {"kind": k, "node_ids": list(n)}
        for k, n in before_kinds - after_kinds
    ]
    findings_new = [
        {"kind": k, "node_ids": list(n)}
        for k, n in after_kinds - before_kinds
    ]

    return {
        "added": added,
        "removed": removed,
        "moved": moved,
        "recoloured": recoloured,
        "findings_gone": findings_gone,
        "findings_new": findings_new,
    }


# ---------------------------------------------------------------------------
# Two-sided pass
# ---------------------------------------------------------------------------

def two_sided_pass(
    before: Scene,
    after: Scene,
    target_kind: str,
) -> tuple[bool, str]:
    """Evaluate the design-verify pass condition.

    PASS requires *both*:

    1. The ``target_kind`` finding is absent from *after*.
    2. No new finding at or above ``"warn"`` severity has appeared.

    :param before: Scene before the fix.
    :param after: Scene after the fix.
    :param target_kind: The finding kind that should be gone.
    :return: ``(passed: bool, reason: str)`` — *reason* is empty on pass.
    """
    # Check target gone
    remaining = [f for f in after.findings if f.kind == target_kind]
    if remaining:
        return (
            False,
            f"finding '{target_kind}' still present ({len(remaining)} instances)",
        )

    # Check no new warn/error findings
    before_kinds = {(f.kind, f.node_ids) for f in before.findings}
    new_findings = [
        f for f in after.findings
        if (f.kind, f.node_ids) not in before_kinds
        and f.severity in ("error", "warn")
    ]
    if new_findings:
        new_desc = ", ".join(f.kind for f in new_findings)
        return (False, f"new findings appeared: {new_desc}")

    return (True, "")


# ---------------------------------------------------------------------------
# Write spec
# ---------------------------------------------------------------------------

def write_spec(scene: Scene, name: str, out: Path) -> Path:
    """Generate a skeleton ``*.spec.json`` from a measured scene.

    :param scene: Source scene (from a reference render).
    :param name: Spec name, e.g. ``"ribbon"``.
    :param out: Output directory.
    :return: Path of the written spec file.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    spec: dict = {
        "name": name,
        "source_ref": scene.scene_id,
        "themes": {},
        "geometry": {
            "total_height": scene.region.h,
        },
        "invariants": [],
        "known_deviations": [],
    }

    spec_path = out / f"{name}.spec.json"
    spec_path.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("wrote spec to %s", spec_path)
    return spec_path
