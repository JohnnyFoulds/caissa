"""
tests/unit/fritz/test_qss_parser_snapshot.py — QSS pre-parser snapshot tests (T-QPS-01..02).

These tests are xfail stubs until §0.2b (the pre-parser hardening) is implemented.
Once §0.2b lands, T-QPS-01 snapshots the parsed {key_gen: colour} dict for all
shipped .qss/.colors pairs, and T-QPS-02 asserts the diff is additions only.

:spec: §0.2b (implementation_plan.md)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.xfail(strict=True, reason="Requires §0.2b pre-parser hardening (chore/fritz-foundations Phase 0.2b)")
def test_qss_parser_snapshot_matches_baseline():
    """T-QPS-01: the parsed {key_gen: colour} dict for all shipped .qss/.colors pairs matches a committed snapshot."""
    pytest.fail("not yet implemented — requires §0.2b pre-parser hardening")


@pytest.mark.xfail(strict=True, reason="Requires §0.2b pre-parser hardening (chore/fritz-foundations Phase 0.2b)")
def test_qss_parser_snapshot_diff_is_additions_only():
    """T-QPS-02: after the §0.2b edits the snapshot diff contains additions only (no key changes or removals)."""
    pytest.fail("not yet implemented — requires §0.2b pre-parser hardening")
