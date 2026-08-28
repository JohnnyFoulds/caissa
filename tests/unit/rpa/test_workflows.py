"""
tests/unit/rpa/test_workflows.py — Unit tests for the Phase 8 Workflows package.

Tests in this file require no running Caissa process and no Qt display.

:spec: FR-10, §13 (feature_spec.md)
"""

from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.rpa


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_register_and_get():
    """Registry.register() stores activities; Registry.get() returns a copy."""
    from Code.Rpa.Workflows.Registry import _clear, get, register
    from Code.Rpa.Activities import Activity

    class _Stub(Activity):
        name = "Stub"
        def precondition(self, ctx): return True
        def execute(self, ctx): pass
        def postcondition(self, ctx): return True

    _clear()
    a = _Stub()
    register("test_wf", [a])
    result = get("test_wf")
    assert result == [a]
    assert result is not [a]  # copy, not the same list object


def test_registry_get_returns_copy():
    """get() returns a new list so mutations do not affect the registry."""
    from Code.Rpa.Workflows.Registry import _clear, get, register
    from Code.Rpa.Activities import Activity

    class _Stub(Activity):
        name = "Stub2"
        def precondition(self, ctx): return True
        def execute(self, ctx): pass
        def postcondition(self, ctx): return True

    _clear()
    register("copy_wf", [_Stub()])
    result = get("copy_wf")
    result.clear()
    assert len(get("copy_wf")) == 1, "Registry copy was mutated"


def test_registry_unknown_raises_workflow_not_found_error():
    """Registry.get() raises WorkflowNotFoundError for unknown workflow names."""
    from Code.Rpa.Errors import WorkflowNotFoundError
    from Code.Rpa.Workflows.Registry import _clear, get

    _clear()
    with pytest.raises(WorkflowNotFoundError, match="not registered"):
        get("no_such_workflow")


def test_registry_all_names_sorted():
    """Registry.all_names() returns sorted workflow names."""
    from Code.Rpa.Workflows.Registry import _clear, all_names, register
    from Code.Rpa.Activities import Activity

    class _Stub(Activity):
        name = "Stub3"
        def precondition(self, ctx): return True
        def execute(self, ctx): pass
        def postcondition(self, ctx): return True

    _clear()
    register("zzz", [_Stub()])
    register("aaa", [_Stub()])
    register("mmm", [_Stub()])
    assert all_names() == ["aaa", "mmm", "zzz"]


# ---------------------------------------------------------------------------
# Built-in workflows load and register
# ---------------------------------------------------------------------------

def test_builtin_workflows_register():
    """All four built-in workflow modules register on import."""
    # Import the modules directly (bypassing Service init)
    import importlib
    from Code.Rpa.Workflows.Registry import _clear, all_names

    _clear()
    for mod in [
        "Code.Rpa.Workflows.smoke_home",
        "Code.Rpa.Workflows.classical_invariant",
        "Code.Rpa.Workflows.play_a_game",
        "Code.Rpa.Workflows.config_roundtrip",
    ]:
        # Reload to re-trigger self-registration after _clear
        module = importlib.import_module(mod)
        importlib.reload(module)

    names = all_names()
    assert "smoke_home" in names
    assert "classical_invariant" in names
    assert "play_a_game" in names
    assert "config_roundtrip" in names


# ---------------------------------------------------------------------------
# Manifest integrity — template references
# ---------------------------------------------------------------------------

def test_every_workflow_template_ref_is_in_manifest():
    """Every template name referenced in workflow activities must appear in the manifest.

    Currently no workflows reference templates (Phase 8 adds object-tier-only
    workflows), so this test passes with an empty template list.  It will catch
    future workflows that reference non-existent templates.
    """
    # Load the manifest
    manifest_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "Resources", "Rpa", "Templates", "manifest.json"
    )
    manifest_path = os.path.normpath(manifest_path)

    assert os.path.isfile(manifest_path), (
        f"manifest.json not found at {manifest_path!r}"
    )

    with open(manifest_path, encoding="utf-8") as fh:
        data = json.load(fh)

    manifest_names = {entry["name"] for entry in data.get("templates", [])}

    # Collect all selector.image references from registered activities
    import importlib
    from Code.Rpa.Workflows.Registry import _clear, all_names, get

    _clear()
    for mod in [
        "Code.Rpa.Workflows.smoke_home",
        "Code.Rpa.Workflows.classical_invariant",
        "Code.Rpa.Workflows.play_a_game",
        "Code.Rpa.Workflows.config_roundtrip",
    ]:
        module = importlib.import_module(mod)
        importlib.reload(module)

    missing_templates = []
    for name in all_names():
        for activity in get(name):
            # Activities with a selector attribute may reference templates
            selector = getattr(activity, "_selector", None)
            if selector is None:
                continue
            image_ref = getattr(selector, "image", None)
            if image_ref and image_ref not in manifest_names:
                missing_templates.append(
                    f"workflow={name!r}, activity={activity.name!r}, image={image_ref!r}"
                )

    assert not missing_templates, (
        "Template references not in manifest:\n" + "\n".join(missing_templates)
    )
