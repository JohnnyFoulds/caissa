# UiPath Ontology ↔ Caissa RPA Mapping

**Audience:** Someone coming from UiPath who wants to understand Caissa's RPA layer,
or a Caissa developer who wants to understand the UiPath vocabulary.

---

## Core Concepts

| UiPath term | Caissa equivalent | Notes |
|---|---|---|
| **Activity** | `Activity` | The fundamental unit. Same concept: precondition → execute → postcondition. |
| **Workflow / Sequence** | `Workflow` (Python function), `Sequence` frame | Caissa workflows are plain Python functions returning activity lists. No XAML. |
| **Robot** | `Runner` | The execution engine that enforces the closed loop. |
| **Orchestrator job** | `rpa_run` → `run_id` | Start a run; poll `rpa_status`. Same job+status model. |
| **Exception Handling** | `DECIDE_RECOVERY`, `COMPENSATE`, `UNWIND` | Equivalent to Try/Catch/Finally in a Workflow diagram. |
| **Retry Scope** | `RetryScope` frame | Same semantics: re-enter body up to N times on failure. |
| **State Machine Workflow** | `AppState` + `StateGraph` | Caissa models the app as a state graph; the runner navigates it automatically. |
| **Selector** | `Selector` | Identifies a UI element. Caissa has three tiers (object/image/OCR); UiPath has similar. |
| **Anchor** | `Target.anchor` | "Relative To" in UiPath CV scope — locate by spatial relationship. |
| **UI Scope** | `scope` field on `Selector` | Restricts search to a part of the UI (e.g. `"toolbar"`, `"dialog"`). |

---

## CV / Computer Vision Activities

| UiPath CV Activity | Caissa equivalent | Notes |
|---|---|---|
| `CV Screen Scope` | `Selector(tier="cv")` | Caissa CV is a tier on any selector, not a separate scope. |
| `CV Click` | `Click(Target(Selector(tier="image", ...)))` | CV-tier target; same closed loop. |
| `CV Get Text` | `GetText(Target(Selector(tier="ocr", ...)))` | OCR tier. |
| `CV Element Exists` | `ElementExists(Target(Selector(tier="auto", ...)))` | Auto-tier tries object first, falls back to CV. |
| `CV Type Into` | `TypeInto(Target(Selector(tier="image", ...)))` | |
| `CV Take Screenshot` | `TakeScreenshot(path)` | |

---

## Execution Model

| UiPath concept | Caissa equivalent |
|---|---|
| Attended robot / foreground | The main use case — running against a live Caissa process |
| Unattended robot / background | `CAISSA_TEST=1` with `QT_QPA_PLATFORM=offscreen` |
| `Start Job` in Orchestrator | `rpa_run {"workflow":"name"}` |
| `Job Status` polling | `rpa_status {"run_id":"r-..."}` |
| `Stop Job` | `rpa_cancel {"run_id":"r-..."}` |
| Transaction-based architecture | Not applicable — Caissa is a single-user desktop app |

---

## Activity Catalogue (Caissa → UiPath)

| Caissa Activity | UiPath analogue | Description |
|---|---|---|
| `Click(target)` | Click | Click a UI element |
| `TypeInto(target, text)` | Type Into | Type text into a field |
| `SelectItem(target, value)` | Select Item | Select a combo/list value |
| `GetText(target)` → str | Get Text / CV Get Text | Read a field's text |
| `ElementExists(target)` → bool | Element Exists / CV Element Exists | Check if an element is visible |
| `TakeScreenshot(path)` | Take Screenshot | Save the current window as PNG |
| `OpenConfig()` | — | Open Caissa Configuration dialog (domain-specific) |
| `CloseDialog()` | — | Close the topmost modal dialog |
| `SwitchTab(label)` | Click (on tab) | Switch to a named tab in a dialog |
| `Sequence(activities)` | Sequence | Group activities; fail fast if any step fails |
| `RetryScope(body, retries)` | Retry Scope | Retry body up to N times |

---

## When to Use an Activity vs Ad-Hoc Code

Use this decision tree before writing any automation code.

```
Q: Do I need to interact with a running process (click, type, screenshot, window event)?
   → YES → Activity subclass in bin/Code/<Target>/Activities.py
   → NO  → Plain Python function (no RPA needed)

Q: Does the action need to be verified — how do I know it worked?
   → Always: use postcondition + verify_ms
   → Never assume success; always verify with a screenshot check
   → This is identical to UiPath's postcondition on every activity

Q: Does the app need to be in a specific state before this action?
   → Use precondition (same as a UiPath guard/condition)
   → The DosRunner / AmigaRunner handles convergence and retry

Q: Can I write this as a /tmp script instead?
   → NO. /tmp scripts:
     - have no verifiable postcondition
     - are invisible after context compaction
     - cannot be unit-tested without the running application
     - cannot be retried or rewound
   → The question is not "can I" but "will a future session know this worked?"

Q: I need to measure a coordinate or colour threshold. Where do I put it?
   → Immediately into bin/Code/<Target>/BattleChess.py AND into CLAUDE.md.
   → Never in a local variable. Never in /tmp. Never only in memory.
```

**The UiPath parallel:**
In UiPath you do not write ad-hoc VBA inside a Code activity to click a button. You use
`Click`, set the selector, test it in the Test Activity pane, then wire it into the
Sequence. The Activity object IS the documentation — its name, selector, and
postcondition describe exactly what it does and how you know it worked. Follow the same
discipline here.

---

## What Is Intentionally Different

Caissa intentionally diverges from UiPath in a few places:

1. **No XAML.** Workflows are Python. This was a deliberate choice — the Caissa codebase is
   Python, and a Python DSL is more maintainable for this team than an XML dialect.

2. **No agent mode.** Recent UiPath versions add LLM/agentic automation (`Autopilot`). Caissa
   does not — the RPA layer is purely procedural and deterministic.

3. **State-graph convergence.** UiPath generally assumes you write explicit navigation.
   Caissa's `AppState` + `StateGraph` + Dijkstra planner adds automatic convergence — the
   runner figures out how to get to the required state for you.

4. **No Orchestrator.** Caissa has no cloud scheduling. The job+status model is implemented
   locally over the Unix socket.

5. **Object tier is primary.** UiPath's modern CV activities use computer vision as the
   primary mechanism. Caissa prefers widget inspection (the object tier) as the primary
   mechanism, using CV/OCR as a fallback. The governance rule — a non-object tier win emits
   a warning and means the object selector is broken — enforces this.
