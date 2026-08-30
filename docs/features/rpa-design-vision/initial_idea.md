# RPA Design Vision — Initial Idea

**Status:** FROZEN — scope locked 2026-08-30
**Frozen by:** Johannes Foulds
**Next artefact:** [feature_spec.md](feature_spec.md)

---

## Problem Statement

`tools/design/` renders Fritz mockups offscreen and scores them numerically, but the
judgement step is still a human looking at a picture. Every measurement is hard-coded to
one widget at one width: `ribbon_report.py:187` scans `range(10, 80)` for the rule row,
`:235` assumes the File tab lives in `x ∈ [2, 70)`. It cannot answer "is the gap between
File and Home the same as the others" because it has no concept of an element, only of
hard-coded boxes.

And there is no agent-facing surface. When a UI complaint arrives ("the tabs look like
disconnected components"), the agent's default is to grep the stylesheet — which produced
three separate attempts to fix `QTabWidget::pane`, a rule that matches no widget in the
application.

This feature closes that loop in two halves:

1. **Eyes** — cv2 + tesseract extract a symbolic `Scene` description (fills, ink spans,
   seams, corners, peer clusters) that is complete enough for Claude to diagnose and fix
   a UI defect without a cloud call to interpret an image.
2. **Surface** — a `.claude/skills/` trigger + `tools/caissa-eyes` CLI so Claude reaches
   for the measurement automatically, before reading any source file.

---

## Business Requirements

| ID | Requirement |
| --- | --- |
| BR-1 | Enable Claude to measure and diagnose Caissa UI defects locally, without uploading images to a cloud vision model. |
| BR-2 | Cover use case (a): design-against-a-reference — the Fritz sign-off flow, producing a machine-readable verdict rather than a human-read PNG. |
| BR-3 | Cover use case (b): interactive repair — given a pasted screenshot or a verbal description, locate the element, name the governing code, and verify the fix landed. |
| BR-4 | Implement as RPA Activities following the existing RPA standards and the 5-step closed loop, so the measurement layer is testable and composable. |
| BR-5 | Provide an agent-facing surface (skill + CLI) so the measurement loop fires automatically on UI complaints, without the agent having to remember a tool name. |

---

## Confirmed Decisions (at scope-lock)

| Decision | Choice | Reason |
| --- | --- | --- |
| Output forms | All three: JSON + crops, annotated PNG, HTML sheet | Different consumers need different views; the annotated PNG is evidence for the user, not an assertion |
| Match target | Both reference image and live app, live preferred | Reference-only would miss runtime state; live-only would miss the Fritz sign-off flow |
| Packaging | New feature directory (`docs/features/rpa-design-vision/`) + RPA Activities in `bin/Code/Rpa/Vision/` | Follows the existing feature-directory convention and RPA module layout |
| Tool surface | Skill (`.claude/skills/design-eyes/SKILL.md`) + CLI (`tools/caissa-eyes`) via Bash | Keeps the single implementation in the CLI; the skill is a trigger, not a separate code path |
| Skill scope | Diagnose + verify only — never edits | Error rate from wrong mechanisms is high enough that an editing surface would be harmful; the skill names the file and line and stops |

---

## Open Questions (at scope-lock)

None. All decisions were made before spec-writing began and are recorded above and in
`design-record.md`. The seven corrections in the design-record (especially the three
failed edits to `QTabWidget::pane`) are the evidence behind the "diagnose + verify only"
scope decision.
