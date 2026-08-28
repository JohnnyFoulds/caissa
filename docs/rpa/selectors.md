# Selectors

A **Selector** is a descriptor that identifies a UI element without holding a live reference to it.
A **Target** wraps a Selector with optional anchor, direction, distance, and timeout.

---

## Why selectors instead of pointers

UiPath's central insight: widget pointers are fragile across modal dialogs, game resets, and
any operation that rebuilds the widget tree.  `ElementRef` carries the selector that found the
element, never the Qt pointer.  `QtDriver` re-resolves the selector at actuation time and
validates with `shiboken6.isValid`.  This eliminates the largest class of Qt use-after-free
bugs documented in `QtDriver.force_cancel()`.

---

## Selector fields

```python
Selector(
    tier        = "auto",        # "auto" | "object" | "image" | "ocr"
    cls         = None,          # Qt widget class, e.g. "QPushButton"
    object_name = None,          # Qt objectName property — most reliable discriminator
    text        = None,          # Label or display text (substring unless text_exact=True)
    text_exact  = False,         # If True, only exact text matches
    role        = None,          # Accessibility role string
    scope       = "all",         # "all" | "toolbar"
    index       = 0,             # 0-based positional tiebreaker among equal-confidence matches
    image       = None,          # Template name from the manifest (image tier only)
    threshold   = 0.50,          # Minimum confidence; default 0.50 admits class-only (0.60)
)
```

At least one **discriminating field** (`object_name`, `text`, `cls`, `image`, `role`) must be
set.  Construction raises `SelectorError` otherwise.

### Object-tier confidence table

| Match type | Confidence |
|---|---|
| Exact `object_name` | 1.00 |
| Exact `text` | 0.95 |
| Substring `text` | 0.80 |
| Class-only (`cls`) | 0.60 |

The default threshold (0.50) admits all four tiers.  Raise it to 0.80 when you only want
`object_name` or exact-text matches.

---

## Tier resolution

`tier="auto"` tries **object → image → OCR** in that order.  The first tier that finds a
candidate at ≥ threshold wins.

| Tier | Phase available | Notes |
|---|---|---|
| `"object"` | Phase 3+ | Qt widget tree; fast, exact, works headless |
| `"image"` | Phase 7+ | Template matching via `cv2.matchTemplate` |
| `"ocr"` | Phase 7+ | Tesseract phrase location |

When the image or OCR tier wins on `"auto"`, a `WARNING` is logged — this means the object
selector is broken and should be fixed.  Do not rely on CV tiers for stable tests.

---

## Wire forms

### JSON (primary)

```json
{"tier": "auto", "cls": "QPushButton", "text": "Play"}
```

Used by `_dispatch()` and the CLI — no escaping problems.  Pass to `Selector.from_json()`.

### Compact string (debugging)

```
obj:object_name=play_btn
obj:cls=QLineEdit,text=Player%20name
auto:cls=QPushButton,text=OK
```

Format: `<tier_abbr>:<key>=<pct-encoded-value>[,<key>=<value>]`

Tier abbreviations: `obj` = object, `img` = image, `auto` = auto, `ocr` = ocr.

Parse with `Selector.from_compact(s)`.  Values are percent-encoded (standard URL encoding).

---

## Target fields

```python
Target(
    selector    = Selector(...),     # Required
    anchor      = None,              # Optional Selector that acts as spatial reference point
    direction   = None,              # "right-of" | "left-of" | "above" | "below"
    max_distance= None,              # Max logical-pixel distance between centres; None = unlimited
    timeout_ms  = None,              # Override default resolver timeout; None = use default
)
```

`anchor` and `direction` must be set together; `direction` without `anchor` is ignored.

### Anchor example

Find the `QLineEdit` to the right of the "Player name" label:

```python
Target(
    selector  = Selector(cls="QLineEdit"),
    anchor    = Selector(text="Player name"),
    direction = "right-of",
    max_distance = 200,
)
```

Anchors are resolved by the same object tier before filtering candidates.  If the anchor
cannot be resolved, candidates are returned unfiltered (a warning is emitted).

---

## TargetResolver

```python
from Code.Rpa.Resolve import TargetResolver

resolver = TargetResolver()
ref = resolver.resolve_one(target, snapshot)
```

**`resolve_one(target, snapshot) → ElementRef`**

- Returns the unique best-confidence match.
- Raises `AmbiguousMatchError` if two candidates share the highest confidence.  Use
  `object_name`, `text_exact=True`, or `index` to disambiguate.
- Raises `TargetNotFoundError` if no candidate meets the threshold.
- Raises `VisionUnavailableError` if `tier="image"` or `tier="ocr"` is requested (Phase 7).

**`visible_elements(snapshot) → list[ElementRef]`**

Returns all visible widgets in the snapshot as `ElementRef` objects.  Useful for
exploration and debugging.

---

## Choosing a good selector

Prefer in this order:

1. `object_name` alone — stable across theme changes, text changes, locale changes.
2. `text` + `cls` — stable for labelled buttons that don't change captions.
3. `cls` alone — only when there is exactly one widget of that class visible.
4. Image tier — only when the widget does not appear in the Qt object tree (custom painting).
5. OCR tier — only as a last resort; requires tesseract installed.

Never use a bare `cls` selector when there are multiple widgets of that class visible — this
produces `AmbiguousMatchError`.  Add `text` or `object_name` to discriminate.

---

## Governance rule

Every workflow that uses a non-object tier must pair it with an object-tier assertion where
one is possible.  Activities using CV-only assertions carry the `rpa_cv` marker and are
excluded from the default test run.  A tier-fallback warning in a test run means an object
selector is broken — fix it, do not suppress the warning.
