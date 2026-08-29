"""
bin/Code/Fritz/WRibbon.py — Office-style ribbon widget hosted in WBase's QToolBar.

Purity tier: **Qt allowlist** (imports PySide6).

The ribbon is a QWidgetAction containing WRibbon, which is composed of:

  WRibbon  #WRibbon
    ├─ #WRibbonHeader  (QWidget, h=26)
    │   ├─ QTabBar #WRibbonTabBar
    │   └─ #WRibbonQAT  (QWidget, QHBox of QToolButtons)
    ├─ QFrame HLine #WRibbonRule
    └─ QStackedWidget #WRibbonPages
         └─ WRibbonPage  per tab

:spec: Phase 7 (feature_spec.md §2.2, §5), docs/fritz/ribbon.md
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

_logger = logging.getLogger(__name__)

# Default pixel metrics — overridable via qproperty- from the active .qss.
_TAB_ROW_H = 24     # Tab row (houses both tab bar and QAT buttons)


class _FritzPaneCheckBox(QtWidgets.QCheckBox):
    """QCheckBox that draws its own indicator in paintEvent.

    macOS AppKit bypasses both QSS ``::indicator`` rules and QProxyStyle
    overrides for native-rendered widgets.  Owning the full ``paintEvent``
    is the only way to guarantee platform-independent blue checkmarks.
    """

    _BOX_SIZE      = 11
    _BG_ON         = QtGui.QColor("#ffffff")
    _BG_OFF        = QtGui.QColor("#ffffff")
    _BORDER        = QtGui.QColor("#a2a4a5")
    _BORDER_HOVER  = QtGui.QColor("#007acc")
    _BORDER_DIS    = QtGui.QColor("#d0d0d0")
    _BG_DIS        = QtGui.QColor("#f0f0f0")
    _MARK_COLOR    = QtGui.QColor("#007acc")
    _TEXT_COLOR    = QtGui.QColor("#1e1e1e")
    _TEXT_DIS      = QtGui.QColor("#a2a4a5")

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)

        enabled = self.isEnabled()
        checked = self.isChecked()
        hovered = self.underMouse()

        # ── indicator box ──────────────────────────────────────────────────────
        sz = self._BOX_SIZE
        y0 = (self.height() - sz) // 2
        box = QtCore.QRect(0, y0, sz, sz)

        bg     = self._BG_DIS    if not enabled else self._BG_ON
        border = (self._BORDER_DIS  if not enabled else
                  self._BORDER_HOVER if hovered   else self._BORDER)

        p.setPen(QtGui.QPen(border, 1))
        p.setBrush(bg)
        p.drawRect(box)

        # ── checkmark ─────────────────────────────────────────────────────────
        if checked and enabled:
            pen = QtGui.QPen(
                self._MARK_COLOR, 2,
                QtCore.Qt.PenStyle.SolidLine,
                QtCore.Qt.PenCapStyle.RoundCap,
                QtCore.Qt.PenJoinStyle.RoundJoin,
            )
            p.setPen(pen)
            left   = box.left()   + 1
            right  = box.right()  - 1
            top    = box.top()    + 2
            bottom = box.bottom() - 1
            mid_x  = left + (right - left) // 3
            mid_y  = bottom
            p.drawLine(left,  (top + bottom) // 2, mid_x, mid_y)
            p.drawLine(mid_x, mid_y,               right, top)

        # ── label text ────────────────────────────────────────────────────────
        text_x = sz + 5
        text_rect = QtCore.QRect(text_x, 0, self.width() - text_x, self.height())
        p.setPen(self._TEXT_COLOR if enabled else self._TEXT_DIS)
        p.setFont(self.font())
        p.drawText(
            text_rect,
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )
        p.end()

    def enterEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)
class _FlatTabBar(QtWidgets.QTabBar):
    """QTabBar with full paintEvent ownership — flat rectangular tabs.

    macOS AppKit bypasses QSS tab-shape rules and QProxyStyle overrides for
    native-rendered widgets, so rounded corners cannot be suppressed via QSS
    alone.  Owning paintEvent gives platform-independent rectangular tabs.
    """

    _BG_FIRST   = QtGui.QColor("#007acc")
    _FG_FIRST   = QtGui.QColor("#ffffff")
    _BG_SEL     = QtGui.QColor("#ffffff")
    _FG_SEL     = QtGui.QColor("#005b99")
    _BORDER_SEL = QtGui.QColor("#9daab8")
    _FG_NORMAL  = QtGui.QColor("#1e1e1e")
    _BG_HOVER   = QtGui.QColor("#e4e6f0")

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        cursor_pos = self.mapFromGlobal(QtGui.QCursor.pos())
        for i in range(self.count()):
            rect = self.tabRect(i)
            selected = (i == self.currentIndex())
            first    = (i == 0)
            hovered  = rect.contains(cursor_pos) and not selected
            if first:
                p.fillRect(rect, self._BG_FIRST)
                p.setPen(self._FG_FIRST)
            elif selected:
                p.fillRect(rect, self._BG_SEL)
                p.setPen(QtGui.QPen(self._BORDER_SEL, 1))
                p.drawLine(rect.left(),  rect.top(),    rect.right(), rect.top())
                p.drawLine(rect.left(),  rect.top(),    rect.left(),  rect.bottom())
                p.drawLine(rect.right(), rect.top(),    rect.right(), rect.bottom())
                p.setPen(self._FG_SEL)
            elif hovered:
                p.fillRect(rect, self._BG_HOVER)
                p.setPen(self._FG_NORMAL)
            else:
                p.fillRect(rect, self.palette().window())
                p.setPen(self._FG_NORMAL)
            p.setFont(self.font())
            p.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.tabText(i))
        p.end()

    def enterEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self.update()
        super().mouseMoveEvent(event)


_RULE_H = 1         # Separator between tabs and content
_CONTENT_H = 76     # Content band (buttons + captions)
_LARGE_BTN_H = 54   # Large button total height (icon + gap + text + gap + chevron area)
_LARGE_ICON_SZ = 28 # Large button icon edge length in pixels
_QAT_BTN_SZ = 20    # QAT icon-only button edge length
_BACKSTAGE_SIDEBAR_W = 150  # Width of the blue branded sidebar in the backstage overlay


class _BackstagePanel(QtWidgets.QWidget):
    """Full-height overlay panel for backstage (File) tabs.

    Parented to the top-level window and positioned to cover the area below
    the ribbon.  Shown when the backstage tab is activated; hidden when any
    other tab is activated or Escape is pressed.

    :param tab: The tab spec dict (with ``"items"`` list).
    :param dic_toolbar: Normalised dic_toolbar from :class:`WRibbon`.
    :param parent: The top-level window that owns this overlay.
    """

    #: Emitted when the panel closes itself (Escape or item activation).
    closed = QtCore.Signal()

    def __init__(
        self,
        tab: dict[str, Any],
        dic_toolbar: dict,
        parent: QtWidgets.QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WRibbonBackstagePanel")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        # Draw on top of everything else in the parent window.
        self.raise_()

        hbox = QtWidgets.QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)

        # ── left branded sidebar ──────────────────────────────────────────────
        sidebar = QtWidgets.QWidget(self)
        sidebar.setObjectName("WRibbonBackstageSidebar")
        sidebar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setFixedWidth(_BACKSTAGE_SIDEBAR_W)

        sb_vbox = QtWidgets.QVBoxLayout(sidebar)
        sb_vbox.setContentsMargins(16, 14, 8, 8)
        sb_vbox.setSpacing(6)

        title_lbl = QtWidgets.QLabel(tab.get("label", "File"), sidebar)
        title_lbl.setObjectName("WRibbonBackstageTitle")
        title_lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        sb_vbox.addWidget(title_lbl)

        subtitle_lbl = QtWidgets.QLabel("Caissa Fritz", sidebar)
        subtitle_lbl.setObjectName("WRibbonBackstageSubtitle")
        subtitle_lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        sb_vbox.addWidget(subtitle_lbl)
        sb_vbox.addStretch(1)

        hbox.addWidget(sidebar)

        # ── right content area ────────────────────────────────────────────────
        content = QtWidgets.QWidget(self)
        content.setObjectName("WRibbonBackstageContent")
        content.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        cv_vbox = QtWidgets.QVBoxLayout(content)
        cv_vbox.setContentsMargins(0, 8, 0, 8)
        cv_vbox.setSpacing(0)

        for item in tab.get("items", []):
            if item.get("separator"):
                sep = QtWidgets.QFrame(content)
                sep.setObjectName("WRibbonBackstageSep")
                sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                cv_vbox.addWidget(sep)
                continue

            key = item.get("key", "")
            action = dic_toolbar.get(key)
            if action is None:
                _logger.warning("Ribbon backstage: key %r not in dic_toolbar", key)
                continue

            btn = QtWidgets.QToolButton(content)
            btn.setObjectName("WRibbonBackstageItem")
            btn.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
            btn.setDefaultAction(action)
            label = item.get("label") or action.text()
            btn.setText(label)
            action.changed.connect(lambda _b=btn, _l=label: _b.setText(_l))
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setIconSize(QtCore.QSize(16, 16))
            btn.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            btn.setFixedHeight(30)
            # Close the backstage after any item is activated.
            btn.clicked.connect(self._on_item_clicked)
            cv_vbox.addWidget(btn)

        cv_vbox.addStretch(1)
        hbox.addWidget(content, 1)

    def _on_item_clicked(self) -> None:
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self._on_item_clicked()
        super().keyPressEvent(event)


class WRibbon(QtWidgets.QWidget):
    """
    Top-level ribbon widget.  Hosted inside ``WBase.tb`` as a single
    :class:`~PySide6.QtWidgets.QWidgetAction`.

    Band layout (top → bottom):

    - ``#WRibbonQAT`` row — Quick Access Toolbar icons
    - ``#WRibbonTabRow`` row — tab bar
    - ``#WRibbonRule`` — 1 px horizontal rule
    - ``#WRibbonPages`` stacked widget — content + captions

    :param spec: Validated ribbon spec (from :mod:`~Code.Fritz.RibbonModel`).
    :param dic_toolbar: ``WBase.dic_toolbar`` — every ``QAction`` keyed by its TB_*
        int or ``caissa:`` string.
    :param pane_api: Optional pane visibility API from the mode hook.
        ``{"names": list, "get": callable, "set": callable}``.

    .. rubric:: E1 qproperty- contract

    The following properties are read by QSS at polish time so that ``Fritz.qss``
    (and ``Modern Fritz.qss``) fully control pixel geometry without any Python
    changes:

    - ``qproperty-tabRowHeight: 26;``       — tab row height (contains tab bar + QAT)
    - ``qproperty-contentHeight: 91;``      — content band height in pixels
    - ``qproperty-largeBtnHeight: 66;``     — large button total height
    - ``qproperty-largeIconSize: 32;``      — large button icon edge length
    """

    # ── E1 backing store ──────────────────────────────────────────────────────
    _tab_row_height: int = _TAB_ROW_H
    _content_height: int = _CONTENT_H
    _large_btn_height: int = _LARGE_BTN_H
    _large_icon_size: int = _LARGE_ICON_SZ

    def __init__(
        self,
        spec: dict[str, Any],
        dic_toolbar: dict,
        pane_api: dict | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WRibbon")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        self._spec = spec
        self._dic_toolbar = self._normalise_dic_toolbar(dic_toolbar)
        self._pane_api = pane_api or {}
        self._user_tab: str | None = None  # tab explicitly chosen by user

        self._build_ui()
        self._apply_metrics()
        _f = self.font(); _f.setPointSize(10); self.setFont(_f)

    # ── dict normalisation ────────────────────────────────────────────────────

    @staticmethod
    def _normalise_dic_toolbar(dic_toolbar: dict) -> dict:
        """Return a copy keyed by both integer TB_* values AND their string names.

        ``WBase.dic_toolbar`` stores actions under integer keys (e.g. ``TB_RESIGN=11``).
        The ribbon JSON uses string names (``"TB_RESIGN"``).  This builds a merged
        dict so both lookup styles resolve to the same QAction.
        """
        from Code.Base import Constantes

        _int_to_name = {
            v: k for k, v in vars(Constantes).items() if k.startswith("TB_")
        }
        merged: dict = dict(dic_toolbar)
        for k, action in dic_toolbar.items():
            if isinstance(k, int) and k in _int_to_name:
                merged[_int_to_name[k]] = action
        return merged

    # ── E1 qproperty- setters / getters ──────────────────────────────────────

    def _get_tab_row_height(self) -> int:
        return self._tab_row_height

    def _set_tab_row_height(self, v: int) -> None:
        self._tab_row_height = v
        if hasattr(self, "_tab_row"):
            self._tab_row.setFixedHeight(v)
        self._apply_metrics()

    tabRowHeight = QtCore.Property(int, _get_tab_row_height, _set_tab_row_height)

    def _get_content_height(self) -> int:
        return self._content_height

    def _set_content_height(self, v: int) -> None:
        self._content_height = v
        self._apply_metrics()

    contentHeight = QtCore.Property(int, _get_content_height, _set_content_height)

    def _get_large_btn_height(self) -> int:
        return self._large_btn_height

    def _set_large_btn_height(self, v: int) -> None:
        self._large_btn_height = v
        # Rebuild large buttons if pages already exist
        self._rebuild_large_buttons()

    largeBtnHeight = QtCore.Property(int, _get_large_btn_height, _set_large_btn_height)

    def _get_large_icon_size(self) -> int:
        return self._large_icon_size

    def _set_large_icon_size(self, v: int) -> None:
        self._large_icon_size = v
        self._rebuild_large_buttons()

    largeIconSize = QtCore.Property(int, _get_large_icon_size, _set_large_icon_size)

    # ── metric application ────────────────────────────────────────────────────

    def _apply_metrics(self) -> None:
        """Recompute total height from current band metrics and resize."""
        total = self._tab_row_height + _RULE_H + self._content_height
        self.setFixedHeight(total)

    def _rebuild_large_buttons(self) -> None:
        """Update icon size and height on all existing large QToolButtons."""
        if not hasattr(self, "_pages"):
            return
        icon_sz = QtCore.QSize(self._large_icon_size, self._large_icon_size)
        for i in range(self._pages.count()):
            page = self._pages.widget(i)
            for btn in page.findChildren(QtWidgets.QToolButton):
                if btn.toolButtonStyle() == QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon:
                    btn.setIconSize(icon_sz)
                    btn.setFixedHeight(self._large_btn_height)

    # ── changeEvent: re-apply metrics when the stylesheet changes ─────────────

    def changeEvent(self, event: QtCore.QEvent) -> None:
        if event.type() == QtCore.QEvent.Type.StyleChange:
            self.ensurePolished()
            self._apply_metrics()
        super().changeEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Reposition any visible backstage overlay when the ribbon width changes.
        for overlay in self._backstage_overlays.values():
            if overlay.isVisible():
                self._position_backstage(overlay)

    # ── public API ────────────────────────────────────────────────────────────

    def sync(self, li_acciones: list) -> None:
        """
        Update enabled/visible state of every slot to match *li_acciones*.

        Idempotent and cheap: only flips :class:`~PySide6.QtGui.QAction` state,
        no widget construction.

        :param li_acciones: The new ``WBase.tb.li_acciones`` list.
        """
        from Code.Fritz import RibbonModel

        slot_state = RibbonModel.state(self._spec, li_acciones)
        for key, (visible, enabled, _tab_id) in slot_state.items():
            action = self._dic_toolbar.get(key)
            if action is None:
                continue
            action.setEnabled(enabled)
            action.setVisible(visible)

        # auto-switch tab unless user has pinned one
        if self._user_tab is None:
            tab_id = RibbonModel.best_tab(self._spec, li_acciones)
            self._set_current_tab(tab_id)

        # sync panes checkboxes
        self._sync_panes()

    def current_tab(self) -> str:
        """Return the id of the currently selected ribbon tab."""
        idx = self._tab_bar.currentIndex()
        tabs = self._spec.get("tabs", [])
        if 0 <= idx < len(tabs):
            return tabs[idx].get("id", "")
        return self._spec.get("default_tab", "home")

    def select_tab(self, id_or_label: str) -> bool:
        """
        Switch to a tab by id or label.

        :param id_or_label: Tab id (e.g. ``"home"``) or display label (e.g. ``"Home"``).
        :returns: ``True`` if the tab was found and selected, ``False`` otherwise.
        """
        for i, tab in enumerate(self._spec.get("tabs", [])):
            if tab.get("id") == id_or_label or tab.get("label") == id_or_label:
                self._user_tab = tab.get("id")
                self._tab_bar.setCurrentIndex(i)
                self._pages.setCurrentIndex(i)
                return True
        return False

    def ribbon_info(self) -> dict[str, Any]:
        """
        Return a serialisable snapshot of the ribbon's current state.

        Used by ``QtDriver.ribbon_info`` to fulfil the ``ribbon_info`` socket verb.

        :returns: Dict with keys ``present``, ``height``, ``current_tab``,
            ``tabs``, ``quick_access``, ``panes``, ``overflow``.
        """
        from Code.Fritz import RibbonModel

        li_acciones = getattr(self.parent(), "li_acciones", [])
        ovf = RibbonModel.overflow(self._spec, li_acciones)

        tabs_info = []
        for i, tab in enumerate(self._spec.get("tabs", [])):
            groups_info = []
            for group in tab.get("groups", []):
                slots_info = []
                for slot in group.get("slots", []):
                    key = slot.get("key", "")
                    action = self._dic_toolbar.get(key)
                    slot_data: dict[str, Any] = {
                        "key": key,
                        "text": slot.get("label") or (action.iconText() if action else ""),
                        "size": slot.get("size", "small"),
                        "enabled": action.isEnabled() if action else False,
                        "visible": action.isVisible() if action else False,
                    }
                    slots_info.append(slot_data)
                groups_info.append({
                    "id": group.get("id", ""),
                    "label": group.get("label", ""),
                    "slots": slots_info,
                })
            tabs_info.append({
                "id": tab.get("id", ""),
                "label": tab.get("label", ""),
                "groups": groups_info,
            })

        qat_info = []
        for key in self._spec.get("quick_access", []):
            action = self._dic_toolbar.get(key)
            qat_info.append({
                "key": key,
                "enabled": action.isEnabled() if action else False,
            })

        panes_info: list[dict] = []
        if self._pane_api:
            names = self._pane_api.get("names", [])
            get_fn = self._pane_api.get("get")
            for name in names:
                panes_info.append({
                    "pane": name,
                    "checked": bool(get_fn(name)) if get_fn else True,
                })

        return {
            "present": True,
            "height": self.height(),
            "current_tab": self.current_tab(),
            "tabs": tabs_info,
            "quick_access": qat_info,
            "panes": panes_info,
            "overflow": ovf,
        }

    # ── internal construction ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Tab row — tab bar on the left, QAT buttons on the right ──────────
        self._tab_row = QtWidgets.QWidget(self)
        self._tab_row.setObjectName("WRibbonTabRow")
        self._tab_row.setFixedHeight(self._tab_row_height)
        self._tab_row.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        tab_hbox = QtWidgets.QHBoxLayout(self._tab_row)
        tab_hbox.setContentsMargins(0, 0, 4, 0)
        tab_hbox.setSpacing(0)

        self._tab_bar = _FlatTabBar(self._tab_row)
        self._tab_bar.setObjectName("WRibbonTabBar")
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        _tf = self._tab_bar.font(); _tf.setPointSize(10); self._tab_bar.setFont(_tf)
        for tab in self._spec.get("tabs", []):
            self._tab_bar.addTab(tab.get("label", ""))
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        tab_hbox.addWidget(self._tab_bar)
        tab_hbox.addStretch(1)

        # QAT — icon-only buttons, right-aligned in the tab row
        self._qat_row = self._tab_row   # alias for property setter compatibility
        self._build_qat_into(tab_hbox, self._tab_row)
        root.addWidget(self._tab_row)

        # ── Horizontal rule ───────────────────────────────────────────────────
        rule = QtWidgets.QFrame(self)
        rule.setObjectName("WRibbonRule")
        rule.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        rule.setFixedHeight(_RULE_H)
        root.addWidget(rule)

        # ── Stacked pages ─────────────────────────────────────────────────────
        self._pages = QtWidgets.QStackedWidget(self)
        self._pages.setObjectName("WRibbonPages")
        self._pages.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        # Backstage overlay widgets, keyed by tab index (created lazily).
        self._backstage_overlays: dict[int, _BackstagePanel] = {}
        for tab in self._spec.get("tabs", []):
            page = self._build_page(tab)
            self._pages.addWidget(page)
        root.addWidget(self._pages, 1)

    def _build_qat_into(
        self, hbox: QtWidgets.QHBoxLayout, parent: QtWidgets.QWidget
    ) -> None:
        """Populate *hbox* with QAT icon-only buttons, right-aligned."""
        # Stretch is already added by caller before this; we just add the buttons.
        qat_container = QtWidgets.QWidget(parent)
        qat_container.setObjectName("WRibbonQAT")
        qat_container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        qat_hbox = QtWidgets.QHBoxLayout(qat_container)
        qat_hbox.setContentsMargins(2, 2, 2, 2)
        qat_hbox.setSpacing(1)
        for key in self._spec.get("quick_access", []):
            action = self._dic_toolbar.get(key)
            if action is None:
                continue
            btn = QtWidgets.QToolButton(qat_container)
            btn.setFixedSize(_QAT_BTN_SZ, _QAT_BTN_SZ)
            btn.setDefaultAction(action)
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
            qat_hbox.addWidget(btn)
        hbox.addWidget(qat_container)

    def _build_page(self, tab: dict[str, Any]) -> QtWidgets.QWidget:
        """Build one ribbon page (stacked-widget child) for a tab."""
        if tab.get("kind") == "backstage":
            return self._build_backstage_page(tab)

        page = QtWidgets.QWidget()
        page.setObjectName(f"WRibbonPage_{tab.get('id', '')}")
        page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        hbox = QtWidgets.QHBoxLayout(page)
        hbox.setContentsMargins(4, 2, 4, 2)
        hbox.setSpacing(4)

        groups = tab.get("groups", [])
        for i, group in enumerate(groups):
            grp_widget = self._build_group(group, page)
            hbox.addWidget(grp_widget)
            # separator between groups only — not after the last one
            if i < len(groups) - 1:
                sep = QtWidgets.QWidget(page)
                sep.setObjectName("WRibbonGroupSep")
                sep.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
                sep.setFixedWidth(1)
                hbox.addWidget(sep)

        hbox.addStretch(1)
        return page

    def _build_backstage_page(self, tab: dict[str, Any]) -> QtWidgets.QWidget:
        """Return an empty placeholder page for a backstage tab.

        The actual backstage content is rendered by a :class:`_BackstagePanel`
        overlay widget (parented to the top-level window) that is created and
        shown/hidden by :meth:`_on_tab_changed`.  The stacked-widget page for a
        backstage tab is intentionally blank so nothing shows in the ribbon
        content band when the overlay is open.
        """
        page = QtWidgets.QWidget()
        page.setObjectName(f"WRibbonPage_{tab.get('id', '')}")
        page.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        return page

    def _build_group(
        self, group: dict[str, Any], parent: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        """Build a ribbon group widget with its controls and caption below."""
        kind = group.get("kind", "slots")
        container = QtWidgets.QWidget(parent)
        container.setObjectName(f"WRibbonGroup_{group.get('id', '')}")
        container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setProperty("ribbonGroup", "1")
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(0)

        if kind == "panes":
            controls = self._build_panes_group(group, container)
        elif kind == "checkboxes":
            controls = self._build_checkboxes_group(group, container)
        else:
            controls = self._build_slots_group(group, container)
        vbox.addWidget(controls, 1)

        caption = QtWidgets.QLabel(group.get("label", ""), container)
        caption.setObjectName("WRibbonGroupCaption")
        caption.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        vbox.addWidget(caption)

        return container

    def _build_slots_group(
        self, group: dict[str, Any], parent: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        """Lay out large/small QToolButtons for normal slot groups.

        Large buttons: each gets its own column in the hbox, icon above text.
        Small buttons: icon beside text, 20px tall, 2-column grid when ≥3 buttons.
        """
        slots = group.get("slots", [])
        container = QtWidgets.QWidget(parent)
        container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setProperty("ribbonGroup", "1")
        hbox = QtWidgets.QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)

        # Small buttons share a 2-column grid
        small_col = QtWidgets.QWidget(container)
        small_col.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        small_col.setProperty("ribbonGroup", "1")
        small_grid = QtWidgets.QGridLayout(small_col)
        small_grid.setContentsMargins(0, 0, 0, 0)
        small_grid.setSpacing(1)

        n_small = sum(
            1 for s in slots
            if s.get("size", "small") != "large" and self._dic_toolbar.get(s.get("key", "")) is not None
        )
        cols = 2 if n_small >= 3 else 1

        icon_sz = QtCore.QSize(self._large_icon_size, self._large_icon_size)
        has_small = False
        small_idx = 0
        for slot in slots:
            key = slot.get("key", "")
            action = self._dic_toolbar.get(key)
            if action is None:
                _logger.warning("Ribbon: key %r not in dic_toolbar — slot disabled", key)
                continue
            btn = QtWidgets.QToolButton(container)
            if slot.get("size") == "large":
                btn.setIconSize(icon_sz)
                btn.setFixedHeight(self._large_btn_height)
                btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setDefaultAction(action)
                # Slot-level icon override (e.g. Fritz-specific icons from Resources/).
                # setDefaultAction connects action.changed → btn syncs action's icon,
                # so we re-apply the override AFTER every such sync via a second connection.
                slot_icon = slot.get("icon")
                if slot_icon:
                    try:
                        from Code import path_resource
                        icon_path = path_resource(*slot_icon.split("/"))
                        if icon_path and QtCore.QFile.exists(icon_path):
                            _ci = QtGui.QIcon(icon_path)
                            btn.setIcon(_ci)
                            action.changed.connect(
                                lambda _b=btn, _i=_ci: _b.setIcon(_i)
                            )
                    except Exception:
                        pass
                # ▾ chevron below the label matches the approved Office-ribbon design
                _base = slot["label"] if slot.get("label") else action.text()
                _lbl = _base + "\n▼"
                btn.setText(_lbl)
                action.changed.connect(
                    lambda _b=btn, _l=_lbl: _b.setText(_l)
                )
                # Each large button is its own column — matches approved side-by-side layout
                hbox.addWidget(btn)
            else:
                btn.setFixedHeight(20)
                btn.setMinimumWidth(90)
                btn.setIconSize(QtCore.QSize(16, 16))
                btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                btn.setDefaultAction(action)
                if slot.get("label"):
                    _lbl = slot["label"]
                    btn.setText(_lbl)
                    action.changed.connect(
                        lambda _b=btn, _l=_lbl: _b.setText(_l)
                    )
                row, col = divmod(small_idx, cols)
                small_grid.addWidget(btn, row, col)
                small_idx += 1
                has_small = True

        if has_small:
            hbox.addWidget(small_col)
        return container

    def _build_checkboxes_group(
        self, group: dict[str, Any], parent: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        """Build a single-column list of standalone boolean checkboxes.

        Unlike the panes group these are not connected to pane_api and preserve
        their default state across sync() calls.
        """
        container = QtWidgets.QWidget(parent)
        container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setProperty("ribbonGroup", "1")
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(2, 0, 2, 0)
        vbox.setSpacing(1)
        for item in group.get("items", []):
            label = item.get("label", "")
            cb = _FritzPaneCheckBox(label, container)
            cb.setChecked(bool(item.get("default", False)))
            vbox.addWidget(cb)
        vbox.addStretch(1)
        return container

    def _build_panes_group(
        self, group: dict[str, Any], parent: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        """Build a 2-column grid of pane-visibility checkboxes."""
        container = QtWidgets.QWidget(parent)
        container.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setProperty("ribbonGroup", "1")
        grid = QtWidgets.QGridLayout(container)
        grid.setContentsMargins(2, 0, 2, 0)
        grid.setSpacing(1)
        self._pane_checkboxes: dict[str, QtWidgets.QCheckBox] = {}

        get_fn = self._pane_api.get("get") if self._pane_api else None
        set_fn = self._pane_api.get("set") if self._pane_api else None

        panes = group.get("panes", [])
        # Layout: first column gets ceil(n/2) items, second column gets the rest
        n_left = (len(panes) + 1) // 2
        for idx, pane in enumerate(panes):
            pane_key = pane.get("pane", "")
            label = pane.get("label", pane_key)
            cb = _FritzPaneCheckBox(label, container)
            cb.setEnabled(True)
            if get_fn:
                cb.setChecked(bool(get_fn(pane_key)))
            else:
                # Use the declared default state from the JSON spec
                cb.setChecked(bool(pane.get("default", False)))
            if set_fn:
                cb.toggled.connect(lambda checked, k=pane_key: set_fn(k, checked))
            self._pane_checkboxes[pane_key] = cb
            if idx < n_left:
                grid.addWidget(cb, idx, 0)
            else:
                grid.addWidget(cb, idx - n_left, 1)

        return container

    def _sync_panes(self) -> None:
        """Re-read pane visibility and update checkboxes under blockSignals."""
        get_fn = self._pane_api.get("get") if self._pane_api else None
        if not get_fn:
            return
        for pane_key, cb in getattr(self, "_pane_checkboxes", {}).items():
            cb.blockSignals(True)
            cb.setChecked(bool(get_fn(pane_key)))
            cb.blockSignals(False)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        tabs = self._spec.get("tabs", [])

        # Hide all backstage overlays first.
        for overlay in self._backstage_overlays.values():
            overlay.hide()

        if 0 <= index < len(tabs):
            tab = tabs[index]
            # A click signals user intent — pin the tab
            self._user_tab = tab.get("id")

            if tab.get("kind") == "backstage":
                self._show_backstage(index, tab)

    def _show_backstage(self, index: int, tab: dict[str, Any]) -> None:
        """Create (if needed) and show the backstage overlay for *tab*."""
        if index not in self._backstage_overlays:
            top = self.window()
            panel = _BackstagePanel(tab, self._dic_toolbar, top)
            panel.closed.connect(
                lambda i=index: self._on_backstage_closed(i)
            )
            self._backstage_overlays[index] = panel

        overlay = self._backstage_overlays[index]
        self._position_backstage(overlay)
        overlay.show()
        overlay.raise_()

    def _position_backstage(self, overlay: "_BackstagePanel") -> None:
        """Position the backstage overlay starting just below the ribbon tab row.

        The overlay covers both the ribbon content band and the entire main
        content area below it, exactly as Office's Backstage View does.
        """
        top = self.window()
        # Start from the bottom of the tab row (not the full ribbon), so the
        # overlay replaces the ribbon content band and everything below it.
        tab_row_bottom = self._tab_row.mapTo(top, QtCore.QPoint(0, self._tab_row.height()))
        y = tab_row_bottom.y()
        overlay.setGeometry(0, y, top.width(), top.height() - y)

    def _on_backstage_closed(self, backstage_index: int) -> None:
        """Switch back to the default tab when the backstage overlay is dismissed."""
        default_id = self._spec.get("default_tab", "home")
        for i, tab in enumerate(self._spec.get("tabs", [])):
            if tab.get("id") == default_id and i != backstage_index:
                self._tab_bar.blockSignals(True)
                self._tab_bar.setCurrentIndex(i)
                self._pages.setCurrentIndex(i)
                self._tab_bar.blockSignals(False)
                # Do not set _user_tab so auto-switching still works.
                return

    def _set_current_tab(self, tab_id: str) -> None:
        """Switch to tab *tab_id* without setting the user-pin."""
        for i, tab in enumerate(self._spec.get("tabs", [])):
            if tab.get("id") == tab_id:
                self._tab_bar.blockSignals(True)
                self._tab_bar.setCurrentIndex(i)
                self._pages.setCurrentIndex(i)
                self._tab_bar.blockSignals(False)
                return
