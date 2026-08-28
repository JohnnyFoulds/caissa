# Session Archaeology — Runbook

How to recover and mine your own Claude Code session history.

---

## Backup Architecture

| Component | Details |
|---|---|
| Script | `~/bin/claude-backup.sh` |
| Schedule | launchd `com.johnnyfoulds.claude-backup`, daily **02:00** |
| What it archives | `tar -czf <archive> -C $HOME .claude` — the **entire** `~/.claude` tree with **no excludes** |
| Destination | `gdrive:claude-backups` via rclone (`~/.config/rclone/rclone.conf`, remote `gdrive:`) |
| Logs | stdout → `/tmp/claude-backup.log`, stderr → `/tmp/claude-backup.error.log` |
| Current corpus | 69 daily archives, 2026-06-18 → 2026-08-28, ~18.6 GiB total |

**Operational notes:**
- Three backup dates are **missing** (machine asleep at 02:00): 2026-06-28, 2026-08-17, 2026-08-21.
- Several consecutive dates share the same byte-size range but have **distinct MD5 hashes** — they are not duplicates; daily activity in `history.jsonl` and caches makes them differ.
- There is currently **no retention policy**: archives accumulate indefinitely.
- The backup script tolerates `tar` exit code 1 (files changing mid-archive) — a session being appended at 02:00 may be **truncated mid-line**. Parse recovered JSONL line-by-line and tolerate a bad final line.

---

## Data Layout

```
~/.claude/
├── history.jsonl                          # prompt history across all sessions
├── projects/
│   └── <slug>/
│       ├── <uuid>.jsonl                   # top-level session transcript
│       └── <uuid>/
│           └── subagents/
│               └── agent-<id>.jsonl       # subagent transcript
├── plans/
│   └── <slug>.md                          # plan-mode plan documents
├── settings.json                          # global config (includes cleanupPeriodDays)
└── .last-cleanup                          # mtime of last retention cleanup run
```

### `history.jsonl` schema

```json
{
  "display":   "<the user's raw prompt text>",
  "timestamp": "<ISO-8601>",
  "project":   "/Users/<user>/code/<repo>",
  "sessionId": "<uuid>"
}
```

### Session `*.jsonl` schema

Each line is a JSON object. User turns have `message.role == "user"` and
`message.content` that is either a plain string or a list of blocks:

```json
{"message": {"role": "user",  "content": "please verify session 2-A"}}
{"message": {"role": "user",  "content": [{"type": "text", "text": "…"}]}}
{"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "ExitPlanMode", …}]}}
```

---

## Why Sessions Disappear Locally

Claude Code runs its own retention cleanup on startup. The default `cleanupPeriodDays`
is approximately **30 days**. If the key is absent from `settings.json`, sessions older
than ~30 days are deleted daily.

**To stop deletion:** set `cleanupPeriodDays: 3650` in `~/.claude/settings.json`:

```json
{
  "cleanupPeriodDays": 3650,
  ...existing keys...
}
```

Do **not** restore recovered sessions back into `~/.claude/projects/` — `tar` restores
original mtimes, and the cleanup run would delete them again at the next startup.
Restore into a separate corpus directory (see below).

---

## Corpus Location

**`~/claude-corpus/`** — outside `~/.claude` for two independent reasons:
1. `claude-backup.sh` has no excludes; a corpus inside `~/.claude` would compound into
   every future archive.
2. Restored files would be deleted by the cleanup run (mtime trap, see above).

Structure:
```
~/claude-corpus/
├── raw/
│   └── 2026-08-12/          # extracted JSONL from that archive date
│       └── .claude/projects/…
└── sessions/                # de-duplicated canonical set (largest copy wins)
    └── <uuid>.jsonl
```

---

## Verified Streaming Extraction Commands

Environment: **bsdtar 3.5.3** (macOS). **No GNU tar is required and no `--wildcards` flag
exists on bsdtar** — do not copy GNU recipes.

### List contents of an archive (streams the whole file)

```bash
rclone cat gdrive:claude-backups/claude-backup-2026-08-12.tar.gz \
  | tar -tzf - '.claude/projects/*.jsonl'
```

Save the listing to a file to avoid re-streaming:

```bash
rclone cat gdrive:claude-backups/claude-backup-2026-08-12.tar.gz \
  | tar -tzf - '.claude/projects/*.jsonl' \
  > /tmp/listing-2026-08-12.txt
```

### Extract all session JSONL from one archive

```bash
mkdir -p ~/claude-corpus/raw/2026-08-12
rclone cat gdrive:claude-backups/claude-backup-2026-08-12.tar.gz \
  | tar -xzf - -C ~/claude-corpus/raw/2026-08-12 --include='*/projects/*.jsonl'
```

**Note on `*` crossing `/`:** On bsdtar, `*` matches across path separators, so the
pattern `'*/projects/*.jsonl'` also picks up subagent transcripts at
`…/<uuid>/subagents/agent-<id>.jsonl`. This is the desired behaviour.

### Extract a single session to stdout (verified working)

```bash
rclone cat gdrive:claude-backups/claude-backup-2026-06-18.tar.gz \
  | tar -xzO -f - --include='*/<uuid>.jsonl'
```

### ⚠️ Do not pipe into `head`

`head` closes the pipe early, causing rclone to log a broken-pipe error with a
non-zero exit code. It wastes the entire stream. Capture to a file instead.

---

## Throughput and Cost

Measured throughput: **~372 KB/s** (~3 Mbit/s). Cost is the link, not CPU.

| Archive | Size | Wall clock |
|---|---|---|
| `2026-06-18` | 35.5 MB | ~2 min |
| `2026-08-12` | 420 MB | ~19 min |
| `2026-08-03` | 499 MB | ~22 min |
| Full corpus (69 archives) | 18.6 GiB | ~14 h |

For selective recovery, the archives immediately **before** a size drop hold everything
that drop removed (the backup is a full snapshot, not incremental). Size drops and
their pre-prune archives:

| Drop date | Δ | Archive to stream |
|---|---|---|
| 2026-08-13 | −291 MB | `2026-08-12` |
| 2026-08-04 | −76 MB | `2026-08-03` |
| 2026-07-14 | −21 MB | `2026-07-13` |

---

## Full Recovery Script (Resumable Background Job)

For complete recovery of all 69 archives, run as a background job that skips dates
already extracted:

```bash
#!/usr/bin/env bash
set -euo pipefail
CORPUS=~/claude-corpus/raw
REMOTE=gdrive:claude-backups
DATES=$(rclone ls "$REMOTE" | awk '{print $2}' | grep -oP '\d{4}-\d{2}-\d{2}' | sort -r)

for DATE in $DATES; do
  MARKER="$CORPUS/$DATE/.done"
  if [[ -f "$MARKER" ]]; then
    echo "SKIP $DATE (already extracted)"
    continue
  fi
  mkdir -p "$CORPUS/$DATE"
  echo "Extracting $DATE …"
  rclone cat "$REMOTE/claude-backup-${DATE}.tar.gz" \
    | tar -xzf - -C "$CORPUS/$DATE" --include='*/projects/*.jsonl' \
    || true   # tar exit 1 = partial archive, acceptable
  touch "$MARKER"
  echo "DONE $DATE"
done
```

**Accelerator (optional, not applied by default):** runs of consecutive same-size
archives almost certainly share the same session set. One representative per run
cuts total time significantly but is a heuristic — verify before relying on it.

---

## De-duplication

After extracting multiple archives, consolidate into `~/claude-corpus/sessions/`
keeping the **largest** copy of each session UUID (sessions grow as they run):

```bash
python3 - <<'EOF'
import os, shutil
from pathlib import Path

raw = Path.home() / "claude-corpus" / "raw"
sessions = Path.home() / "claude-corpus" / "sessions"
sessions.mkdir(parents=True, exist_ok=True)

for jsonl in raw.rglob("*.jsonl"):
    dest = sessions / jsonl.name
    if not dest.exists() or jsonl.stat().st_size > dest.stat().st_size:
        shutil.copy2(str(jsonl), str(dest))
        print(f"kept {jsonl.name} ({jsonl.stat().st_size} bytes)")

print(f"Total unique sessions: {sum(1 for _ in sessions.glob('*.jsonl'))}")
EOF
```

---

## Mining the Corpus

Use `tools/claude_mine.py` to extract patterns from the corpus:

```bash
# From local sessions + history only (fast)
python3 tools/claude_mine.py

# Include the recovered corpus
python3 tools/claude_mine.py --corpus ~/claude-corpus/sessions

# Verify counts against known ground truth
python3 tools/claude_mine.py --verify

# Short-directive report only
python3 tools/claude_mine.py --report short

# Plan-interaction stats only
python3 tools/claude_mine.py --report plan
```

The sanitiser is always active by default. Output is safe to include in public
documentation. Pass `--unsafe` only for local analysis; never commit that output.

---

## OAuth Token

rclone's access token typically expires within an hour; a refresh token is present
and rclone handles refreshes automatically. A 14 h full-recovery job will cross
several refresh cycles — this is normal and requires no intervention.

---

## Known Gaps

- **No retention policy** on the backup: archives accumulate indefinitely. Consider
  a pruning policy (e.g. keep daily for 90 days, weekly thereafter).
- **No excludes** in the backup script: `~/.claude/plugins/`, `~/.claude/cache/`, and
  any corpus placed inside `~/.claude` would be tarred into every archive.
- **Missing dates**: 2026-06-28, 2026-08-17, 2026-08-21 have no archive.
