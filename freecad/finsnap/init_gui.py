"""Registers the FinSnap workbench. FreeCAD loads this file by its name."""

import os

import FreeCADGui as Gui

from .i18n import QT_TRANSLATE_NOOP, TRANSLATIONS_PATH, translate
from .version import application

Gui.addLanguagePath(TRANSLATIONS_PATH)
Gui.updateLocale()

TOOLBAR = QT_TRANSLATE_NOOP("Workbench", "FinSnap")
TOOLTIP = QT_TRANSLATE_NOOP("Workbench", "Breakaway fins for parts printed standing on an edge")
ICON = os.path.join(os.path.dirname(__file__), "icons", "finsnap.svg")


class FinSnapWorkbench(Gui.Workbench):
    MenuText = "FinSnap"
    # Translated here at import: the language path is registered above. The
    # version follows in brackets, so the tooltip shows which FinSnap is installed.
    ToolTip = "%s (%s)" % (translate("Workbench", TOOLTIP), application())
    Icon = ICON

    def Initialize(self):  # noqa: N802 - FreeCAD API
        from . import commands

        names = commands.register()
        self.appendToolbar(TOOLBAR, names)
        self.appendMenu(TOOLBAR, names)

    def GetClassName(self):  # noqa: N802 - FreeCAD API
        return "Gui::PythonWorkbench"


Gui.addWorkbench(FinSnapWorkbench())
