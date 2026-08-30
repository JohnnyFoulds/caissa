"""
tests/unit/rpa/test_eyes_cli.py — unit tests for the eyes CLI (Phase 4b).

Tests ingest, format-agent, and format-human CLI subcommands.

:spec: docs/features/rpa-design-vision/feature_spec.md §8 FR-12
"""
import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires Phase 4b — eyes CLI not yet written")
def test_ingest_decodes_base64_image_from_transcript():
    """eyes ingest must decode a base64 image embedded in a transcript JSON and
    write a valid PNG to the store — not a stub file of zero bytes."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4b — eyes CLI not yet written")
def test_ingest_unknown_phrase_no_socket_dies_naming_missing_thing():
    """eyes ingest with an unknown phrase and no open RPA socket must exit non-zero
    and include the unresolved phrase in the error message. It must not silently
    succeed with an empty region."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4b — eyes CLI not yet written")
def test_format_agent_under_2kb():
    """eyes format --agent on a 5-node Scene must produce output under 2 KB.
    The 2 KB budget is the agent-consumption contract (FR-12)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="Requires Phase 4b — eyes CLI not yet written")
def test_format_agent_last_line_starts_next():
    """The last line of eyes format --agent output must begin with 'Next:' so the
    consuming agent knows where to start without parsing the full report."""
    raise NotImplementedError
