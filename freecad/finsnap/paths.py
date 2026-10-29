# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Where the files of the workbench lie: icons, drawings, translations, package.xml.

Every module takes its paths from here, so a file is named once.
"""

import os

PACKAGE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(PACKAGE, "icons")
IMAGES = os.path.join(PACKAGE, "images")
TRANSLATIONS = os.path.join(PACKAGE, "translations")
# The root of the repository, two levels above the package: package.xml,
# CHANGELOG.md and the pictures of the README lie there.
ROOT = os.path.dirname(os.path.dirname(PACKAGE))
# The names alone as well: the version tools also work on copies elsewhere.
PACKAGE_XML_NAME = "package.xml"
CHANGELOG_NAME = "CHANGELOG.md"
PACKAGE_XML = os.path.join(ROOT, PACKAGE_XML_NAME)
LOGO = os.path.join(ROOT, "docs", "assets", "logo.svg")

# Icons of the commands.
ICON_WORKBENCH = os.path.join(ICONS, "finsnap.svg")
ICON_QUICK = os.path.join(ICONS, "quick_fins.svg")
ICON_TILT = os.path.join(ICONS, "tilt.svg")
ICON_LAY_FLAT = os.path.join(ICONS, "lay_flat.svg")
ICON_ADD = os.path.join(ICONS, "add_fins.svg")
ICON_COUNTER = os.path.join(ICONS, "counter_fin.svg")
ICON_MESH = os.path.join(ICONS, "mesh_to_solid.svg")
ICON_EXPORT = os.path.join(ICONS, "export_3mf.svg")
ICON_EXPORT_STEP = os.path.join(ICONS, "export_step.svg")
ICON_STABILITY = os.path.join(ICONS, "check_stability.svg")
ICON_CHECK_PART = os.path.join(ICONS, "check_part.svg")
ICON_ISLANDS = os.path.join(ICONS, "islands_live.svg")

# Icons of the Edit fins buttons in the task panel; Add counter fin there uses
# the command's.
ICON_REMOVE_FIN = os.path.join(ICONS, "remove_fin.svg")
ICON_RESET_FINS = os.path.join(ICONS, "reset_fins.svg")
ICON_REMOVE_COUNTER = os.path.join(ICONS, "remove_counter.svg")

# Drawings of the task panel.
SIDE_VIEW = os.path.join(IMAGES, "side_view.svg")
TOP_VIEW = os.path.join(IMAGES, "top_view.svg")
