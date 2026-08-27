"""
CaissaClient — socket wrapper around RemoteControl.py for UI integration tests.

Connects to the running Caissa process via /tmp/caissa-control.sock and provides
typed assertion helpers used by the pytest test suite in tests/ui/.
"""

import json
import socket
import time

SOCKET_PATH = "/tmp/caissa-control.sock"
_DEFAULT_TIMEOUT = 10.0


class CaissaClientError(Exception):
    """Raised when the RemoteControl server returns an error response."""


class CaissaClient:
    """
    Client for the Caissa RemoteControl Unix socket server.

    :param socket_path: Path to the Unix domain socket.
    :param default_timeout: Default per-command timeout in seconds.
    """

    def __init__(self, socket_path: str = SOCKET_PATH, default_timeout: float = _DEFAULT_TIMEOUT):
        self.socket_path = socket_path
        self.default_timeout = default_timeout

    # ------------------------------------------------------------------
    # Core transport
    # ------------------------------------------------------------------

    def send(self, cmd: str, timeout: float | None = None) -> dict:
        """
        Send a single newline-terminated command and return the parsed JSON response.

        :param cmd:     Command string, e.g. ``"ping"`` or ``"click_toolbar Options"``.
        :param timeout: Socket timeout in seconds.  Uses ``default_timeout`` if omitted.
        :returns:       Parsed response dict.
        :raises CaissaClientError: If the response contains an ``"error"`` key.
        :raises socket.timeout:    If no response arrives within ``timeout`` seconds.
        :raises FileNotFoundError: If the socket file does not exist.
        """
        t = timeout if timeout is not None else self.default_timeout
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(t)
        s.connect(self.socket_path)
        try:
            s.sendall((cmd + "\n").encode())
            data = b""
            while b"\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
        finally:
            s.close()
        result = json.loads(data.decode().strip())
        if "error" in result:
            raise CaissaClientError(f"Remote error for {cmd!r}: {result['error']}")
        return result

    def wait_ready(self, timeout: float = 30.0, poll_interval: float = 0.5) -> None:
        """
        Poll the socket until the app responds to ``ping`` or ``timeout`` expires.

        :param timeout:       Maximum time to wait in seconds.
        :param poll_interval: Seconds between attempts.
        :raises TimeoutError: If the app does not become ready in time.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.send("ping", timeout=2.0)
                return
            except (FileNotFoundError, ConnectionRefusedError, socket.timeout):
                time.sleep(poll_interval)
        raise TimeoutError(f"Caissa did not become ready within {timeout}s")

    # ------------------------------------------------------------------
    # High-level commands
    # ------------------------------------------------------------------

    def info(self) -> dict:
        """Return current theme/style/icons config."""
        return self.send("info")

    def screenshot(self, path: str = "/tmp/caissa-screenshot.png") -> str:
        """
        Grab the main window and save to ``path``.

        :returns: The saved file path.
        """
        return self.send(f"screenshot {path}")["path"]

    def click_toolbar(self, text: str) -> dict:
        """
        Trigger a toolbar button by action text (partial, case-insensitive match).

        :param text: Substring of the action text, e.g. ``"Options"`` or ``"Config"``.
        """
        return self.send(f"click_toolbar {text}")

    def click_tab(self, text: str) -> dict:
        """
        Switch a QTabWidget to the tab whose label contains ``text``.

        :param text: Substring of the tab label.
        """
        return self.send(f"click_tab {text}")

    def combo_select(self, query: str, value: str) -> dict:
        """
        Set a QComboBox (found by ``query``) to the item matching ``value``.

        :param query: Widget search query (text / objectName / class substring).
        :param value: Item text to select (partial, case-insensitive).
        """
        return self.send(f"combo_select {query} {value}")

    def find_widget(self, query: str) -> dict:
        """
        Return info for the first visible widget matching ``query``.

        :raises CaissaClientError: If no widget matches.
        """
        return self.send(f"find_widget {query}")

    def dialog_info(self) -> dict:
        """
        Return the widget tree of the topmost modal dialog.

        :raises CaissaClientError: If no modal dialog is open.
        """
        return self.send("dialog_info")

    def dialog_accept(self) -> dict:
        """Click OK / Accept on the topmost modal dialog."""
        return self.send("dialog_accept")

    def dialog_cancel(self) -> dict:
        """Click Cancel on the topmost modal dialog."""
        return self.send("dialog_cancel")

    def set_field(self, query: str, value: str) -> dict:
        """
        Set the text of a QLineEdit / QSpinBox matching ``query``.

        :param query: Widget search query.
        :param value: New value string.
        """
        return self.send(f"set_field {query} {value}")

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def _dialog_texts(self) -> list[str]:
        """Return a flat list of all text values from the topmost dialog's widgets."""
        info = self.dialog_info()
        texts = [info.get("title", "")]
        for w in info.get("widgets", []):
            t = w.get("text", "")
            if t:
                texts.append(t)
            items = w.get("items", [])
            texts.extend(items)
        return texts

    def _dialog_tab_labels(self) -> list[str]:
        """Return a flat list of tab labels from all QTabWidgets in the dialog."""
        info = self.dialog_info()
        labels = []
        for w in info.get("widgets", []):
            if w.get("class") == "QTabBar":
                # QTabBar items are listed as text of child widgets — look for tab texts
                # in items list if present
                pass
        # Fall back: use click_tab to test tab existence via try/except
        return labels

    def assert_dialog_field(self, label: str) -> None:
        """
        Assert that a field with the given label text is present in the topmost dialog.

        :param label: Exact or partial label text to search for (case-insensitive).
        :raises AssertionError: If no matching label is found.
        """
        texts = self._dialog_texts()
        label_lower = label.lower()
        matched = any(label_lower in t.lower() for t in texts if t)
        assert matched, (
            f"Expected dialog field {label!r} but it was not found.\n"
            f"Visible texts: {[t for t in texts if t]}"
        )

    def assert_dialog_field_absent(self, label: str) -> None:
        """
        Assert that no field with the given label text is present in the topmost dialog.

        :param label: Text that must not appear (case-insensitive).
        :raises AssertionError: If the label IS found.
        """
        texts = self._dialog_texts()
        label_lower = label.lower()
        matched = any(label_lower in t.lower() for t in texts if t)
        assert not matched, (
            f"Expected dialog field {label!r} to be absent but it was found.\n"
            f"Visible texts: {[t for t in texts if t]}"
        )

    def assert_tab_exists(self, label: str) -> None:
        """
        Assert that a tab with the given label exists in the topmost dialog.

        Attempts to click the tab; if that succeeds the tab exists.

        :param label: Exact or partial tab label.
        :raises AssertionError: If the tab is not found.
        """
        try:
            self.click_tab(label)
        except CaissaClientError as exc:
            raise AssertionError(
                f"Expected tab {label!r} but it was not found: {exc}"
            ) from exc

    def assert_tab_absent(self, label: str) -> None:
        """
        Assert that no tab with the given label exists in the topmost dialog.

        :param label: Label that must not be present.
        :raises AssertionError: If the tab IS found.
        """
        try:
            self.click_tab(label)
            raise AssertionError(
                f"Expected tab {label!r} to be absent but it was found."
            )
        except CaissaClientError:
            pass  # expected — tab not found
