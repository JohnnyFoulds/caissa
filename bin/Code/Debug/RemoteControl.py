"""
In-process remote control server for Caissa — Unix socket, Qt-safe.

Commands (newline-terminated, sent to /tmp/caissa-control.sock):
  ping                         → {"ok": true}
  info                         → current theme/style/icons config
  themes                       → list of available theme names
  theme <name>                 → apply a Caissa theme atomically
  screenshot [/path/file.png]  → grab main window, save PNG, return path
  menu <key>                   → trigger an OptionsMenu action by key

All responses are JSON + newline.
"""

import json
import os
import queue
import socket
import threading

from PySide6 import QtCore, QtWidgets

SOCKET_PATH = "/tmp/caissa-control.sock"


class RemoteControl(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = queue.Queue()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(50)

        t = threading.Thread(target=self._serve, daemon=True)
        t.start()

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
            conn.sendall((json.dumps(response) + "\n").encode())
        except Exception as exc:
            try:
                conn.sendall((json.dumps({"error": str(exc)}) + "\n").encode())
            except Exception:
                pass
        finally:
            conn.close()

    def _drain(self):
        """Called on the Qt main thread every 50 ms — safe to touch Qt objects."""
        while True:
            try:
                cmd, result_holder, done = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                result_holder[0] = self._dispatch(cmd)
            except Exception as exc:
                result_holder[0] = {"error": str(exc)}
            finally:
                done.set()

    # ------------------------------------------------------------------
    def _dispatch(self, cmd: str) -> dict:
        parts = cmd.split(None, 1)
        verb = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if verb == "ping":
            return {"ok": True}

        if verb == "info":
            return self._info()

        if verb == "themes":
            from Code.Themes import CaissaThemes
            return {"themes": [t["name"] for t in CaissaThemes.load_themes()]}

        if verb == "theme":
            from Code.Themes import CaissaThemes
            CaissaThemes.apply_theme(arg)
            return {"ok": True, "theme": arg}

        if verb == "screenshot":
            return self._screenshot(arg or "/tmp/caissa-screenshot.png")

        if verb == "menu":
            return self._menu(arg)

        return {"error": f"unknown command: {verb!r}"}

    def _info(self) -> dict:
        import Code
        from Code.QT import IconosBase
        conf = Code.configuration
        mode_names = {v: k for k, v in vars(IconosBase.Icons).items()
                      if isinstance(v, int) and not k.startswith("_")}
        return {
            "caissa_theme": getattr(conf, "x_caissa_theme", None),
            "style_mode":   conf.x_style_mode,
            "icons":        mode_names.get(conf.x_style_icons, conf.x_style_icons),
            "style":        conf.x_style,
        }

    def _screenshot(self, path: str) -> dict:
        import Code
        screen = QtWidgets.QApplication.primaryScreen()
        mw = None
        if Code.procesador and hasattr(Code.procesador, "main_window"):
            mw = Code.procesador.main_window
        if mw:
            pixmap = screen.grabWindow(int(mw.winId()))
        else:
            pixmap = screen.grabWindow(0)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        pixmap.save(path)
        return {"ok": True, "path": path}

    def _menu(self, key: str) -> dict:
        import Code
        if not (Code.procesador and hasattr(Code.procesador, "main_window")):
            return {"error": "no main window"}
        mw = Code.procesador.main_window
        # Try the options menu first, then any accessible menu
        for menu_name in ("options_menu", "play_menu", "train_menu",
                          "tools_menu", "engines_menu", "information_menu"):
            menu = getattr(mw, menu_name, None)
            if menu and hasattr(menu, "run_select"):
                try:
                    menu.run_select(key)
                    return {"ok": True, "key": key, "menu": menu_name}
                except Exception:
                    pass
        return {"error": f"key {key!r} not found in any menu"}
