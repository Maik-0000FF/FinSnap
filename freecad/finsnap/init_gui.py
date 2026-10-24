"""Registers the FinSnap workbench. FreeCAD loads this file by its name."""

import os

import FreeCADGui as Gui

from .i18n import QT_TRANSLATE_NOOP, TRANSLATIONS_PATH

Gui.addLanguagePath(TRANSLATIONS_PATH)
Gui.updateLocale()

TOOLBAR = QT_TRANSLATE_NOOP("Workbench", "FinSnap")
ICON = os.path.join(os.path.dirname(__file__), "icons", "finsnap.svg")


class FinSnapWorkbench(Gui.Workbench):
    MenuText = "FinSnap"
    ToolTip = QT_TRANSLATE_NOOP("Workbench",
                                "Breakaway fins for parts printed standing on an edge")
    Icon = ICON

    def Initialize(self):  # noqa: N802 - FreeCAD API
        from . import commands

        names = commands.register()
        self.appendToolbar(TOOLBAR, names)
        self.appendMenu(TOOLBAR, names)

    def GetClassName(self):  # noqa: N802 - FreeCAD API
        return "Gui::PythonWorkbench"


Gui.addWorkbench(FinSnapWorkbench())
