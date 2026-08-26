import os.path

from PySide6 import QtCore, QtGui, QtWidgets

import Code
from Code.Z import Util
from Code.QT import Controles


def init_app_style(app, configuration):
    # - Style
    style = configuration.x_style
    if style == "windows11":
        style = "fusion"
    app.setStyle(QtWidgets.QStyleFactory.create(style))

    # - Style Mode
    style_mode = configuration.x_style_mode
    path_qss = Code.path_resource("Styles", f"{style_mode}.qss")
    if not os.path.isfile(path_qss):
        style_mode = configuration.x_style_mode = "By default"
        configuration.graba()
        path_qss = Code.path_resource("Styles", f"{style_mode}.qss")

    # - Colors
    path_colors = Code.path_resource("Styles", f"{style_mode}.colors")
    Code.dic_colors = Util.ini_base2dic(path_colors)
    dic_personal = Util.ini_base2dic(configuration.paths.file_colors(), rfind_equal=True)
    Code.dic_colors.update(dic_personal)
    Code.dic_qcolors = qdic = {}
    for key, color in Code.dic_colors.items():
        qdic[key] = QtGui.QColor(color)

    # - QSS
    with open(path_qss) as f:
        current = None
        li_lines = []
        for line in f:
            line = line.strip()
            if line and not line.startswith("/"):
                if current is None:
                    current = line
                elif line == "}":
                    current = None
                elif "#" in line:
                    try:
                        key, value = line.split(":")
                    except:
                        continue
                    key = key.strip()
                    color = f"#{value.split('#')[1][:6]}"
                    key_gen = f"{current}|{key}"
                    if key_gen in Code.dic_colors:
                        line = line.replace(color, Code.dic_colors[key_gen])
            li_lines.append(line)

        style_sheet = "\n".join(li_lines)
        default = """*{
background-color: %s;
color: %s;
}\n""" % (
            Code.dic_colors["BACKGROUND"],
            Code.dic_colors["FOREGROUND"],
        )
    app.setStyleSheet(default + style_sheet)

    if Code.dic_colors.get("IS_DARK") == "1":
        # Build a full dark QPalette so Qt-drawn internals (combo popups,
        # tooltips, disabled text, scroll areas) follow the theme.
        # Test must be == "1", not truthy: "0" is a non-empty string.
        qpalette = QtGui.QPalette()
        bg   = Code.dic_qcolors["BACKGROUND"]
        fg   = Code.dic_qcolors["FOREGROUND"]
        surf = Code.dic_qcolors["CHROME_SURFACE"]
        dim  = Code.dic_qcolors["CHROME_TEXT_DIM"]
        acc  = Code.dic_qcolors["CHROME_ACCENT"]
        white = QtGui.QColor("#ffffff")
        roles = [
            (QtGui.QPalette.ColorRole.Window,           bg),
            (QtGui.QPalette.ColorRole.WindowText,       fg),
            (QtGui.QPalette.ColorRole.Base,             bg),
            (QtGui.QPalette.ColorRole.AlternateBase,    surf),
            (QtGui.QPalette.ColorRole.Text,             fg),
            (QtGui.QPalette.ColorRole.BrightText,       white),
            (QtGui.QPalette.ColorRole.Button,           surf),
            (QtGui.QPalette.ColorRole.ButtonText,       fg),
            (QtGui.QPalette.ColorRole.ToolTipBase,      surf),
            (QtGui.QPalette.ColorRole.ToolTipText,      fg),
            (QtGui.QPalette.ColorRole.Highlight,        acc),
            (QtGui.QPalette.ColorRole.HighlightedText,  white),
            (QtGui.QPalette.ColorRole.PlaceholderText,  dim),
            (QtGui.QPalette.ColorRole.Link,             Code.dic_qcolors["LINKS"]),
        ]
        for role, color in roles:
            qpalette.setColor(QtGui.QPalette.ColorGroup.All,      role, color)
        # Disabled group — desaturated and half-opacity variants
        for role, color in roles:
            disabled = QtGui.QColor(color)
            disabled.setAlpha(128)
            qpalette.setColor(QtGui.QPalette.ColorGroup.Disabled, role, disabled)
    else:
        qpalette = QtWidgets.QApplication.style().standardPalette()
        qpalette.setColor(QtGui.QPalette.ColorRole.Link, Code.dic_qcolors["LINKS"])
    app.setPalette(qpalette)

    app.setEffectEnabled(QtCore.Qt.UIEffect.UI_AnimateMenu)


def apply_live_style(configuration):
    """Re-apply the current theme to the running app without restarting.

    Updates the global stylesheet, QPalette, and font so color/theme changes
    take effect immediately.  Widgets with baked-in inline stylesheets (set at
    creation time) will pick up new values the next time they are created.
    Icon-pack changes still require a restart (toolbars hold stale QIcon objects).
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    init_app_style(app, configuration)

    QtGui.QFontDatabase.addApplicationFont(Code.path_resource("IntFiles", "ChessMerida.ttf"))

    font = Controles.FontTypeNew(family=configuration.x_font_family, point_size=configuration.x_font_points)
    app.setFont(font)
