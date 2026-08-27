"""UI overlay loader and proxy for theme-driven dialog customisation."""

import json
import logging
import os

import Code
from Code.QT import FormLayout

logger = logging.getLogger(__name__)


def load_overlay(theme_name):
    """
    Load the UI overlay JSON for the given theme.

    :param theme_name: Theme stem, e.g. ``"Caissa"`` or ``"Dark"``.
    :returns:          Parsed overlay dict, or ``{}`` if no overlay file exists.
    :rtype:            dict
    :raises ValueError: If ``theme_name`` is empty.
    """
    if not theme_name:
        raise ValueError("theme_name must not be empty")
    path = Code.path_resource("Styles", f"{theme_name}.ui.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        logger.error("Malformed overlay JSON: %s", path, exc_info=True)
        return {}


class OverlayForm:
    """
    Proxy wrapping :class:`FormLayout.FormLayout` that applies a theme UI overlay.

    Intercepts field-building calls to rename or suppress fields according to the
    overlay dict.  Tracks which fields were visible per tab so :meth:`result` can
    perform safe named-field lookup against the raw positional result list returned
    by :meth:`run`.

    :param base_form: The :class:`FormLayout.FormLayout` instance to wrap.
    :param overlay:   Parsed overlay dict from :func:`load_overlay`.
                      May be ``{}`` to pass all calls through unchanged.
    """

    def __init__(self, base_form, overlay):
        self._form = base_form
        self._overlay_labels = overlay.get("labels", {})
        self._overlay_tabs = overlay.get("tabs", {})
        self._current_fields = []   # (label, visible) list being built for current tab
        self._tabs = []             # completed tabs; _tabs[n] corresponds to resp[n]

    def _apply_label(self, label):
        """
        Apply the overlay rename or hide rule for a field label.

        :param label: Translated label as passed by the caller.
        :returns:     ``(new_label, visible)``.  ``new_label`` is ``None`` when the
                      field should be hidden and not forwarded to the base form.
        :rtype:       tuple[str | None, bool]
        """
        if label in self._overlay_labels:
            replacement = self._overlay_labels[label]
            if replacement is None:
                return None, False
            return replacement, True
        return label, True

    def _track(self, label, visible):
        self._current_fields.append((label, visible))

    #region Field-building methods (intercept, track, conditionally forward)

    def combobox(self, label, lista, init_value, **kwargs):
        new_label, visible = self._apply_label(label)
        self._track(label, visible)
        if visible:
            self._form.combobox(new_label, lista, init_value, **kwargs)

    def checkbox(self, label, init_value):
        new_label, visible = self._apply_label(label)
        self._track(label, visible)
        if visible:
            self._form.checkbox(new_label, init_value)

    def edit(self, label, init_value):
        new_label, visible = self._apply_label(label)
        self._track(label, visible)
        if visible:
            self._form.edit(new_label, init_value)

    def spinbox(self, label, minimo, maximo, ancho, init_value):
        new_label, visible = self._apply_label(label)
        self._track(label, visible)
        if visible:
            self._form.spinbox(new_label, minimo, maximo, ancho, init_value)

    def slider(self, label, minimo, maximo, init_value, **kwargs):
        new_label, visible = self._apply_label(label)
        self._track(label, visible)
        if visible:
            self._form.slider(new_label, minimo, maximo, init_value, **kwargs)

    def font(self, label, init_value):
        new_label, visible = self._apply_label(label)
        self._track(label, visible)
        if visible:
            self._form.font(new_label, init_value)

    #endregion

    #region Passthrough methods (structural, produce no result values)

    def separador(self):
        self._form.separador()

    def line(self, arriba=0, abajo=0):
        self._form.line(arriba, abajo)

    def apart(self, label):
        self._form.apart(label)

    def titulo(self, label):
        self._form.titulo(label)

    def titulo_aviso(self, label):
        self._form.titulo_aviso(label)

    #endregion

    def add_tab(self, label):
        renamed = self._overlay_tabs.get(label, label)
        self._form.add_tab(renamed)
        self._tabs.append(self._current_fields)
        self._current_fields = []

    def run(self):
        return self._form.run()

    def result(self, tab_idx, tab_result, label, default=None):
        """
        Return the submitted value for a named field from a tab's result list.

        Accounts for hidden fields: the positional index in ``tab_result`` is
        computed from only the visible fields tracked for that tab.

        :param tab_idx:    Zero-based tab index (0 = first ``add_tab`` group).
        :param tab_result: Raw result list for that tab as returned by :meth:`run`.
        :param label:      The label string as originally passed to the form builder
                           (translated, matching the value used at build time).
        :param default:    Returned when the field was hidden or not found.
        :returns:          Submitted field value, or ``default``.
        """
        if tab_idx >= len(self._tabs):
            return default
        result_idx = 0
        for field_label, visible in self._tabs[tab_idx]:
            if field_label == label:
                if not visible:
                    return default
                if result_idx < len(tab_result):
                    return tab_result[result_idx]
                return default
            if visible:
                result_idx += 1
        return default
