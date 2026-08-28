"""
bin/Code/Retro/Errors.py — Retro Engine exception hierarchy.

Hierarchy::

    Exception
    └─ CaissaError              (Code.Base.CaissaErrors — repo-wide root)
       └─ RetroError             (Retro domain base)
          ├─ RomError            ROM loading / verification failures
          ├─ RomNotFoundError    ROM file missing from expected path
          ├─ ManifestError       manifest.json parse / schema failures
          ├─ HashMismatchError   sha256 does not match any known-good digest
          ├─ UnsupportedRomError ROM identified but not in the supported manifest
          ├─ PackedBinaryError   binary appears to be packed/compressed
          ├─ CpuError            emulator initialisation or execution fault
          ├─ EmulatorUnavailableError  unicorn not installed; actionable message
          ├─ BridgeError         FEN ↔ board-struct marshalling failure
          ├─ ThinkError          think orchestrator encountered an unrecoverable state
          ├─ OracleError         corpus record/replay failure
          └─ UciError            UCI protocol state-machine error

:spec: feature_spec.md §11, docs/standards/error-handling.md
"""

from Code.Base.CaissaErrors import CaissaError

__all__ = [
    "CaissaError",
    "RetroError",
    "RomError",
    "RomNotFoundError",
    "ManifestError",
    "HashMismatchError",
    "UnsupportedRomError",
    "PackedBinaryError",
    "CpuError",
    "EmulatorUnavailableError",
    "BridgeError",
    "ThinkError",
    "OracleError",
    "UciError",
]


class RetroError(CaissaError):
    """Base class for all errors raised by the Caissa Retro Engine (``Code.Retro``).

    Catch this when you want to handle any Retro failure without caring about
    the specific kind.
    """


class RomError(RetroError):
    """Raised when a ROM file cannot be opened, parsed, or loaded into the emulator."""


class RomNotFoundError(RetroError):
    """Raised when the ROM file does not exist at the expected path.

    :attr path: Filesystem path that was checked.
    """

    def __init__(self, path: str) -> None:
        """Initialise with an actionable message.

        :param path: Filesystem path of the missing ROM.
        """
        super().__init__(
            f"ROM not found at {path!r}. Supply a verified copy and set the path — "
            f"see docs/retro/rom-setup.md."
        )
        self.path = path


class ManifestError(RetroError):
    """Raised when ``Resources/Retro/manifest.json`` is missing, malformed, or fails schema validation."""


class HashMismatchError(RetroError):
    """Raised when the supplied ROM's sha256 digest matches no entry in the manifest.

    :attr path: Path to the rejected file.
    :attr digest: The actual sha256 hex digest of the file.
    """

    def __init__(self, path: str, digest: str) -> None:
        """Initialise with the file path and the actual digest for diagnostics.

        :param path: Filesystem path of the rejected ROM file.
        :param digest: Actual sha256 hex digest of the file.
        """
        super().__init__(
            f"ROM at {path!r} has digest {digest[:16]}… which is not in the Caissa manifest. "
            f"Supply a verified copy — see docs/retro/rom-setup.md."
        )
        self.path = path
        self.digest = digest


class UnsupportedRomError(RetroError):
    """Raised when a ROM is hash-verified but the manifest marks it as unsupported."""


class PackedBinaryError(RetroError):
    """Raised when a ROM appears to be packed or encrypted and cannot be parsed as-is."""


class CpuError(RetroError):
    """Raised when the emulator encounters a fault during initialisation or execution."""


class EmulatorUnavailableError(RetroError):
    """Raised when the ``unicorn`` package is not installed.

    :attr reason: Human-readable message with the exact install command.
    """

    def __init__(self, reason: str = "") -> None:
        """Initialise with an actionable install message.

        :param reason: Optional override; defaults to the standard pip install hint.
        """
        msg = reason or "unicorn is not installed — run: pip install -r requirements-retro.txt"
        super().__init__(msg)
        self.reason = msg


class BridgeError(RetroError):
    """Raised when FEN-to-struct or struct-to-FEN marshalling fails."""


class ThinkError(RetroError):
    """Raised when the think orchestrator encounters an unrecoverable state."""


class OracleError(RetroError):
    """Raised when a corpus record cannot be written or a replay assertion fails."""


class UciError(RetroError):
    """Raised when the UCI protocol state machine receives an unexpected command or state."""
