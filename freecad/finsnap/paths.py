"""Where the files of the workbench lie: icons, drawings, translations, package.xml.

Every module takes its paths from here, so a file is named once.
"""

import os

PACKAGE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(PACKAGE, "icons")
IMAGES = os.path.join(PACKAGE, "images")
TRANSLATIONS = os.path.join(PACKAGE, "translations")
# package.xml sits at the root of the repository, two levels above the package.
PACKAGE_XML = os.path.join(os.path.dirname(os.path.dirname(PACKAGE)), "package.xml")

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

# Icons of the Edit fins buttons in the task panel; Add counter fin there uses
# the command's.
ICON_REMOVE_FIN = os.path.join(ICONS, "remove_fin.svg")
ICON_RESTORE_FINS = os.path.join(ICONS, "restore_fins.svg")
ICON_REMOVE_COUNTER = os.path.join(ICONS, "remove_counter.svg")

# Drawings of the task panel.
SIDE_VIEW = os.path.join(IMAGES, "side_view.svg")
TOP_VIEW = os.path.join(IMAGES, "top_view.svg")
