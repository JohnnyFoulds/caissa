# Caissa — Future Directions

**Status:** Living document — product thinking and roadmap candidates  
**Last updated:** 2026-08-28

---

## 0. Cross-Platform Compatibility

### Current state

Caissa runs on **macOS Apple Silicon only** — not because of any code constraint, but because
the vendored engine binaries in `bin/OS/` are `arm64`-only and the README scoped the initial
release that way deliberately. The Python code itself is fully cross-platform.

### The Windows path is open

Nothing we have built closes it:

- All Caissa additions (modes, themes, RPA layer, config overlays) are pure Python
- PySide6 is cross-platform — Windows, macOS, Linux
- The upstream Windows engine binaries exist in `bin/OS/win32/Engines/` and can be pulled
  from `lukasmonk/lucaschessR6` at any time
- No PyInstaller spec exists yet, but writing one is a packaging task, not a code task

To produce a Windows installer:

```bash
# Pull win32 engines from upstream
git remote add upstream https://github.com/lukasmonk/lucaschessR6
git fetch upstream
git checkout upstream/main -- bin/OS/win32/

# On a Windows machine or GitHub Actions windows-latest runner:
pip install pyinstaller
pyinstaller caissa.spec   # spec file to be written
```

The packaging work is roughly a day: write the `.spec` file, bundle `Resources/`, handle
the `UserData/` path correctly on Windows, produce an NSIS or Inno Setup installer.

### Rules that must not be broken — ever

These are the lines that keep the Windows path open. Violating any of them may not break
macOS immediately but will silently break Windows.

| Rule | Why |
|---|---|
| **No `os.path` hardcoded separators** — always use `os.path.join()` or `pathlib.Path` | Backslash vs forward slash |
| **No hardcoded `/tmp/` paths** — use `tempfile.gettempdir()` | `/tmp` does not exist on Windows |
| **No hardcoded Unix socket paths** — `RemoteControl` already uses a configurable path; keep it that way | Unix domain sockets work on Windows 10+ but the path rules differ |
| **No `os.fork()`, `os.kill()`, `signal.SIGTERM` without a Windows fallback** — use `subprocess` and `psutil` instead | `os.fork` is Unix-only |
| **No `chmod`/`chown` calls without a `hasattr` guard** — these are no-ops or errors on Windows | Permissions model is completely different |
| **No shell=True with Unix-specific syntax** — pipes, `&&`, `>>` are cmd.exe-incompatible | Use `subprocess` with a list of args |
| **Resource paths via `Code.path_resource()` only** — never relative paths, never `__file__`-relative joins | PyInstaller rewrites `__file__`; `path_resource` handles both dev and frozen correctly |
| **No PySide6 imports outside the three-module allowlist** — `Driver.py`, `Vision/Capture.py`, `Service.py` | Already enforced by `test_no_pyside6_import_outside_allowlist`; keeping Qt contained also keeps the headless-test path open on Windows CI |
| **New dependencies go in `requirements.txt` or `requirements-rpa.txt`** — never silently assumed present | PyInstaller must be able to enumerate all imports; hidden imports break the frozen build |
| **No `brew`-installed binary assumptions** — `tesseract`, `ffmpeg`, etc. must be either bundled or gracefully absent | Homebrew does not exist on Windows |

### What to check before any new feature touches system interfaces

Before writing code that touches files, processes, sockets, or system paths, ask:

1. Does this work on Windows without modification?
2. If it calls an external binary, can that binary be bundled in `bin/OS/win32/`?
3. Does `Code.path_resource()` cover the paths, or do I need to add a case?
4. Is the dependency in `requirements.txt`? Will PyInstaller find it?

---

## 1. Getting Known

The engineering is done when the feature works. Getting known requires different work entirely.

### The blocking problem

Nobody can use Caissa today. There is no release, no installer, no download for a non-developer.
Lucas Chess has a Windows installer. Caissa requires cloning a repo and setting up a Python venv.
That is a complete barrier for the chess community, which skews older and non-technical.

This is a packaging gap, not a code gap. The Windows path is fully open — see §0 above.
The Python code runs on Windows without modification; it just has not been packaged yet.

### Minimum viable launch (in order)

1. **A working Windows download** — single `.exe` or `.msi` that just runs. This is the
   prerequisite for everything else. Until this exists, nothing else matters.

2. **A landing page** — one screenshot, one sentence explaining what is different from Lucas
   Chess, a download link. GitHub Pages off this repo is sufficient.

3. **One GIF or short video** — showing the mode switch and the Fritz-style layout. 30 seconds.
   Chess players are visual.

4. **One well-placed post** — `r/chess` or `r/chessbeginners` on Reddit. Not a press release.
   A genuine "I built this, here's what it does differently, try it." The chess software
   community is small enough that one well-received post reaches thousands of potential users.

5. **Lucas Chess's own community** — Lucas Monge's forum and Discord. A respectful post there
   reaches exactly the right people. Lucas Monge himself is approachable; if he thinks it is
   good he might link to it. This is the highest-leverage single action.

### Where chess players actually are

- Reddit: `r/chess` (1M+), `r/chessbeginners` (500K+), `r/chessprogramming`
- Chess.com forums
- Lichess community (more technically inclined)
- YouTube chess channels (contacting a mid-size channel for a feature review)
- National federation newsletters (slower but reaches club players specifically)

---

## 2. The "Much Better at One Thing" Question

The chess community does not need another chess GUI. Arena, ChessBase, Fritz, Lucas Chess,
Banksia, en-croissant, Nibbler — there are already too many. What breaks through is either
*much better at one thing* or *serving an audience the existing tools ignore*.

The candidates below are ranked by estimated differentiation (how clearly better than existing
tools) and feasibility (how buildable on the current Caissa foundation).

---

### 2.1 Structured Learning Progression ★★★★★

**The gap:** Chess.com has badges. Lichess has puzzles. Lucas Chess has training features.
None of them have a *progression model* — a structured path that takes a 1000-rated player
toward 1600 in a principled way, with the software adapting to where they actually are.
Chessable does spaced repetition for openings but it is cloud-only, subscription, and not
integrated with actual games.

**What Caissa could do:** The Coach/Train/Compete mode progression is already the skeleton.
The idea is that the software knows what phase of the game you struggle with, what tactical
patterns you keep missing, and what openings suit your style — and it builds a weekly
practice plan around that. Not a rigid curriculum but an adaptive one, driven by your own
game history.

**Why it would win:** Chess parents buying software for their kids want this. Chess coaches
want something to hand to students. This is the sustainable audience — not the enthusiast who
already has ChessBase, but the improver who doesn't know what to practise next.

**Feasibility:** The mode system is the foundation. The hard part is the recommendation
engine — what to practise next. A simple version (track blunder patterns, generate targeted
puzzles from your own games) is buildable without ML. A better version uses the engine to
annotate your games and extract recurring weaknesses.

---

### 2.2 Longitudinal Weakness Tracking ★★★★☆

**The gap:** After a game, every tool shows you where you blundered. None of them track
*patterns* across hundreds of your games — "you've blundered on back-rank mates 11 times
this month", "you consistently misplay the IQP endgame", "you lose 70% of games where you
castle queenside." Lichess has some of this but it is shallow and cloud-only.

**What Caissa could do:** Keep a local database of annotated games. After each game,
run a lightweight engine analysis pass, tag the blunders by tactical motif (using a
pattern library), and surface the top two or three recurring weaknesses. Show a dashboard:
"Your biggest problem this month is X. Here are three positions from your own games to
study."

**Why it would win:** It is personalised in a way cloud tools are not — because it uses
*your* games, not a generic puzzle set. And it is offline and private, which matters to
some players.

**Feasibility:** The game database and engine annotation are straightforward. The hard part
is the tactical motif classifier — tagging a position as "back-rank mate" vs "discovered
attack" requires either a lookup against known patterns or a small ML model. A coarse version
(blunder, mistake, inaccuracy by centipawn loss, categorised by game phase) is buildable
immediately. Motif tagging is a follow-on.

---

### 2.3 The Offline Chessable ★★★★☆

**The gap:** Chessable is excellent for opening training with spaced repetition, but it
requires internet, a subscription, and trusts a third party with your repertoire. There is
no serious offline alternative.

**What Caissa could do:** A repertoire builder with genuine spaced repetition (SM-2 or
similar), integrated with the engine so lines can be annotated automatically, and exportable
to PGN. The key differentiator over Lucas Chess's existing opening training is the spaced
repetition scheduling — most tools just drill the same lines in order.

**Why it would win:** "Chessable but offline and free" is a sentence that lands immediately
with serious club players who are privacy-conscious or travel frequently.

**Feasibility:** Spaced repetition is well-understood algorithmically (SM-2 is simple to
implement). The repertoire data model is a PGN tree with annotation metadata. This is
buildable without any new ML or CV work.

---

### 2.4 Coach Mode with Local LLM Commentary ★★★☆☆

**The gap:** Engine evaluation tells you a move is -0.7. It does not tell you *why* that
matters or what you should be thinking about. Natural language chess commentary exists in
ChessBase and some online tools but requires an internet connection and is not interactive.

**What Caissa could do:** Integrate with a locally-running LLM (Ollama + a quantised model)
to give natural language commentary on positions and moves, calibrated to the player's level.
"You moved your knight to f6 but left your king's rook stuck in the corner — at your level,
getting your pieces out before attacking is the most important habit to build."

**Why it would win:** This does not exist anywhere in a free, offline, integrated form.
The closest is ChatGPT with a FEN pasted in — which is clunky and cloud-dependent.

**Feasibility:** Ollama integration is straightforward (local HTTP API). The hard part is
prompt engineering — getting a small model (7B–13B) to produce useful chess commentary
without hallucinating illegal moves or wrong evaluations. The engine supplies the ground
truth; the LLM supplies the explanation. Keeping those roles cleanly separated is the design
challenge.

**Risk:** LLM commentary quality on small local models is variable. This could easily
produce output that sounds plausible but is wrong, which would be worse than no commentary.
Needs careful evaluation before shipping.

---

### 2.5 The "Dead Simple" Experience ★★★☆☆

**The gap:** Starting a game in Lucas Chess requires navigating menus and popups. Chess.com
has so much gamification and notification noise that many serious players find it distracting.
There is no chess tool that prioritises *reduction of friction* — opening the app and being
in a game in under three seconds, with nothing on screen that is not the board.

**What Caissa could do:** The Fritz one-screen layout is the start of this. The further step
is a "Just Play" mode that is genuinely just a board, a clock, and a level slider. No menus,
no stats, no achievement popups. As minimal as a physical board and clock.

**Why it would win:** A specific audience — players who find chess.com overstimulating,
serious players who want a distraction-free tool, people using Caissa as a physical board
substitute. This is less about features and more about *removing* things.

**Feasibility:** Mostly done — the Just Play mode exists. The gap is polish and
intentionality. The current UI still has Lucas Chess's menu bar and chrome. A true
distraction-free mode would hide or remove all of it.

---

### 2.6 Club / Class Management ★★☆☆☆

**The gap:** Chess clubs and school chess programs have no good free tool for managing
multiple students, tracking their progress, assigning homework positions, and running
internal tournaments. Commercial tools exist (chess-results.com for tournaments, various
school platforms) but nothing integrated and offline.

**What Caissa could do:** A "Coach" mode variant that manages a roster of students, lets a
coach assign positions to study, see a dashboard of student progress, and run a round-robin
or Swiss tournament among a group.

**Why it would win:** Every chess club with 10+ juniors has this problem. The person who
runs the club is usually a volunteer with limited technical skill — a simple, self-contained
tool would be genuinely valuable.

**Feasibility:** This requires a multi-user data model, which is a significant architectural
departure. Feasible but not a small task.

---

## 3. Recommended Focus

If forced to pick one thing: **Structured Learning Progression (2.1)** combined with
**Longitudinal Weakness Tracking (2.2)**. They are complementary — weakness tracking feeds
the progression model. Together they answer the question "what should I practise next?" which
is the question every improving player has and no existing free tool answers well.

The Fritz layout (already in progress) is the hook that gets people to download it.
The structured learning mode is the reason they stay.

The Windows installer is the prerequisite for any of this reaching anyone.

---

## 4. What We Are Not Trying to Be

- A replacement for Lichess or Chess.com for online play — they have network effects we
  cannot match
- A replacement for ChessBase for professional opening preparation — that is a different
  market with different willingness to pay
- An engine — Stockfish exists and we use it

Caissa is a **learning and practice environment for the improving offline player**. That
focus should constrain every feature decision.
