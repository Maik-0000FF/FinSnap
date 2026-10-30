# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Registers the FinSnap workbench. FreeCAD loads this file by its name."""

import FreeCADGui as Gui

from .i18n import QT_TRANSLATE_NOOP, translate
from .paths import ICON_WORKBENCH, TRANSLATIONS
from .preferences import LimitsPage
from .version import NAME, application

Gui.addLanguagePath(TRANSLATIONS)
Gui.updateLocale()
Gui.addPreferencePage(LimitsPage, NAME)

TOOLBAR = QT_TRANSLATE_NOOP("Workbench", "FinSnap")
TOOLTIP = QT_TRANSLATE_NOOP("Workbench", "Breakaway fins for parts printed standing on an edge")


class FinSnapWorkbench(Gui.Workbench):
    MenuText = "FinSnap"
    # Translated here at import: the language path is registered above. The
    # version follows in brackets, so the tooltip shows which FinSnap is installed.
    ToolTip = "%s (%s)" % (translate("Workbench", TOOLTIP), application())
    Icon = ICON_WORKBENCH

    def Initialize(self):  # noqa: N802 - FreeCAD API
        from . import commands

        names = commands.register()
        self.appendToolbar(TOOLBAR, names)
        self.appendMenu(TOOLBAR, names)

    def GetClassName(self):  # noqa: N802 - FreeCAD API
        return "Gui::PythonWorkbench"


Gui.addWorkbench(FinSnapWorkbench())
