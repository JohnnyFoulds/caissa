# Amiga vs DOS: Move Divergences

This document records positions where the Battle Chess Amiga (68k) and DOS (x86)
builds produce different moves.  Divergences are expected because the two ports
have slightly different evaluation code and may have different game-loop timing.

## Status

No divergences have been captured yet.  The DOS target is at Phase 9 (scaffolding
only).  Ground-truth DOS corpus capture requires:
1. The Battle Chess DOS binary (user-supplied, SHA256 to be added to manifest.json).
2. DOSBox-X or equivalent running the binary headlessly.
3. A capture script recording `(fen, level, uci_move)` tuples for every position
   in the Amiga ground-truth corpus.

## Format

Once divergences are found, they are documented as:

```
### FEN: <fen>
- **Amiga move**: <uci>
- **DOS move**: <uci>
- **Notes**: <why — different eval? timing difference? known port bug?>
```

## Known Divergences

*(none yet)*
