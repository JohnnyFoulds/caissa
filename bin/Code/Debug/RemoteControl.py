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
import os
import queue
import socket
import threading

from PySide6 import QtCore, QtWidgets

SOCKET_PATH = "/tmp/caissa-control.sock"


_DEBUG_LOG = "/tmp/caissa_rc_trace.log"
_FAULT_LOG = "/tmp/caissa_faulthandler.log"


def _dlog(msg: str):
    try:
        with open(_DEBUG_LOG, "a") as _f:
            import time as _t
            _f.write(f"[{_t.monotonic():.3f}] {msg}\n")
    except Exception:
        pass


def _enable_faulthandler():
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

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(50)

        self._hb_timer = QtCore.QTimer(self)
        self._hb_timer.timeout.connect(self._heartbeat)
        self._hb_timer.start(200)

        _enable_faulthandler()
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()

    def _heartbeat(self):
        self._heartbeat_seq += 1
        if self._heartbeat_seq % 5 == 0:  # every 1s
            import Code
            mgr = getattr(Code.procesador, "manager", None) if Code.procesador else None
            _dlog(f"HB {self._heartbeat_seq} manager={type(mgr).__name__ if mgr else None}")

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
            _dlog("DRAIN re-entered — skipping")
            return
        self._draining = True
        _dlog("DRAIN enter")
        try:
            while True:
                try:
                    cmd, result_holder, done = self._queue.get_nowait()
                except queue.Empty:
                    break
                _dlog(f"DISPATCH begin: {cmd!r}")
                try:
                    result_holder[0] = self._dispatch(cmd)
                except Exception as exc:
                    result_holder[0] = {"error": str(exc)}
                finally:
                    _dlog(f"DISPATCH end: {cmd!r}")
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

        if verb == "action":
            return self._action(arg)

        if verb == "toolbar_info":
            return self._toolbar_info()

        # UI inspection
        if verb == "list_windows":
            return self._list_windows()

        if verb == "dump_ui":
            depth = int(arg) if arg.isdigit() else 3
            return self._dump_ui(depth)

        if verb == "find_widget":
            return self._find_widget(arg)

        # UI interaction
        if verb == "click_widget":
            return self._click_widget(arg)

        if verb == "click_toolbar":
            return self._click_toolbar(arg)

        if verb == "click_tab":
            return self._click_tab(arg)

        if verb == "set_field":
            # format: "set_field <query> <value>" — split on first space after query
            sub_parts = arg.split(None, 1)
            if len(sub_parts) < 2:
                return {"error": "usage: set_field <query> <value>"}
            return self._set_field(sub_parts[0], sub_parts[1])

        if verb == "combo_select":
            sub_parts = arg.split(None, 1)
            if len(sub_parts) < 2:
                return {"error": "usage: combo_select <query> <value>"}
            return self._combo_select(sub_parts[0], sub_parts[1])

        if verb == "dialog_info":
            return self._dialog_info()

        if verb == "dialog_accept":
            return self._dialog_button(accept=True)

        if verb == "dialog_cancel":
            return self._dialog_button(accept=False)

        # Game control
        if verb == "startgame":
            return self._startgame(arg)

        if verb == "make_move":
            return self._make_move(arg)

        if verb == "game_info":
            return self._game_info()

        if verb == "force_cancel":
            return self._force_cancel()

        if verb == "set_config":
            return self._set_config(arg)

        if verb == "open_config":
            return self._open_config()

        return {"error": f"unknown command: {verb!r}"}

    # ------------------------------------------------------------------
    # Existing helpers
    # ------------------------------------------------------------------

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
        mw = None
        if Code.procesador and hasattr(Code.procesador, "main_window"):
            mw = Code.procesador.main_window
        if mw and mw.isVisible():
            pixmap = mw.grab()  # widget.grab() works on any screen/monitor
        else:
            screen = QtWidgets.QApplication.primaryScreen()
            pixmap = screen.grabWindow(0)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        pixmap.save(path)
        return {"ok": True, "path": path}

    def _menu(self, key: str) -> dict:
        import Code
        if not (Code.procesador and hasattr(Code.procesador, "main_window")):
            return {"error": "no main window"}
        mw = Code.procesador.main_window
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

    def _action(self, key: str) -> dict:
        import Code
        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}
        try:
            proc.run_action(key)
            return {"ok": True, "key": key}
        except Exception as exc:
            return {"error": str(exc)}

    def _toolbar_info(self) -> dict:
        import Code
        from PySide6.QtCore import QPoint
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        tb = getattr(mw, "tb", None) or getattr(getattr(mw, "base", None), "tb", None)
        if not tb:
            return {"error": "no toolbar"}
        mw_origin = mw.mapToGlobal(QPoint(0, 0))
        buttons = []
        for action in tb.actions():
            widget = tb.widgetForAction(action)
            if widget:
                sz = widget.size()
                gpos = widget.mapToGlobal(QPoint(0, 0))
                buttons.append({
                    "text": action.text(),
                    "enabled": action.isEnabled(),
                    "width": sz.width(),
                    "height": sz.height(),
                    "x": gpos.x() - mw_origin.x(),
                    "y": gpos.y() - mw_origin.y(),
                })
        dpr = mw.devicePixelRatio()
        return {
            "count": len(buttons),
            "toolbar_size": {"w": tb.width(), "h": tb.height()},
            "device_pixel_ratio": dpr,
            "buttons": buttons,
        }

    # ------------------------------------------------------------------
    # UI inspection
    # ------------------------------------------------------------------

    def _list_windows(self) -> dict:
        app = QtWidgets.QApplication.instance()
        windows = []
        for w in app.topLevelWidgets():
            if not w.isVisible():
                continue
            g = w.geometry()
            windows.append({
                "class": type(w).__name__,
                "title": w.windowTitle(),
                "modal": w.isModal() if hasattr(w, "isModal") else False,
                "geometry": {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
            })
        return {"windows": windows}

    def _widget_info(self, w, depth: int) -> dict:
        """Build compact info dict for a widget."""
        g = w.geometry()
        info = {
            "class": type(w).__name__,
            "objectName": w.objectName() or None,
            "visible": w.isVisible(),
            "enabled": w.isEnabled(),
            "geometry": {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
        }
        # Extract text where available
        for attr in ("text", "title", "windowTitle", "currentText", "toolTip"):
            try:
                val = getattr(w, attr)()
                if val:
                    info["text"] = val
                    break
            except Exception:
                pass
        if depth > 0:
            children = []
            for child in w.children():
                if isinstance(child, QtWidgets.QWidget) and child.isVisible():
                    children.append(self._widget_info(child, depth - 1))
            if children:
                info["children"] = children
        return info

    def _dump_ui(self, depth: int = 3) -> dict:
        app = QtWidgets.QApplication.instance()
        roots = []
        for w in app.topLevelWidgets():
            if w.isVisible():
                roots.append(self._widget_info(w, depth))
        return {"roots": roots}

    def _find_all_visible(self):
        """Return flat list of all visible QWidget instances."""
        app = QtWidgets.QApplication.instance()
        return [w for w in app.allWidgets()
                if isinstance(w, QtWidgets.QWidget) and w.isVisible()]

    def _match_widget(self, query: str):
        """Find first visible widget whose text, objectName, or class contains query (case-insensitive)."""
        q = query.lower()
        for w in self._find_all_visible():
            # objectName match
            if q in (w.objectName() or "").lower():
                return w
            # class name match
            if q in type(w).__name__.lower():
                return w
            # text match
            for attr in ("text", "windowTitle", "title", "currentText"):
                try:
                    val = getattr(w, attr)()
                    if val and q in val.lower():
                        return w
                except Exception:
                    pass
        return None

    def _find_widget(self, query: str) -> dict:
        w = self._match_widget(query)
        if w is None:
            return {"error": f"no visible widget matching {query!r}"}
        g = w.geometry()
        parent_name = type(w.parent()).__name__ if w.parent() else None
        return {
            "class": type(w).__name__,
            "objectName": w.objectName() or None,
            "parent_class": parent_name,
            "geometry": {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
            "enabled": w.isEnabled(),
        }

    # ------------------------------------------------------------------
    # UI interaction
    # ------------------------------------------------------------------

    def _click_widget(self, query: str) -> dict:
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        w = self._match_widget(query)
        if w is None:
            return {"error": f"no visible widget matching {query!r}"}
        if not w.isEnabled():
            return {"error": f"widget {query!r} is disabled"}
        # Try QPushButton.click() first, then QTest
        if hasattr(w, "click") and callable(w.click):
            try:
                w.click()
                return {"ok": True, "class": type(w).__name__, "text": query}
            except Exception:
                pass
        QTest.mouseClick(w, Qt.MouseButton.LeftButton)
        return {"ok": True, "class": type(w).__name__, "text": query}

    def _click_toolbar(self, text: str) -> dict:
        import Code
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        tb = getattr(mw, "tb", None) or getattr(getattr(mw, "base", None), "tb", None)
        if not tb:
            return {"error": "no toolbar"}
        t_lower = text.lower()
        for action in tb.actions():
            if t_lower in action.text().lower():
                if not action.isEnabled():
                    return {"error": f"toolbar action {text!r} is disabled"}
                # Use singleShot so trigger fires AFTER this dispatch returns,
                # preventing blocking commands (menus/dialogs) from deadlocking.
                QtCore.QTimer.singleShot(0, action.trigger)
                return {"ok": True, "text": action.text()}
        return {"error": f"no toolbar action matching {text!r}"}

    def _click_tab(self, text: str) -> dict:
        t_lower = text.lower()
        for w in self._find_all_visible():
            if isinstance(w, QtWidgets.QTabWidget):
                for i in range(w.count()):
                    if t_lower in w.tabText(i).lower():
                        w.setCurrentIndex(i)
                        return {"ok": True, "tab": w.tabText(i), "index": i}
        return {"error": f"no visible QTabWidget tab matching {text!r}"}

    def _set_field(self, query: str, value: str) -> dict:
        w = self._match_widget(query)
        if w is None:
            return {"error": f"no visible widget matching {query!r}"}
        if isinstance(w, QtWidgets.QLineEdit):
            w.setText(value)
            return {"ok": True, "class": "QLineEdit", "value": value}
        if isinstance(w, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            w.setPlainText(value)
            return {"ok": True, "class": type(w).__name__, "value": value}
        if isinstance(w, QtWidgets.QSpinBox):
            try:
                w.setValue(int(value))
                return {"ok": True, "class": "QSpinBox", "value": value}
            except ValueError:
                return {"error": f"QSpinBox requires integer, got {value!r}"}
        return {"error": f"widget {type(w).__name__} does not support set_field"}

    def _combo_select(self, query: str, value: str) -> dict:
        w = self._match_widget(query)
        if w is None:
            return {"error": f"no visible widget matching {query!r}"}
        if not isinstance(w, QtWidgets.QComboBox):
            return {"error": f"widget {type(w).__name__} is not a QComboBox"}
        v_lower = value.lower()
        for i in range(w.count()):
            if v_lower in w.itemText(i).lower():
                w.setCurrentIndex(i)
                return {"ok": True, "selected": w.itemText(i), "index": i}
        return {"error": f"no combo item matching {value!r}"}

    def _get_topmost_dialog(self):
        """Return the topmost visible modal dialog, or None.

        We filter by isModal() to exclude the main window, which inherits
        QDialog (via LCDialog) but is shown non-modally.
        """
        from shiboken6 import isValid
        app = QtWidgets.QApplication.instance()
        result = None
        widgets = list(app.topLevelWidgets())  # snapshot into list
        for w in widgets:
            if not isValid(w):
                continue
            if w.isVisible() and isinstance(w, QtWidgets.QDialog) and w.isModal():
                result = w  # last one wins (topmost)
        del widgets
        return result

    def _dialog_info(self) -> dict:
        dlg = self._get_topmost_dialog()
        if dlg is None:
            return {"error": "no visible modal dialog"}
        widgets = []
        for w in dlg.findChildren(QtWidgets.QWidget):
            if not w.isVisible():
                continue
            entry = {"class": type(w).__name__, "enabled": w.isEnabled()}
            for attr in ("text", "windowTitle", "currentText", "toolTip", "placeholderText"):
                try:
                    val = getattr(w, attr)()
                    if val:
                        entry["text"] = val
                        break
                except Exception:
                    pass
            if isinstance(w, QtWidgets.QComboBox):
                entry["items"] = [w.itemText(i) for i in range(w.count())]
                entry["current"] = w.currentText()
            if isinstance(w, QtWidgets.QLineEdit):
                entry["value"] = w.text()
            if isinstance(w, QtWidgets.QSpinBox):
                entry["value"] = w.value()
            g = w.geometry()
            entry["geometry"] = {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}
            widgets.append(entry)
        return {
            "title": dlg.windowTitle(),
            "class": type(dlg).__name__,
            "widgets": widgets,
        }

    def _dialog_button(self, accept: bool) -> dict:
        dlg = self._get_topmost_dialog()
        if dlg is None:
            return {"error": "no visible modal dialog"}
        keywords = (["accept", "ok", "yes", "aceptar", "confirm"] if accept
                    else ["cancel", "close", "no", "cancelar", "reject"])
        # Search buttons in dialog
        for btn in dlg.findChildren(QtWidgets.QPushButton):
            if not btn.isVisible():
                continue
            btn_text = btn.text().lower().replace("&", "")
            if any(kw in btn_text for kw in keywords):
                btn.click()
                return {"ok": True, "clicked": btn.text(), "title": dlg.windowTitle()}
        # Fall back to QDialog accept/reject
        if accept:
            dlg.accept()
        else:
            dlg.reject()
        return {"ok": True, "method": "accept" if accept else "reject", "title": dlg.windowTitle()}

    # ------------------------------------------------------------------
    # Game control
    # ------------------------------------------------------------------

    def _build_dic_var(self, engine_key: str, depth: int, side: str) -> dict:
        import Code
        from Code.Base.Constantes import (
            ADJUST_BETTER, ENG_INTERNAL, BOOK_BEST_MOVE
        )
        from Code.Engines import SelectEngines

        rival = SelectEngines.busca_engine_default(ENG_INTERNAL, engine_key, engine_key)
        if rival is None:
            rival = SelectEngines.busca_engine_default(ENG_INTERNAL, "irina", "irina")
        if rival is None:
            raise RuntimeError("no engine found")

        is_white = (side.lower() != "black")
        dr = {
            "ENGINE":          rival.key,
            "TYPE":            rival.type,
            "ALIAS":           rival.key,
            "LIUCI":           rival.liUCI,
            "ENGINE_TIME":     0,
            "ENGINE_DEPTH":    depth,
            "ENGINE_NODES":    0,
            "ENGINE_UNLIMITED": 1,
            "CM":              rival,
        }
        return {
            "ISWHITE":       is_white,
            "SIDE":          "B" if is_white else "N",
            "RIVAL":         dr,
            "HINTS":         0,
            "ARROWS":        0,
            "THOUGHTOP":     -1,
            "THOUGHTTT":     -1,
            "ARROWSTT":      0,
            "2CHANCE":       False,
            "SUMMARY":       False,
            "TAKEBACK":      True,
            "WITHTIME":      False,
            "TIME_MODE":     0,
            "MINUTES":       10.0,
            "SECONDS":       0,
            "MINEXTRA":      0,
            "ADJUST":        ADJUST_BETTER,
            "LEVEL_HUMANIZE": 0,
            "WITH_LIMIT_PWW": False,
            "LIMIT_PWW":     90,
            "BOXHEIGHT":     24,
            "ACTIVATE_EBOARD": False,
            "OPENING":       None,
            "OPENING_LINE":  None,
            "FEN":           "",
            "RESIGN":        -800,
        }

    def _startgame(self, arg: str) -> dict:
        """Start a game directly, bypassing the dialog."""
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine

        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}

        # Parse optional kwargs: engine=X depth=N side=white|black
        engine_key = "stockfish"
        depth = 1
        side = "white"
        for part in arg.split():
            if "=" in part:
                k, v = part.split("=", 1)
                if k == "engine":
                    engine_key = v
                elif k == "depth":
                    try:
                        depth = int(v)
                    except ValueError:
                        pass
                elif k == "side":
                    side = v

        # If there's a current manager running, cancel it cleanly
        if proc.manager and hasattr(proc.manager, "game"):
            try:
                proc.manager.terminate()
            except Exception:
                pass

        try:
            dic_var = self._build_dic_var(engine_key, depth, side)
        except Exception as exc:
            return {"error": f"build_dic_var failed: {exc}"}

        try:
            with open("/tmp/caissa_startgame.log", "a") as _f:
                _f.write(f"[startgame] creating manager\n")
            manager = ManagerPlayAgainstEngine.ManagerPlayAgainstEngine(proc)
            with open("/tmp/caissa_startgame.log", "a") as _f:
                _f.write(f"[startgame] calling manager.start()\n")
            manager.start(dic_var)
            with open("/tmp/caissa_startgame.log", "a") as _f:
                _f.write(f"[startgame] manager.start() returned\n")
            return {"ok": True, "engine": engine_key, "depth": depth, "side": side}
        except Exception as exc:
            with open("/tmp/caissa_startgame.log", "a") as _f:
                import traceback as _tb
                _f.write(f"[startgame] EXCEPTION: {exc}\n{_tb.format_exc()}\n")
            return {"error": f"start failed: {exc}"}

    def _make_move(self, uci: str) -> dict:
        """Inject a player move in UCI notation (e.g. e2e4, e7e8q)."""
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine as MPAE

        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}
        manager = getattr(proc, "manager", None)
        if manager is None:
            return {"error": "no active manager"}
        if not isinstance(manager, MPAE.ManagerPlayAgainstEngine):
            return {"error": f"active manager is {type(manager).__name__}, not ManagerPlayAgainstEngine"}
        if len(uci) < 4:
            return {"error": f"invalid UCI move {uci!r} — expected at least 4 chars"}
        from_sq = uci[0:2]
        to_sq = uci[2:4]
        promo = uci[4:].lower() if len(uci) > 4 else ""
        try:
            manager.player_has_moved_dispatcher(from_sq, to_sq, promo)
            return {"ok": True, "move": uci}
        except Exception as exc:
            return {"error": str(exc)}

    def _game_info(self) -> dict:
        """Return current game state."""
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine as MPAE

        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}

        manager = getattr(proc, "manager", None)
        result = {
            "manager_class": type(manager).__name__ if manager else None,
        }

        if manager and hasattr(manager, "game") and manager.game is not None:
            game = manager.game
            try:
                result["fen"] = game.last_position.fen()
            except Exception:
                result["fen"] = None
            try:
                moves = []
                for move in game.li_moves:
                    moves.append(move.from_sq + move.to_sq + (move.promotion or ""))
                result["moves"] = moves
                result["move_count"] = len(moves)
            except Exception:
                result["moves"] = []
                result["move_count"] = 0
            try:
                result["turn"] = "white" if game.last_position.is_white else "black"
            except Exception:
                result["turn"] = None
            try:
                result["result"] = game.result
            except Exception:
                result["result"] = None
            try:
                result["is_human_side_white"] = manager.is_human_side_white
            except Exception:
                pass
            try:
                result["human_is_playing"] = manager.human_is_playing
            except Exception:
                pass

        # Toolbar buttons + enabled state
        tb_info = self._toolbar_info()
        result["toolbar"] = tb_info.get("buttons", [])

        return result

    def _set_config(self, arg: str) -> dict:
        """Set a single configuration attribute.

        Usage: ``set_config <key> <value>``
        Supported types: bool (true/false), int (digits-only), str.

        After updating the attribute, re-applies the app style so QSS changes
        take effect without a restart.
        """
        parts = arg.split(None, 1)
        if len(parts) < 2:
            return {"error": "usage: set_config <key> <value>"}
        key, raw_value = parts[0], parts[1].strip()

        import Code
        conf = Code.configuration
        if not hasattr(conf, key):
            return {"error": f"unknown configuration key: {key!r}"}

        # Type-coerce to match the existing attribute type
        existing = getattr(conf, key)
        if isinstance(existing, bool):
            value = raw_value.lower() in ("true", "1", "yes")
        elif isinstance(existing, int):
            try:
                value = int(raw_value)
            except ValueError:
                return {"error": f"key {key!r} expects int, got {raw_value!r}"}
        else:
            value = raw_value

        setattr(conf, key, value)
        conf.graba()

        # Re-apply style when x_style_mode changes so QSS takes effect immediately
        if key == "x_style_mode":
            try:
                from Code.Main import InitApp
                app = QtWidgets.QApplication.instance()
                InitApp.init_app_style(app, conf)
            except Exception as exc:
                return {"ok": True, "key": key, "value": value, "style_warning": str(exc)}

        return {"ok": True, "key": key, "value": value}

    def _open_config(self) -> dict:
        """Open the General Configuration dialog.

        Uses QTimer.singleShot to avoid blocking the dispatch loop.
        Returns immediately; the dialog opens asynchronously.
        """
        import Code
        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}
        try:
            if not getattr(proc, "main_window", None):
                return {"error": "no main window"}
            QtCore.QTimer.singleShot(0, proc.menu_options)
            return {"ok": True}
        except Exception as exc:
            return {"error": str(exc)}

    def _force_cancel(self) -> dict:
        """Force-return to home screen without showing any confirmation dialog."""
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine as MPAE
        from Code.Base.Constantes import ST_ENDGAME
        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}
        manager = getattr(proc, "manager", None)
        if manager and isinstance(manager, MPAE.ManagerPlayAgainstEngine):
            # Mark the game over FIRST so any pending singleShot(0) callbacks
            # (rival_has_moved, play_next_move) return immediately instead of
            # calling play_engine_rival() and reopening the engine.
            try:
                manager.state = ST_ENDGAME
            except Exception:
                pass
            # Invalidate any pending 800ms pon_toolbar deferred callbacks.
            # pon_toolbar(ENGINE_PLAYING) and pon_toolbar(TUTOR_THINKING) both
            # schedule QTimer.singleShot(800, partial(deferred, self.tb_huella)).
            # Each deferred checks `huella == self.tb_huella` before calling
            # set_toolbar() → WBase.pon_toolbar() → refresh_gui() → processEvents().
            # If that processEvents() runs after the engine QProcess is deleted
            # (but its CFSocket source is still in the CFRunLoop), it crashes.
            # Resetting tb_huella makes the comparison fail → deferred is a no-op.
            try:
                from Code.Z import Util
                manager.tb_huella = Util.huella()
            except Exception:
                pass
            # Properly shut down engines before procesador.start() to avoid
            # "QProcess destroyed while still running" crashes.
            try:
                manager.analyze_terminate()
            except Exception:
                pass
            try:
                if hasattr(manager, "manager_rival") and manager.manager_rival:
                    manager.manager_rival.close()
            except Exception:
                pass
            try:
                if hasattr(manager, "manager_tutor") and manager.manager_tutor:
                    manager.manager_tutor.close()
            except Exception:
                pass
        # Close open popup menus immediately (safe from inside a nested loop).
        app = QtWidgets.QApplication.instance()
        for w in app.allWidgets():
            if isinstance(w, QtWidgets.QMenu) and w.isVisible():
                try:
                    w.close()
                except Exception:
                    pass

        # Only reset to home when there is actually an active *game* manager
        # (ManagerPlayAgainstEngine).  Calling proc.start() when already on the
        # home screen schedules a deferred toolbar teardown that races with any
        # subsequent startgame command and causes a use-after-free C crash.
        active_manager = getattr(proc, "manager", None)
        if active_manager is not None and isinstance(active_manager, MPAE.ManagerPlayAgainstEngine):
            def _deferred_reset():
                _dlog("DEFERRED_RESET: calling proc.start()")
                try:
                    proc.start()
                except Exception as _e:
                    _dlog(f"DEFERRED_RESET: proc.start() raised {_e}")
                _dlog("DEFERRED_RESET: proc.start() returned")
                # Force GC on the main thread to collect Qt-object cycles
                # before a background socket thread can trigger it and crash.
                import gc
                gc.collect()
                _dlog("DEFERRED_RESET: done")

            # Defer by 300ms so proc.start() runs after any in-flight
            # action.trigger() singleShot has fully returned, preventing
            # use-after-free when pon_toolbar() deletes live QActions.
            _dlog(f"FORCE_CANCEL: scheduling deferred reset (manager={type(active_manager).__name__})")
            QtCore.QTimer.singleShot(300, _deferred_reset)

        return {"ok": True}
