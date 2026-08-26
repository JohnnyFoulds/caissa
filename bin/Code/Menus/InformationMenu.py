import webbrowser

import Code
from Code.About import About
from Code.Menus import BaseMenu
from Code.QT import Iconos


class InformationMenu(BaseMenu.RootMenu):
    name = "Information"

    def add_options(self):
        self.new("docs", _("Documents"), Iconos.Ayuda())
        self.new("web", _("Homepage"), Iconos.Web())
        self.new("https://github.com/JohnnyFoulds/caissa/releases", _("Releases"), Iconos.Update())
        self.new("acercade", _("About"), Iconos.Aplicacion64())

    def run_select(self, resp):

        if resp == "acercade":
            self.acercade()
        elif resp == "docs":
            webbrowser.open(f"{Code.web}/docs")
        elif resp.startswith("http"):
            webbrowser.open(resp)
        elif resp == "web":
            webbrowser.open(f"{Code.web}/index?lang={Code.configuration.translator()}")

    @staticmethod
    def acercade():
        w = About.WAbout()
        w.exec()
