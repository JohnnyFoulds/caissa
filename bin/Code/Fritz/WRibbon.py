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

from PySide6 import QtCore, QtWidgets

_logger = logging.getLogger(__name__)

_HEADER_H = 26
_RULE_H = 1
_CONTENT_H = 88  # overridden by qproperty-ribbonContentHeight at polish
_QAT_BTN_SZ = 20


class WRibbon(QtWidgets.QWidget):
    """
    Top-level ribbon widget.  Hosted inside ``WBase.tb`` as a single
    :class:`~PySide6.QtWidgets.QWidgetAction`.

    :param spec: Validated ribbon spec (from :mod:`~Code.Fritz.RibbonModel`).
    :param dic_toolbar: ``WBase.dic_toolbar`` — every ``QAction`` keyed by its TB_*
        int or ``caissa:`` string.
    :param pane_api: Optional pane visibility API from the mode hook.
        ``{"names": list, "get": callable, "set": callable}``.
    """

    # qproperty- contract (E1)
    _ribbon_height = _HEADER_H + _RULE_H + _CONTENT_H

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
        self._dic_toolbar = dic_toolbar
        self._pane_api = pane_api or {}
        self._user_tab: str | None = None  # tab explicitly chosen by user

        self._build_ui()
        self.setFixedHeight(self._ribbon_height)

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

        # header row: tab bar + QAT
        header = QtWidgets.QWidget(self)
        header.setObjectName("WRibbonHeader")
        header.setFixedHeight(_HEADER_H)
        hbox = QtWidgets.QHBoxLayout(header)
        hbox.setContentsMargins(0, 0, 4, 0)
        hbox.setSpacing(0)

        self._tab_bar = QtWidgets.QTabBar(header)
        self._tab_bar.setObjectName("WRibbonTabBar")
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        for tab in self._spec.get("tabs", []):
            self._tab_bar.addTab(tab.get("label", ""))
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        hbox.addWidget(self._tab_bar)
        hbox.addStretch(1)

        qat = self._build_qat(header)
        qat.setObjectName("WRibbonQAT")
        hbox.addWidget(qat)
        root.addWidget(header)

        # horizontal rule
        rule = QtWidgets.QFrame(self)
        rule.setObjectName("WRibbonRule")
        rule.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        rule.setFixedHeight(_RULE_H)
        root.addWidget(rule)

        # stacked pages
        self._pages = QtWidgets.QStackedWidget(self)
        self._pages.setObjectName("WRibbonPages")
        for tab in self._spec.get("tabs", []):
            page = self._build_page(tab)
            self._pages.addWidget(page)
        root.addWidget(self._pages, 1)

    def _build_qat(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """Build the Quick Access Toolbar strip of icon-only buttons."""
        container = QtWidgets.QWidget(parent)
        hbox = QtWidgets.QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(2)
        for key in self._spec.get("quick_access", []):
            action = self._dic_toolbar.get(key)
            if action is None:
                continue
            btn = QtWidgets.QToolButton(container)
            btn.setFixedSize(_QAT_BTN_SZ, _QAT_BTN_SZ)
            btn.setDefaultAction(action)
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
            hbox.addWidget(btn)
        return container

    def _build_page(self, tab: dict[str, Any]) -> QtWidgets.QWidget:
        """Build one ribbon page (stacked-widget child) for a tab."""
        page = QtWidgets.QWidget()
        page.setObjectName(f"WRibbonPage_{tab.get('id', '')}")
        hbox = QtWidgets.QHBoxLayout(page)
        hbox.setContentsMargins(4, 2, 4, 2)
        hbox.setSpacing(4)

        for group in tab.get("groups", []):
            grp_widget = self._build_group(group, page)
            hbox.addWidget(grp_widget)
            # vertical separator
            sep = QtWidgets.QFrame(page)
            sep.setObjectName("WRibbonGroupSep")
            sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            hbox.addWidget(sep)

        hbox.addStretch(1)
        return page

    def _build_group(
        self, group: dict[str, Any], parent: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        """Build a ribbon group widget with its controls and caption below."""
        kind = group.get("kind", "slots")
        container = QtWidgets.QWidget(parent)
        container.setObjectName(f"WRibbonGroup_{group.get('id', '')}")
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(0)

        if kind == "panes":
            controls = self._build_panes_group(group, container)
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
        """Lay out large/small QToolButtons for normal slot groups."""
        slots = group.get("slots", [])
        container = QtWidgets.QWidget(parent)
        hbox = QtWidgets.QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(2)

        large_col = QtWidgets.QWidget(container)
        large_vbox = QtWidgets.QVBoxLayout(large_col)
        large_vbox.setContentsMargins(0, 0, 0, 0)
        large_vbox.setSpacing(1)

        small_col = QtWidgets.QWidget(container)
        small_vbox = QtWidgets.QVBoxLayout(small_col)
        small_vbox.setContentsMargins(0, 0, 0, 0)
        small_vbox.setSpacing(1)

        has_large = any(s.get("size") == "large" for s in slots)
        has_small = any(s.get("size", "small") == "small" for s in slots)

        for slot in slots:
            key = slot.get("key", "")
            action = self._dic_toolbar.get(key)
            if action is None:
                _logger.warning("Ribbon: key %r not in dic_toolbar — slot disabled", key)
                continue
            btn = QtWidgets.QToolButton(container)
            if slot.get("size") == "large":
                btn.setFixedSize(56, 56)
                btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setDefaultAction(action)
                large_vbox.addWidget(btn)
            else:
                btn.setFixedHeight(20)
                btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                btn.setDefaultAction(action)
                small_vbox.addWidget(btn)

        if has_large:
            hbox.addWidget(large_col)
        if has_small:
            hbox.addWidget(small_col)
        return container

    def _build_panes_group(
        self, group: dict[str, Any], parent: QtWidgets.QWidget
    ) -> QtWidgets.QWidget:
        """Build a group of pane-visibility checkboxes."""
        container = QtWidgets.QWidget(parent)
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(1)
        self._pane_checkboxes: dict[str, QtWidgets.QCheckBox] = {}

        get_fn = self._pane_api.get("get") if self._pane_api else None
        set_fn = self._pane_api.get("set") if self._pane_api else None

        for pane in group.get("panes", []):
            pane_key = pane.get("pane", "")
            label = pane.get("label", pane_key)
            cb = QtWidgets.QCheckBox(label, container)
            cb.setEnabled(bool(self._pane_api))
            if get_fn:
                cb.setChecked(bool(get_fn(pane_key)))
            if set_fn:
                cb.toggled.connect(lambda checked, k=pane_key: set_fn(k, checked))
            self._pane_checkboxes[pane_key] = cb
            vbox.addWidget(cb)

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
        if 0 <= index < len(tabs):
            # A click signals user intent — pin the tab
            self._user_tab = tabs[index].get("id")

    def _set_current_tab(self, tab_id: str) -> None:
        """Switch to tab *tab_id* without setting the user-pin."""
        for i, tab in enumerate(self._spec.get("tabs", [])):
            if tab.get("id") == tab_id:
                self._tab_bar.blockSignals(True)
                self._tab_bar.setCurrentIndex(i)
                self._pages.setCurrentIndex(i)
                self._tab_bar.blockSignals(False)
                return
