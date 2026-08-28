"""
Driver base class and Qt-backed concrete implementation.

:class:`Driver` is a plain base (no ABC, matching the existing ``Manager``
hierarchy in this codebase) that defines the eight-method seam through which
the RPA engine touches the running application.  All timing and Qt actuation
goes through this interface so :class:`~Code.Rpa.Fakes.FakeDriver` +
:class:`~Code.Rpa.Fakes.FakeClock` can drive the entire engine at zero
wall-clock cost in unit tests.

Purity tier (N-RPA-2): **only this module** (and ``Vision/Capture.py``,
``Service.py``) may import PySide6.  Everything else in ``Code.Rpa`` is
pure Python over plain dicts and dataclasses.
"""

from __future__ import annotations

import logging
import os
import time
import typing

if typing.TYPE_CHECKING:
    from Code.Rpa.Types import Snapshot

logger = logging.getLogger(__name__)


class Driver:
    """Abstract base for Caissa automation drivers.

    Concrete subclasses must override all eight methods.  Instances are
    constructed once (by :class:`~Code.Rpa.Service.RpaService` for
    :class:`QtDriver`, by tests for :class:`~Code.Rpa.Fakes.FakeDriver`)
    and passed to :class:`~Code.Rpa.Runner.Runner` via a
    :class:`~Code.Rpa.Runner.Context`.

    :raises NotImplementedError: For every method — subclasses must override.
    """

    def snapshot(self, depth: int = 3) -> "Snapshot":
        """Return a widget-tree snapshot of the current UI state.

        :param depth: Widget-tree depth (default 3, as in :meth:`dump_ui`).
        :returns: A :class:`~Code.Rpa.Types.Snapshot` with ``state_name="UNKNOWN"``
                  until :mod:`~Code.Rpa.AppState` is wired in Phase 4.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def click(self, selector: str, target_type: str = "widget") -> dict:
        """Click a UI element identified by ``selector``.

        :param selector:    Widget search query (text / objectName / class substring)
                            or toolbar action text.
        :param target_type: ``"widget"`` (default) or ``"toolbar"``.
        :returns:           Dict with ``ok=True`` on success, ``error=...`` on failure.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def set_text(self, selector: str, value: str) -> dict:
        """Set the text value of a QLineEdit / QTextEdit / QSpinBox.

        :param selector: Widget search query.
        :param value:    New text value.
        :returns:        Dict with ``ok=True`` on success, ``error=...`` on failure.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def select_combo(self, selector: str, value: str) -> dict:
        """Select an item in a QComboBox.

        :param selector: Widget search query for the combo box.
        :param value:    Item text to select (partial, case-insensitive).
        :returns:        Dict with ``ok=True`` on success, ``error=...`` on failure.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def trigger_action(self, key: str) -> dict:
        """Invoke ``procesador.run_action(key)``.

        :param key:     Action key.
        :returns:       Dict with ``ok=True`` and ``key`` on success, ``error=...``
                        if no procesador is available.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def now(self) -> float:
        """Return current time in **milliseconds**.

        All deadlines, settle windows, and backoff calculations in the runner
        use this value so :class:`~Code.Rpa.Fakes.FakeClock` can make the
        entire timing machinery deterministic.

        :returns: Monotonic time in ms.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def defer(self, ms: float, callback: typing.Callable[[], None]) -> None:
        """Schedule ``callback`` to run after ``ms`` milliseconds.

        In :class:`QtDriver` this is ``QTimer.singleShot(int(ms), callback)``.
        In :class:`~Code.Rpa.Fakes.FakeDriver` it enqueues the callback on
        the :class:`~Code.Rpa.Fakes.FakeClock` timeline.

        :param ms:       Delay in milliseconds.
        :param callback: Zero-argument callable to invoke after the delay.
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError

    def capture(self, path: str) -> str:
        """Capture the main window to ``path`` and return the saved path.

        :param path: Absolute file path for the PNG output.
        :returns:    The saved file path (same as ``path``).
        :raises NotImplementedError: Must be overridden.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Qt-backed concrete driver
# ---------------------------------------------------------------------------

class QtDriver(Driver):
    """Qt-backed driver — the only class in ``Code.Rpa`` that imports PySide6.

    Implements all eight :class:`Driver` abstract methods and additionally
    exposes every UI helper extracted from
    :class:`~Code.Debug.RemoteControl.RemoteControl` so that class can
    delegate to this one without duplicating Qt code.

    Constructed once by :class:`~Code.Rpa.Service.RpaService` (or directly
    by :class:`~Code.Debug.RemoteControl.RemoteControl` for Phase 2).
    Thread-safety: all methods must be called from the Qt main thread.
    """

    # ------------------------------------------------------------------
    # Driver interface
    # ------------------------------------------------------------------

    def snapshot(self, depth: int = 3) -> "Snapshot":
        """Return a widget-tree snapshot with an optional screen capture.

        Populates ``Snapshot.screenshot`` via :func:`~Code.Rpa.Vision.Capture.grab`
        when cv2 is available; silently omits it otherwise so object-tier RPA works
        without OpenCV installed.

        :param depth: Widget-tree recursion depth passed to :meth:`dump_ui`.
        :returns:     :class:`~Code.Rpa.Types.Snapshot` wrapping the raw dump.
        """
        from Code.Rpa.Types import Snapshot
        tree = self.dump_ui(depth).get("roots", [])

        screenshot = None
        try:
            from Code.Rpa.Vision.Availability import probe as _probe
            if _probe().cv_available:
                from Code.Rpa.Vision.Capture import grab as _grab
                from PySide6.QtWidgets import QApplication
                mw = QApplication.activeWindow()
                if mw is not None:
                    screenshot = _grab(mw)
        except Exception:
            pass  # Vision unavailable or window not ready — object tier unaffected

        return Snapshot(
            state_name="UNKNOWN",
            widget_tree=tree,
            timestamp_ms=self.now(),
            screenshot=screenshot,
        )

    def click(self, selector: str, target_type: str = "widget") -> dict:
        """Click a UI element.

        :param selector:    Widget query or toolbar action text.
        :param target_type: ``"widget"`` (default) or ``"toolbar"``.
        :returns:           Response dict.
        """
        if target_type == "toolbar":
            return self.click_toolbar(selector)
        return self.click_widget(selector)

    def set_text(self, selector: str, value: str) -> dict:
        """Set text on the widget matching ``selector``.

        :param selector: Widget search query.
        :param value:    New text value.
        :returns:        Response dict.
        """
        return self.set_field(selector, value)

    def select_combo(self, selector: str, value: str) -> dict:
        """Select a combo item.

        :param selector: Widget search query.
        :param value:    Item text.
        :returns:        Response dict.
        """
        return self.combo_select(selector, value)

    def trigger_action(self, key: str) -> dict:
        """Invoke procesador.run_action(key).

        :param key: Action key.
        :returns:   Response dict.
        """
        return self.action(key)

    def now(self) -> float:
        """Return ``time.monotonic()`` converted to milliseconds.

        :returns: Current time in ms.
        """
        return time.monotonic() * 1000.0

    def defer(self, ms: float, callback: typing.Callable[[], None]) -> None:
        """Schedule ``callback`` via ``QTimer.singleShot``.

        :param ms:       Delay in milliseconds.
        :param callback: Callable to invoke after the delay.
        """
        from PySide6 import QtCore
        QtCore.QTimer.singleShot(int(ms), callback)

    def capture(self, path: str) -> str:
        """Capture the main window to ``path``.

        :param path: Output PNG path.
        :returns:    Saved file path.
        """
        return self.screenshot(path).get("path", path)

    # ------------------------------------------------------------------
    # UI inspection helpers (extracted from RemoteControl)
    # ------------------------------------------------------------------

    def app_info(self) -> dict:
        """Return current theme/style/icons config.

        :returns: Dict with keys ``caissa_theme``, ``style_mode``, ``icons``, ``style``.
        """
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

    def screenshot(self, path: str) -> dict:
        """Grab the main window, save to ``path``, return response dict.

        :param path: Absolute PNG path.
        :returns:    ``{"ok": True, "path": path}`` on success.
        """
        import Code
        from PySide6 import QtWidgets
        mw = None
        if Code.procesador and hasattr(Code.procesador, "main_window"):
            mw = Code.procesador.main_window
        if mw and mw.isVisible():
            pixmap = mw.grab()
        else:
            screen = QtWidgets.QApplication.primaryScreen()
            pixmap = screen.grabWindow(0)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        pixmap.save(path)
        return {"ok": True, "path": path}

    def toolbar_info(self) -> dict:
        """Return main toolbar button list and dimensions.

        :returns: Dict with ``count``, ``toolbar_size``, ``device_pixel_ratio``, ``buttons``.
        """
        import Code
        from PySide6 import QtWidgets
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

    def list_windows(self) -> dict:
        """Return all top-level visible windows.

        :returns: Dict with ``windows`` list.
        """
        from PySide6 import QtWidgets
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

    def widget_info(self, w, depth: int) -> dict:
        """Build compact info dict for a single widget.

        :param w:     QWidget instance.
        :param depth: Remaining recursion depth.
        :returns:     Info dict.
        """
        from PySide6 import QtWidgets
        g = w.geometry()
        info = {
            "class": type(w).__name__,
            "objectName": w.objectName() or None,
            "visible": w.isVisible(),
            "enabled": w.isEnabled(),
            "geometry": {"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()},
        }
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
                    children.append(self.widget_info(child, depth - 1))
            if children:
                info["children"] = children
        return info

    def dump_ui(self, depth: int = 3) -> dict:
        """Return widget tree for all visible top-level windows.

        :param depth: Recursion depth (default 3).
        :returns:     Dict with ``roots`` list.
        """
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication.instance()
        roots = []
        for w in app.topLevelWidgets():
            if w.isVisible():
                roots.append(self.widget_info(w, depth))
        return {"roots": roots}

    def all_visible_widgets(self) -> list:
        """Return a flat list of all visible QWidget instances.

        :returns: List of visible QWidget objects.
        """
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication.instance()
        return [w for w in app.allWidgets()
                if isinstance(w, QtWidgets.QWidget) and w.isVisible()]

    def match_widget(self, query: str):
        """Find first visible widget whose text/objectName/class contains ``query``.

        :param query: Case-insensitive substring to match.
        :returns:     Matching QWidget or ``None``.
        """
        q = query.lower()
        for w in self.all_visible_widgets():
            if q in (w.objectName() or "").lower():
                return w
            if q in type(w).__name__.lower():
                return w
            for attr in ("text", "windowTitle", "title", "currentText"):
                try:
                    val = getattr(w, attr)()
                    if val and q in val.lower():
                        return w
                except Exception:
                    pass
        return None

    def inspect_widget(self, query: str) -> dict:
        """Return info dict for the first visible widget matching ``query``.

        :param query: Widget search query.
        :returns:     Info dict on match; ``{"error": ...}`` if not found.
        """
        w = self.match_widget(query)
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
    # Fixed-window verbs (Phase 2)
    # ------------------------------------------------------------------

    def window_info(self) -> dict:
        """Return the main window's current geometry, state, and Fritz flags.

        :returns: Dict with keys ``x``, ``y``, ``w``, ``h``, ``maximized``,
                  ``fullscreen``, ``min_w``, ``min_h``, ``normal_w``,
                  ``normal_h``, ``fit_board``, ``key_video``, ``ui_mode``.
        :spec: §2.8, Phase 2 (feature_spec.md)
        """
        import Code
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        g = mw.geometry()
        min_size = mw.minimumSize()
        normal = mw.normalGeometry()
        return {
            "x": g.x(),
            "y": g.y(),
            "w": g.width(),
            "h": g.height(),
            "maximized": mw.isMaximized(),
            "fullscreen": mw.isFullScreen(),
            "min_w": min_size.width(),
            "min_h": min_size.height(),
            "normal_w": normal.width(),
            "normal_h": normal.height(),
            "fit_board": getattr(mw, "_fit_board", False),
            "key_video": getattr(mw, "key_video", None),
            "ui_mode": getattr(Code.configuration, "x_ui_mode", None),
        }

    def board_info(self) -> dict:
        """Return the main board's current dimensions and piece-size config.

        :returns: Dict with keys ``ancho``, ``width_piece``, ``is_white_bottom``.
        :spec: §2.8, Phase 2 (feature_spec.md)
        """
        import Code
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        board = getattr(getattr(mw, "base", None), "board", None)
        if board is None:
            board = getattr(mw, "board", None)
        if board is None:
            return {"error": "no board found"}
        return {
            "ancho": board.ancho,
            "width_piece": board.width_piece,
            "is_white_bottom": getattr(board, "is_white_bottom", True),
        }

    def resize_window(self, w: int, h: int) -> dict:
        """Resize the main window and return the resulting geometry.

        Un-maximizes/un-fullscreens first so the resize takes effect.
        Calls ``processEvents`` so the reported geometry reflects the
        completed resize.

        :param w: Target width in pixels.
        :param h: Target height in pixels.
        :returns: :meth:`window_info` payload, or error dict.
        :spec: §2.8, Phase 2 (feature_spec.md)
        """
        import Code
        from PySide6 import QtWidgets
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        if mw.isMaximized() or mw.isFullScreen():
            mw.showNormal()
            QtWidgets.QApplication.processEvents()
        mw.resize(w, h)
        QtWidgets.QApplication.processEvents()
        return self.window_info()

    def set_window_state(self, state: str) -> dict:
        """Apply a named window state and return the resulting geometry.

        :param state: One of ``"normal"``, ``"maximized"``, ``"fullscreen"``.
        :returns: :meth:`window_info` payload after the state change.
        :spec: §2.8, Phase 2 (feature_spec.md)
        """
        import Code
        from PySide6 import QtWidgets
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        s = state.lower()
        if s == "normal":
            mw.showNormal()
        elif s == "maximized":
            mw.showMaximized()
        elif s == "fullscreen":
            mw.showFullScreen()
        else:
            return {"error": f"unknown state {state!r}; expected normal|maximized|fullscreen"}
        QtWidgets.QApplication.processEvents()
        return self.window_info()

    def set_splitter_sizes(self, name: str, sizes_str: str) -> dict:
        """Set sizes on a splitter found by registered name or ``objectName``.

        Search order: ``liSplitters`` on the main window (and its ``base``
        widget), then all visible ``QSplitter`` widgets whose ``objectName``
        matches *name* (case-insensitive substring).  This lets callers
        address the Fritz right-column splitter by
        ``objectName="WFritzRightCol"`` even though it is not registered.

        :param name: Registered splitter name **or** widget objectName
                     (case-insensitive substring match).
        :param sizes_str: Comma-separated integer sizes, e.g. ``"300,200,150"``.
        :returns: Response dict with ``ok``, ``name``, ``actual_sizes``.
        :spec: §2.8, Phase 2 (feature_spec.md)
        """
        import Code
        from PySide6 import QtWidgets
        from shiboken6 import isValid
        proc = Code.procesador
        if not proc or not hasattr(proc, "main_window"):
            return {"error": "no main window"}
        mw = proc.main_window
        try:
            sizes = [int(s.strip()) for s in sizes_str.split(",") if s.strip()]
        except ValueError:
            return {"error": f"invalid sizes {sizes_str!r}; expected comma-separated integers"}
        sp = None
        # 1. Search liSplitters by registered name (exact)
        for candidate, nm in getattr(mw, "liSplitters", []):
            if nm == name and isValid(candidate):
                sp = candidate
                break
        if sp is None:
            base = getattr(mw, "base", None)
            for candidate, nm in getattr(base, "liSplitters", []):
                if nm == name and isValid(candidate):
                    sp = candidate
                    break
        # 2. Fall back: search all visible QSplitters by objectName substring
        if sp is None:
            q = name.lower()
            for w in self.all_visible_widgets():
                if isinstance(w, QtWidgets.QSplitter) and q in (w.objectName() or "").lower():
                    sp = w
                    break
        if sp is None:
            return {"error": f"no live splitter named or objectName-matching {name!r}"}
        try:
            sp.setSizes(sizes)
        except Exception as exc:
            return {"error": f"setSizes failed: {exc}"}
        try:
            actual = list(sp.sizes())
        except Exception:
            actual = sizes
        return {"ok": True, "name": name, "actual_sizes": actual}

    def click_tabbar(self, query: str, target: str) -> dict:
        """Click a tab on a bare ``QTabBar`` found by *query*.

        Use this verb for bare ``QTabBar`` widgets — the ribbon tab strip
        (Phase 7) and the notation strip (Phase 5) — where :meth:`click_tab`
        (which matches only ``QTabWidget``) does not apply.

        :param query: Case-insensitive substring matching the ``QTabBar``'s
                      ``objectName``, its parent's ``objectName``, or its
                      parent's class name.  Pass ``"qtabbar"`` to match the
                      first visible ``QTabBar`` regardless of name.
        :param target: Tab label (partial, case-insensitive) or integer index
                       string.
        :returns: Response dict with ``ok``, ``tab``, ``index``.
        :spec: §2.8, Phase 2 (feature_spec.md)
        """
        from PySide6 import QtWidgets
        q = query.lower()
        for w in self.all_visible_widgets():
            if not isinstance(w, QtWidgets.QTabBar):
                continue
            if q != "qtabbar":
                parent = w.parent()
                parent_name = (parent.objectName() or "").lower() if parent else ""
                parent_class = type(parent).__name__.lower() if parent else ""
                own_name = (w.objectName() or "").lower()
                if q not in own_name and q not in parent_name and q not in parent_class:
                    continue
            t_lower = target.lower()
            for i in range(w.count()):
                tab_text = w.tabText(i)
                if t_lower == str(i) or (tab_text and t_lower in tab_text.lower()):
                    w.setCurrentIndex(i)
                    return {"ok": True, "tab": tab_text, "index": i}
            return {"error": f"no tab matching {target!r} in QTabBar {w.objectName()!r}"}
        return {"error": f"no visible QTabBar matching {query!r}"}

    # ------------------------------------------------------------------
    # UI interaction helpers (extracted from RemoteControl)
    # ------------------------------------------------------------------

    def click_widget(self, query: str) -> dict:
        """Click a visible widget by text / objectName / class.

        :param query: Widget search query.
        :returns:     Response dict.
        """
        from PySide6 import QtCore, QtWidgets
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        w = self.match_widget(query)
        if w is None:
            return {"error": f"no visible widget matching {query!r}"}
        if not w.isEnabled():
            return {"error": f"widget {query!r} is disabled"}
        if hasattr(w, "click") and callable(w.click):
            QtCore.QTimer.singleShot(0, w.click)
        else:
            QtCore.QTimer.singleShot(0, lambda: QTest.mouseClick(w, Qt.MouseButton.LeftButton))
        return {"ok": True, "class": type(w).__name__, "text": query}

    def click_toolbar(self, text: str) -> dict:
        """Click a main toolbar button by action text.

        :param text: Partial, case-insensitive action text.
        :returns:    Response dict.
        """
        import Code
        from PySide6 import QtCore
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
                QtCore.QTimer.singleShot(0, action.trigger)
                return {"ok": True, "text": action.text()}
        return {"error": f"no toolbar action matching {text!r}"}

    def click_tab(self, text: str) -> dict:
        """Click a QTabWidget tab by label.

        :param text: Partial, case-insensitive tab label.
        :returns:    Response dict.
        """
        from PySide6 import QtWidgets
        t_lower = text.lower()
        for w in self.all_visible_widgets():
            if isinstance(w, QtWidgets.QTabWidget):
                for i in range(w.count()):
                    if t_lower in w.tabText(i).lower():
                        w.setCurrentIndex(i)
                        return {"ok": True, "tab": w.tabText(i), "index": i}
        return {"error": f"no visible QTabWidget tab matching {text!r}"}

    def set_field(self, query: str, value: str) -> dict:
        """Set text on a QLineEdit / QTextEdit / QSpinBox.

        :param query: Widget search query.
        :param value: New value string.
        :returns:     Response dict.
        """
        from PySide6 import QtWidgets
        w = self.match_widget(query)
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

    def combo_select(self, selector: str, value: str) -> dict:
        """Select an item in a QComboBox.

        :param selector: Widget search query.
        :param value:    Item text (partial, case-insensitive).
        :returns:        Response dict.
        """
        from PySide6 import QtWidgets
        w = self.match_widget(selector)
        if w is None:
            return {"error": f"no visible widget matching {selector!r}"}
        if not isinstance(w, QtWidgets.QComboBox):
            return {"error": f"widget {type(w).__name__} is not a QComboBox"}
        v_lower = value.lower()
        for i in range(w.count()):
            if v_lower in w.itemText(i).lower():
                w.setCurrentIndex(i)
                return {"ok": True, "selected": w.itemText(i), "index": i}
        return {"error": f"no combo item matching {value!r}"}

    def get_topmost_dialog(self):
        """Return the topmost visible modal dialog, or ``None``.

        Filters by ``isModal()`` to exclude the main window (which inherits
        QDialog but is shown non-modally).

        :returns: A QDialog or ``None``.
        """
        from shiboken6 import isValid
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication.instance()
        result = None
        widgets = list(app.topLevelWidgets())
        for w in widgets:
            if not isValid(w):
                continue
            if w.isVisible() and isinstance(w, QtWidgets.QDialog) and w.isModal():
                result = w
        del widgets
        return result

    def dialog_info(self) -> dict:
        """Return widget tree of the topmost modal dialog.

        :returns: Dict with ``title``, ``class``, ``widgets`` on success;
                  ``{"error": "no visible modal dialog"}`` when none is open.
        """
        from PySide6 import QtWidgets
        dlg = self.get_topmost_dialog()
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

    def click_dialog_button(self, accept: bool) -> dict:
        """Accept or cancel the topmost modal dialog.

        :param accept: ``True`` to accept/OK, ``False`` to cancel.
        :returns:      Response dict.
        """
        from PySide6 import QtWidgets
        dlg = self.get_topmost_dialog()
        if dlg is None:
            return {"error": "no visible modal dialog"}
        keywords = (["accept", "ok", "yes", "aceptar", "confirm"] if accept
                    else ["cancel", "close", "no", "cancelar", "reject"])
        for btn in dlg.findChildren(QtWidgets.QPushButton):
            if not btn.isVisible():
                continue
            btn_text = btn.text().lower().replace("&", "")
            if any(kw in btn_text for kw in keywords):
                btn.click()
                return {"ok": True, "clicked": btn.text(), "title": dlg.windowTitle()}
        if accept:
            dlg.accept()
        else:
            dlg.reject()
        return {"ok": True, "method": "accept" if accept else "reject", "title": dlg.windowTitle()}

    # ------------------------------------------------------------------
    # Menu / action helpers (extracted from RemoteControl)
    # ------------------------------------------------------------------

    def menu(self, key: str) -> dict:
        """Trigger an OptionsMenu action by key.

        :param key: Menu action key.
        :returns:   Response dict.
        """
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

    def action(self, key: str) -> dict:
        """Invoke ``procesador.run_action(key)``.

        :param key: Action key.
        :returns:   Response dict.
        """
        import Code
        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}
        try:
            proc.run_action(key)
            return {"ok": True, "key": key}
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Game control helpers (extracted from RemoteControl)
    # ------------------------------------------------------------------

    def _build_dic_var(self, engine_key: str, depth: int, side: str) -> dict:
        """Build the dic_var dict for :meth:`startgame`.

        :param engine_key: Engine key string.
        :param depth:      Engine search depth.
        :param side:       ``"white"`` or ``"black"``.
        :returns:          dic_var dict for ManagerPlayAgainstEngine.
        :raises RuntimeError: If no engine is found.
        """
        import Code
        from Code.Base.Constantes import ADJUST_BETTER, ENG_INTERNAL
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

    def startgame(self, arg: str) -> dict:
        """Start a game directly, bypassing the dialog.

        :param arg: Space-separated kwargs: ``engine=X depth=N side=white|black``.
        :returns:   Response dict.
        """
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine

        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}

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
            manager = ManagerPlayAgainstEngine.ManagerPlayAgainstEngine(proc)
            manager.start(dic_var)
            return {"ok": True, "engine": engine_key, "depth": depth, "side": side}
        except Exception as exc:
            return {"error": f"start failed: {exc}"}

    def make_move(self, uci: str) -> dict:
        """Inject a player move in UCI notation.

        :param uci: UCI move string (e.g. ``e2e4``, ``e7e8q``).
        :returns:   Response dict.
        """
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

    def game_info(self) -> dict:
        """Return current game state.

        :returns: Dict with ``manager_class``, ``toolbar``, and (when a game is
                  active) ``fen``, ``moves``, ``move_count``, ``turn``, ``result``,
                  ``is_human_side_white``, ``human_is_playing``.
        """
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

        tb_info = self.toolbar_info()
        result["toolbar"] = tb_info.get("buttons", [])

        return result

    # ------------------------------------------------------------------
    # Config helpers (extracted from RemoteControl)
    # ------------------------------------------------------------------

    def set_config(self, arg: str) -> dict:
        """Set a single configuration attribute.

        :param arg: ``"<key> <value>"`` string.  Supported types: bool, int, str.
        :returns:   Response dict.
        """
        from PySide6 import QtWidgets
        parts = arg.split(None, 1)
        if len(parts) < 2:
            return {"error": "usage: set_config <key> <value>"}
        key, raw_value = parts[0], parts[1].strip()

        import Code
        conf = Code.configuration
        if not hasattr(conf, key):
            return {"error": f"unknown configuration key: {key!r}"}

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

        if key == "x_style_mode":
            try:
                from Code.Main import InitApp
                app = QtWidgets.QApplication.instance()
                InitApp.init_app_style(app, conf)
            except Exception as exc:
                return {"ok": True, "key": key, "value": value, "style_warning": str(exc)}

        return {"ok": True, "key": key, "value": value}

    def open_config(self) -> dict:
        """Open the General Configuration dialog asynchronously.

        Bypasses the options QMenu (which pops up at the cursor position and
        may appear on a different monitor) and calls WindowConfig.options
        directly so the dialog reliably appears parented to the main window.

        :returns: ``{"ok": True}`` immediately; dialog opens after the current
                  dispatch returns.
        """
        import Code
        from PySide6 import QtCore
        proc = Code.procesador
        if not proc:
            return {"error": "no procesador"}
        mw = getattr(proc, "main_window", None)
        if not mw:
            return {"error": "no main window"}

        def _open():
            try:
                from Code.Config import WindowConfig
                from Code.Main import InitApp
                dic_previo = Code.configuration.read_dic_x()
                if WindowConfig.options(mw, Code.configuration):
                    Code.configuration.graba()
                    InitApp.apply_live_style(Code.configuration)
                    if Code.configuration.needs_reinit(dic_previo):
                        proc.reiniciar()
            except Exception as exc:
                logger.error("open_config _open callback failed: %s", exc, exc_info=True)

        try:
            QtCore.QTimer.singleShot(0, _open)
            return {"ok": True}
        except Exception as exc:
            return {"error": str(exc)}

    def force_cancel(self) -> dict:
        """Force-return to home screen without showing any confirmation dialog.

        Moves verbatim from RemoteControl with all safety comments preserved.
        Every precaution documented below protects against real use-after-free
        C-level crashes observed during development.

        :returns: Always ``{"ok": True}``.
        """
        import Code
        from Code.PlayAgainstEngine import ManagerPlayAgainstEngine as MPAE
        from Code.Base.Constantes import ST_ENDGAME
        from PySide6 import QtWidgets, QtCore
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
                logger.debug("force_cancel deferred reset: calling proc.start()")
                try:
                    proc.start()
                except Exception as _e:
                    logger.debug("force_cancel deferred reset: proc.start() raised %s", _e)
                logger.debug("force_cancel deferred reset: done")
                import gc
                gc.collect()

            # Defer by 300ms so proc.start() runs after any in-flight
            # action.trigger() singleShot has fully returned, preventing
            # use-after-free when pon_toolbar() deletes live QActions.
            logger.debug(
                "force_cancel: scheduling deferred reset (manager=%s)",
                type(active_manager).__name__,
            )
            QtCore.QTimer.singleShot(300, _deferred_reset)

        return {"ok": True}
