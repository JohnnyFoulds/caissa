"""
In-process remote control server for Caissa — Unix socket, Qt-safe.

Commands (newline-terminated, sent to /tmp/caissa-control.sock):
  ping                              → {"ok": true}
  info                              → current theme/style/icons config
  themes                            → list of available theme names
  theme <name>                      → apply a Caissa theme atomically
  screenshot [/path/file.png]       → grab main window, save PNG, return path
  menu <key>                        → trigger an OptionsMenu action by key
  action <key>                      → invoke procesador.run_action(key)
  toolbar_info                      → current toolbar button list + sizes

  list_windows                      → all top-level windows: class, title, visible, geometry
  dump_ui [depth]                   → JSON tree of all visible widgets (default depth 3)
  find_widget <query>               → first visible widget matching text/objectName/class
  click_widget <query>              → click a visible widget by text/objectName
  click_toolbar <text>              → click a main toolbar button by action text
  click_tab <text>                  → click a QTabWidget tab by label
  set_field <query> <value>         → set text on QLineEdit/QTextEdit matching query
  combo_select <query> <value>      → set QComboBox to item matching value
  dialog_info                       → inspect topmost modal dialog
  dialog_accept                     → accept/OK the topmost modal dialog
  dialog_cancel                     → cancel/close the topmost modal dialog

  startgame [engine=X] [depth=N] [side=white|black]
                                    → start a game vs engine, bypassing the dialog
  make_move <uci>                   → inject a player move (e.g. e2e4, e7e8q)
  game_info                         → current game state: fen, moves, turn, toolbar

  set_config <key> <value>          → set one configuration attribute (bool/int/str) + save
  open_config                       → open General Configuration dialog (async)

All responses are JSON + newline.
"""

import json
import logging
import os
import queue
import socket
import threading

from PySide6 import QtCore, QtWidgets

SOCKET_PATH = "/tmp/caissa-control.sock"

logger = logging.getLogger(__name__)

_FAULT_LOG = "/tmp/caissa_faulthandler.log"


def _enable_faulthandler():
    # Kept — genuinely valuable given the crash history documented in
    # QtDriver.force_cancel().  Gated on CAISSA_RPA_FAULTHANDLER=1 so it
    # does not interfere with normal operation or produce leftover log files.
    if not os.environ.get("CAISSA_RPA_FAULTHANDLER"):
        return
    try:
        import faulthandler
        _fh = open(_FAULT_LOG, "w")
        faulthandler.enable(file=_fh, all_threads=True)
    except Exception:
        pass


class RemoteControl(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = queue.Queue()
        self._heartbeat_seq = 0
        self._draining = False  # re-entrancy guard

        # Qt driver — all Qt-touching helpers delegate here.
        from Code.Rpa.Driver import QtDriver
        self._qt = QtDriver()

        # RPA service — lazily created on first rpa_* verb (None if CAISSA_RPA=0)
        self._rpa_service = None
        self._rpa_disabled = os.environ.get("CAISSA_RPA", "1") == "0"

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(50)

        self._hb_timer = QtCore.QTimer(self)
        self._hb_timer.timeout.connect(self._heartbeat)
        self._hb_timer.start(200)

        _enable_faulthandler()
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()

    def _rpa(self):
        """Return the lazily-created RpaService instance, or None if disabled.

        Code.Rpa is never imported until an rpa_* verb arrives — zero cost
        for sessions that never use the RPA layer.  CAISSA_RPA=0 disables it.
        """
        if self._rpa_disabled:
            return None
        if self._rpa_service is None:
            from Code.Rpa.Service import RpaService
            self._rpa_service = RpaService(driver=self._qt, _start_pump=False)
            logger.debug("RpaService initialised (pump driven by _drain timer)")
        return self._rpa_service

    def _heartbeat(self):
        self._heartbeat_seq += 1
        if self._heartbeat_seq % 5 == 0:  # every 1s
            import Code
            mgr = getattr(Code.procesador, "manager", None) if Code.procesador else None
            logger.debug("HB %d manager=%s", self._heartbeat_seq,
                         type(mgr).__name__ if mgr else None)

    def _serve(self):
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(SOCKET_PATH)
        srv.listen(8)
        while True:
            try:
                conn, _ = srv.accept()
                threading.Thread(
                    target=self._handle_conn, args=(conn,), daemon=True
                ).start()
            except Exception:
                pass

    def _handle_conn(self, conn):
        cmd = "<unset>"
        try:
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            cmd = data.decode().strip()

            result_holder = [None]
            done = threading.Event()
            self._queue.put((cmd, result_holder, done))
            if done.wait(timeout=15):
                response = result_holder[0]
            else:
                response = {"error": "timeout"}
            try:
                payload = json.dumps(response) + "\n"
            except Exception as serial_exc:
                payload = json.dumps({"error": f"serialize: {serial_exc}"}) + "\n"
            conn.sendall(payload.encode())
        except Exception as exc:
            with open("/tmp/caissa_rc_debug.log", "a") as _f:
                import traceback as _tb
                _f.write(f"[_handle_conn] cmd={cmd!r} exc={exc!r}\n{_tb.format_exc()}\n")
            try:
                conn.sendall((json.dumps({"error": str(exc)}) + "\n").encode())
            except Exception:
                pass
        finally:
            conn.close()

    def _drain(self):
        """Called on the Qt main thread every 50 ms — safe to touch Qt objects."""
        if self._draining:
            logger.debug("DRAIN re-entered — skipping")
            return
        self._draining = True
        logger.debug("DRAIN enter")
        try:
            # Pump the RPA runner (one step per drain cycle, separate from dispatch)
            if self._rpa_service is not None:
                self._rpa_service.pump_once()

            while True:
                try:
                    cmd, result_holder, done = self._queue.get_nowait()
                except queue.Empty:
                    break
                logger.debug("DISPATCH begin: %r", cmd)
                try:
                    result_holder[0] = self._dispatch(cmd)
                except Exception as exc:
                    result_holder[0] = {"error": str(exc)}
                finally:
                    logger.debug("DISPATCH end: %r", cmd)
                    done.set()
        finally:
            self._draining = False

    # ------------------------------------------------------------------
    def _dispatch(self, cmd: str) -> dict:
        parts = cmd.split(None, 1)
        verb = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if verb == "ping":
            return {"ok": True}

        if verb == "info":
            return self._qt.app_info()

        if verb == "themes":
            from Code.Themes import CaissaThemes
            return {"themes": [t["name"] for t in CaissaThemes.load_themes()]}

        if verb == "theme":
            from Code.Themes import CaissaThemes
            CaissaThemes.apply_theme(arg)
            return {"ok": True, "theme": arg}

        if verb == "screenshot":
            return self._qt.screenshot(arg or "/tmp/caissa-screenshot.png")

        if verb == "menu":
            return self._qt.menu(arg)

        if verb == "action":
            return self._qt.action(arg)

        if verb == "toolbar_info":
            return self._qt.toolbar_info()

        # UI inspection
        if verb == "list_windows":
            return self._qt.list_windows()

        if verb == "dump_ui":
            depth = int(arg) if arg.isdigit() else 3
            return self._qt.dump_ui(depth)

        if verb == "find_widget":
            return self._qt.inspect_widget(arg)

        # UI interaction
        if verb == "click_widget":
            return self._qt.click_widget(arg)

        if verb == "click_toolbar":
            return self._qt.click_toolbar(arg)

        if verb == "click_tab":
            return self._qt.click_tab(arg)

        if verb == "set_field":
            # format: "set_field <query> <value>" — split on first space after query
            sub_parts = arg.split(None, 1)
            if len(sub_parts) < 2:
                return {"error": "usage: set_field <query> <value>"}
            return self._qt.set_field(sub_parts[0], sub_parts[1])

        if verb == "combo_select":
            sub_parts = arg.split(None, 1)
            if len(sub_parts) < 2:
                return {"error": "usage: combo_select <query> <value>"}
            return self._qt.combo_select(sub_parts[0], sub_parts[1])

        if verb == "dialog_info":
            return self._qt.dialog_info()

        if verb == "dialog_accept":
            return self._qt.click_dialog_button(accept=True)

        if verb == "dialog_cancel":
            return self._qt.click_dialog_button(accept=False)

        # Game control
        if verb == "startgame":
            return self._qt.startgame(arg)

        if verb == "make_move":
            return self._qt.make_move(arg)

        if verb == "game_info":
            return self._qt.game_info()

        if verb == "force_cancel":
            return self._qt.force_cancel()

        if verb == "set_config":
            return self._qt.set_config(arg)

        if verb == "open_config":
            return self._qt.open_config()

        # ------------------------------------------------------------------
        # rpa_* verbs — all delegate to RpaService; none block _drain
        # ------------------------------------------------------------------
        if verb.startswith("rpa_"):
            svc = self._rpa()
            if svc is None:
                return {"error": "RPA layer disabled (CAISSA_RPA=0)"}
            handler = getattr(svc, verb, None)
            if handler is None:
                return {"error": f"unknown rpa verb: {verb!r}"}
            try:
                return handler(arg)
            except Exception as exc:
                logger.error("rpa verb %r raised: %s", verb, exc, exc_info=True)
                return {"error": str(exc)}

        return {"error": f"unknown command: {verb!r}"}
