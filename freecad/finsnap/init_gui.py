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
# The group of the page in Edit > Preferences shows the icon named
# "preferences-" and its name in lower case; the workbench icon stands for it.
Gui.addIcon("preferences-%s" % NAME.lower(), ICON_WORKBENCH)
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

        toolbar, menu = commands.register()
        self.appendToolbar(TOOLBAR, toolbar)
        self.appendMenu(TOOLBAR, menu)

    def GetClassName(self):  # noqa: N802 - FreeCAD API
        return "Gui::PythonWorkbench"


Gui.addWorkbench(FinSnapWorkbench())
