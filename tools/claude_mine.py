#!/usr/bin/env python3
"""
claude_mine.py — Mine Claude Code session transcripts for working patterns.

Reads ``~/.claude/history.jsonl``, session ``*.jsonl`` files, and a recovered
corpus directory.  Filters harness noise, tallies short control directives,
classifies substantive prompts into archetypes, and detects plan
approve/amend/reject moves by tracking ``ExitPlanMode`` call + following user
turn pairs.

A **sanitiser** is always active by default: absolute paths, email addresses,
URLs, IP addresses, AWS ARNs and account IDs, long tokens, and a configurable
project-name denylist are redacted.  Pass ``--unsafe`` only when the output
stays strictly local.

Usage::

    # Report from local sessions + history.jsonl only
    python3 tools/claude_mine.py

    # Include a recovered corpus directory
    python3 tools/claude_mine.py --corpus ~/claude-corpus/sessions

    # Disable sanitiser (local use only; output must NOT be committed)
    python3 tools/claude_mine.py --unsafe

    # Show only plan-interaction stats
    python3 tools/claude_mine.py --report plan

    # Print ground-truth verification counts to confirm the tool is correct
    python3 tools/claude_mine.py --verify
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Home directory — used to locate the default sources.
HOME = Path.home()

#: Default path to the Claude history log.
HISTORY_PATH = HOME / ".claude" / "history.jsonl"

#: Default path to the Claude projects directory.
PROJECTS_PATH = HOME / ".claude" / "projects"

#: Noise prefixes that identify harness-injected content, not user text.
NOISE_PREFIXES = (
    "<",
    "This session is being continued",
    "Caveat:",
    "[SYSTEM NOTIFICATION",
)

#: Slash-command prefix — tallied separately, not counted as prompts.
SLASH_PREFIX = "/"

#: Maximum length (chars) for a message to be counted as a "short directive".
SHORT_THRESHOLD = 40

#: Known short directives treated as ground-truth counts for ``--verify``.
GROUND_TRUTH_SESSION = {
    "continue": 49,
    "go": 27,
    "what's next?": 39,
    "yes": 13,
    "open": 14,
}

GROUND_TRUTH_HISTORY = {
    "yes": 46,
    "continue": 19,
    "done": 18,
    "what's next?": 17,
    "do it": 16,
    "go": 13,
    "push": 11,
}

# ---------------------------------------------------------------------------
# Sanitiser
# ---------------------------------------------------------------------------

#: Compiled patterns applied by the sanitiser.
_SANITISE_PATTERNS = [
    # Absolute filesystem paths
    (re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+(?:/[^\s\"'<>]+)?"), "<PATH>"),
    # Email addresses
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "<EMAIL>"),
    # URLs
    (re.compile(r"https?://[^\s\"'<>]+"), "<URL>"),
    # IP addresses (IPv4)
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "<IP>"),
    # AWS ARNs
    (re.compile(r"arn:[a-z0-9\-]+:[a-z0-9\-]*:[a-z0-9\-]*:[0-9]{10,12}:[^\s\"'<>]+"), "<ARN>"),
    # AWS account IDs (standalone 12-digit numbers)
    (re.compile(r"\b[0-9]{12}\b"), "<ACCOUNT_ID>"),
    # Long opaque tokens (base64-ish, ≥40 chars)
    (re.compile(r"[A-Za-z0-9+/=_\-]{40,}"), "<TOKEN>"),
]


def sanitise(text: str, denylist: list[str] | None = None) -> str:
    """
    Redact sensitive content from *text*.

    Applies regex patterns for paths, emails, URLs, IPs, ARNs, account IDs,
    and long tokens.  Also replaces any string in *denylist* with
    ``<REDACTED>``.

    :param text: The raw text to sanitise.
    :param denylist: Optional list of exact strings to redact.
    :returns: Sanitised text with sensitive fragments replaced.
    :rtype: str
    """
    if denylist:
        for term in denylist:
            if term and term in text:
                text = text.replace(term, "<REDACTED>")
    for pattern, replacement in _SANITISE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# JSONL parsing helpers
# ---------------------------------------------------------------------------

def _iter_jsonl(path: Path):
    """
    Yield parsed JSON objects from *path*, tolerating a truncated final line.

    :param path: Path to a ``.jsonl`` file.
    :yields: Parsed dict per non-empty line.
    """
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Tolerate a truncated final line (backup written mid-append)
                    continue
    except OSError:
        pass


def _extract_user_text(content) -> str | None:
    """
    Extract the plain text from a ``message.content`` value.

    Content may be a plain string or a list of blocks with ``type == "text"``.
    Returns ``None`` if no text block is found.

    :param content: The raw ``message.content`` value from the transcript.
    :returns: Concatenated text, or ``None``.
    :rtype: str or None
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        text = " ".join(p for p in parts if p)
        return text if text else None
    return None


def _is_noise(text: str) -> bool:
    """
    Return ``True`` if *text* is harness-injected noise, not a real user prompt.

    :param text: Stripped message text.
    :returns: ``True`` when the message should be dropped.
    :rtype: bool
    """
    for prefix in NOISE_PREFIXES:
        if text.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Core data model
# ---------------------------------------------------------------------------

class PromptRecord:
    """
    A single genuine user-authored prompt.

    :param text: The sanitised prompt text.
    :param source: ``"history"`` or ``"session"``.
    :param project: Project path slug (may be empty).
    :param is_short: ``True`` when ``len(text) <= SHORT_THRESHOLD``.
    :param is_slash: ``True`` when the prompt is a slash command.
    :param after_exit_plan: ``True`` when this prompt immediately follows an
        ``ExitPlanMode`` tool call — used to classify plan interactions.
    """

    __slots__ = ("text", "source", "project", "is_short", "is_slash", "after_exit_plan")

    def __init__(
        self,
        text: str,
        source: str,
        project: str = "",
        is_short: bool = False,
        is_slash: bool = False,
        after_exit_plan: bool = False,
    ) -> None:
        """
        Initialise a :class:`PromptRecord`.

        :param text: The sanitised prompt text.
        :param source: ``"history"`` or ``"session"``.
        :param project: Project path slug.
        :param is_short: Whether the prompt is a short directive.
        :param is_slash: Whether the prompt is a slash command.
        :param after_exit_plan: Whether the prompt follows ``ExitPlanMode``.
        """
        self.text = text
        self.source = source
        self.project = project
        self.is_short = is_short
        self.is_slash = is_slash
        self.after_exit_plan = after_exit_plan


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_history(
    path: Path = HISTORY_PATH,
    sanitise_output: bool = True,
    denylist: list[str] | None = None,
) -> list[PromptRecord]:
    """
    Load prompts from ``history.jsonl``.

    Each line has keys ``display``, ``timestamp``, ``project``, ``sessionId``.
    The ``display`` field is the user's raw prompt text.

    :param path: Path to ``history.jsonl``.
    :param sanitise_output: Whether to run the sanitiser.
    :param denylist: Additional strings to redact.
    :returns: List of :class:`PromptRecord` objects.
    :rtype: list[PromptRecord]
    """
    records: list[PromptRecord] = []
    for obj in _iter_jsonl(path):
        raw = (obj.get("display") or "").strip()
        if not raw or _is_noise(raw):
            continue
        project = (obj.get("project") or "").strip()
        text = sanitise(raw, denylist) if sanitise_output else raw
        is_slash = text.startswith(SLASH_PREFIX)
        is_short = len(text) <= SHORT_THRESHOLD
        records.append(
            PromptRecord(
                text=text,
                source="history",
                project=project,
                is_short=is_short,
                is_slash=is_slash,
            )
        )
    return records


def _session_prompts(
    jsonl_path: Path,
    sanitise_output: bool,
    denylist: list[str] | None,
) -> list[PromptRecord]:
    """
    Extract user prompts from a single session ``*.jsonl`` file.

    Also detects ``ExitPlanMode`` tool calls and marks the first user turn
    that follows as ``after_exit_plan=True`` so plan-interaction analysis
    can identify approve/amend/reject moves.

    :param jsonl_path: Path to the session JSONL file.
    :param sanitise_output: Whether to run the sanitiser.
    :param denylist: Additional strings to redact.
    :returns: List of :class:`PromptRecord` objects from this session.
    :rtype: list[PromptRecord]
    """
    records: list[PromptRecord] = []
    pending_exit_plan = False

    for obj in _iter_jsonl(jsonl_path):
        msg = obj.get("message", {})
        if not isinstance(msg, dict):
            continue

        role = msg.get("role", "")

        # Detect ExitPlanMode assistant calls
        if role == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block.get("name") == "ExitPlanMode"
                    ):
                        pending_exit_plan = True
            continue

        if role not in ("user", "human"):
            continue

        raw = _extract_user_text(msg.get("content", ""))
        if not raw:
            continue
        raw = raw.strip()
        if not raw or _is_noise(raw):
            continue

        text = sanitise(raw, denylist) if sanitise_output else raw
        is_slash = text.startswith(SLASH_PREFIX)
        is_short = len(text) <= SHORT_THRESHOLD

        after = pending_exit_plan
        pending_exit_plan = False  # consumed

        records.append(
            PromptRecord(
                text=text,
                source="session",
                is_short=is_short,
                is_slash=is_slash,
                after_exit_plan=after,
            )
        )

    return records


def load_sessions(
    projects_path: Path = PROJECTS_PATH,
    corpus_path: Path | None = None,
    sanitise_output: bool = True,
    denylist: list[str] | None = None,
) -> list[PromptRecord]:
    """
    Load prompts from all session ``*.jsonl`` files.

    Scans *projects_path* for top-level ``*.jsonl`` files (session roots) and
    optionally a de-duplicated *corpus_path* directory.

    :param projects_path: Path to ``~/.claude/projects/``.
    :param corpus_path: Optional path to a de-duplicated session corpus
        (e.g. ``~/claude-corpus/sessions/``).
    :param sanitise_output: Whether to run the sanitiser.
    :param denylist: Additional strings to redact.
    :returns: List of :class:`PromptRecord` objects.
    :rtype: list[PromptRecord]
    """
    records: list[PromptRecord] = []
    seen: set[str] = set()

    def _scan(base: Path, max_depth: int = 2) -> None:
        if not base.exists():
            return
        for p in base.rglob("*.jsonl"):
            rel_depth = len(p.relative_to(base).parts)
            if rel_depth > max_depth:
                continue
            uid = p.name
            if uid in seen:
                continue
            seen.add(uid)
            records.extend(
                _session_prompts(p, sanitise_output, denylist)
            )

    _scan(projects_path)
    if corpus_path:
        _scan(corpus_path, max_depth=4)

    return records


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def short_directive_counts(records: list[PromptRecord]) -> collections.Counter:
    """
    Count occurrences of short (``<= SHORT_THRESHOLD`` chars) non-slash directives.

    :param records: The prompt records to analyse.
    :returns: Counter keyed by lowercased prompt text.
    :rtype: collections.Counter
    """
    counter: collections.Counter = collections.Counter()
    for r in records:
        if r.is_short and not r.is_slash:
            counter[r.text.lower()] += 1
    return counter


def plan_interaction_stats(records: list[PromptRecord]) -> dict:
    """
    Compute plan approval / amendment / rejection statistics.

    Looks at prompts where ``after_exit_plan`` is ``True``.  A prompt is
    classified as:

    - **silent_approve**: the record exists but is very short and neutral
      (``y``, ``yes``, single bare verb like ``go``/``continue``/``do it``).
    - **text_response**: longer or non-trivial reply — encodes an amendment,
      rejection, or question.

    Note: truly *silent* approvals (no user turn at all) cannot be detected
    from the transcript; this function only counts *text* responses and infers
    the silent-approval rate from the total ``ExitPlanMode`` count.

    :param records: The prompt records to analyse.
    :returns: Dict with keys ``total_exit_plan``, ``text_responses``,
        ``silent_approvals_lower_bound``, ``text_sample`` (list of sanitised
        text snippets).
    :rtype: dict
    """
    APPROVAL_TOKENS = frozenset({
        "y", "yes", "ok", "okay", "go", "do it", "begin", "proceed",
        "implement", "run", "continue", "do that", "all", "done",
    })

    total = 0
    text_responses: list[str] = []

    # Count how many ExitPlanMode calls produced any subsequent user turn
    for r in records:
        if not r.after_exit_plan:
            continue
        total += 1
        if r.is_slash:
            continue
        lower = r.text.lower().strip()
        if lower not in APPROVAL_TOKENS and len(r.text) > 12:
            text_responses.append(r.text[:200])

    return {
        "total_exit_plan_turns_with_response": total,
        "text_response_count": len(text_responses),
        "text_sample": text_responses[:10],
    }


def archetype_counts(records: list[PromptRecord]) -> dict[str, int]:
    """
    Classify substantive (non-short, non-slash) prompts into loose archetypes.

    Archetypes are detected by keyword presence; a prompt can match multiple.

    :param records: The prompt records to analyse.
    :returns: Dict of archetype label → count.
    :rtype: dict[str, int]
    """
    ARCHETYPES = {
        "document_integrity_review": [
            r"review.*plan", r"make sure.*logical", r"internally consistent",
            r"gaps and ambiguities",
        ],
        "adversarial_review": [
            r"adversarial", r"read.*as.*attacker", r"hostile.*expert",
            r"critically.*as",
        ],
        "claim_verification": [
            r"verify.*against.*code", r"verify.*branch", r"check.*finding",
            r"each.*finding.*individually",
        ],
        "deep_research": [
            r"deep research", r"academic research", r"full rigour", r"citations",
        ],
        "repo_close_out": [
            r"committed.*pushed", r"all.*merged", r"leftover branches",
            r"everything.*checked in",
        ],
        "process_conformance": [
            r"still following.*process", r"sdd.*tdd", r"definition of done",
            r"our process",
        ],
        "self_verify": [
            r"instrument.*everything", r"take.*screenshot", r"drive.*yourself",
            r"exhaust.*verification",
        ],
        "reproducibility": [
            r"reproducible", r"re.?run", r"script.*gather", r"process.*reproducible",
        ],
        "orientation_sitrep": [
            r"sitrep", r"what are we.*working on", r"where are we", r"orientate",
        ],
        "viability_interrogation": [
            r"would.*want to use", r"actually want", r"waste.*time.*tokens",
            r"massive success",
        ],
    }

    import re as _re
    counts: dict[str, int] = {k: 0 for k in ARCHETYPES}

    for r in records:
        if r.is_short or r.is_slash:
            continue
        low = r.text.lower()
        for label, patterns in ARCHETYPES.items():
            if any(_re.search(pat, low) for pat in patterns):
                counts[label] += 1

    return counts


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def print_short_directives(records: list[PromptRecord], top_n: int = 30) -> None:
    """
    Print the top short directive counts to stdout.

    :param records: Prompt records to analyse.
    :param top_n: Number of top entries to display.
    """
    counts = short_directive_counts(records)
    print(f"\n=== Top {top_n} short directives (≤{SHORT_THRESHOLD} chars) ===")
    for text, n in counts.most_common(top_n):
        print(f"  {n:5d}  {text!r}")


def print_plan_stats(records: list[PromptRecord]) -> None:
    """
    Print plan interaction statistics to stdout.

    :param records: Prompt records to analyse.
    """
    stats = plan_interaction_stats(records)
    print("\n=== Plan interaction stats ===")
    print(f"  ExitPlanMode turns with any user response : {stats['total_exit_plan_turns_with_response']}")
    print(f"  Of those, substantive text responses       : {stats['text_response_count']}")
    if stats["text_sample"]:
        print("  Sample text responses (first 10):")
        for s in stats["text_sample"]:
            print(f"    • {s[:120]}")


def print_archetypes(records: list[PromptRecord]) -> None:
    """
    Print archetype classification counts to stdout.

    :param records: Prompt records to analyse.
    """
    counts = archetype_counts(records)
    print("\n=== Prompt archetypes (substantive prompts only) ===")
    for label, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n:
            print(f"  {n:5d}  {label}")


def print_verification(
    history_records: list[PromptRecord],
    session_records: list[PromptRecord],
) -> None:
    """
    Print ground-truth comparison for verification.

    Reports the observed count for each known ground-truth directive and marks
    it as PASS (within ±20%) or FAIL.

    :param history_records: Records loaded from ``history.jsonl``.
    :param session_records: Records loaded from session files.
    """
    print("\n=== Verification against ground-truth counts ===")

    def _check(counter, truth, label):
        print(f"  {label}:")
        for key, expected in sorted(truth.items(), key=lambda kv: -kv[1]):
            observed = counter[key.lower()]
            margin = max(1, int(expected * 0.20))
            status = "PASS" if abs(observed - expected) <= margin else "WARN"
            print(f"    {status}  {key!r:25s}  expected≈{expected}  observed={observed}")

    hist_counts = short_directive_counts(history_records)
    sess_counts = short_directive_counts(session_records)

    _check(hist_counts, GROUND_TRUTH_HISTORY, "history.jsonl")
    _check(sess_counts, GROUND_TRUTH_SESSION, "session files")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the CLI.

    :returns: Configured :class:`argparse.ArgumentParser`.
    :rtype: argparse.ArgumentParser
    """
    p = argparse.ArgumentParser(
        description="Mine Claude Code transcripts for working patterns.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--corpus",
        metavar="DIR",
        help="Path to a de-duplicated session corpus (e.g. ~/claude-corpus/sessions/).",
    )
    p.add_argument(
        "--history",
        metavar="FILE",
        default=str(HISTORY_PATH),
        help=f"Path to history.jsonl (default: {HISTORY_PATH}).",
    )
    p.add_argument(
        "--projects",
        metavar="DIR",
        default=str(PROJECTS_PATH),
        help=f"Path to ~/.claude/projects/ (default: {PROJECTS_PATH}).",
    )
    p.add_argument(
        "--unsafe",
        action="store_true",
        help="Disable sanitiser. Output must NOT be committed to a public repo.",
    )
    p.add_argument(
        "--denylist",
        metavar="TERM",
        nargs="*",
        default=[],
        help="Extra strings to redact in addition to the default patterns.",
    )
    p.add_argument(
        "--report",
        choices=["all", "short", "plan", "archetypes"],
        default="all",
        help="Which report section to print (default: all).",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="Check observed counts against known ground-truth values.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for the ``claude_mine.py`` CLI.

    :param argv: Argument vector; defaults to ``sys.argv[1:]``.
    :returns: Exit code (0 = success).
    :rtype: int
    """
    args = _build_parser().parse_args(argv)

    sanitise_output = not args.unsafe
    denylist = args.denylist or []

    corpus_path = Path(args.corpus).expanduser() if args.corpus else None

    print("Loading history.jsonl ...", file=sys.stderr)
    history_records = load_history(
        path=Path(args.history).expanduser(),
        sanitise_output=sanitise_output,
        denylist=denylist,
    )

    print("Loading session files ...", file=sys.stderr)
    session_records = load_sessions(
        projects_path=Path(args.projects).expanduser(),
        corpus_path=corpus_path,
        sanitise_output=sanitise_output,
        denylist=denylist,
    )

    all_records = history_records + session_records

    print(
        f"Loaded {len(history_records)} history prompts, "
        f"{len(session_records)} session prompts.",
        file=sys.stderr,
    )

    if args.verify:
        print_verification(history_records, session_records)
        return 0

    if args.report in ("all", "short"):
        print_short_directives(all_records)

    if args.report in ("all", "plan"):
        print_plan_stats(session_records)

    if args.report in ("all", "archetypes"):
        print_archetypes(all_records)

    return 0


if __name__ == "__main__":
    sys.exit(main())
