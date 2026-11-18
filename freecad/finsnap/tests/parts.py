# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The parts the tests run in side by side, one CI job each, and the one
place their names are written. Free of FreeCAD, so CI reads them before it
fetches FreeCAD: `python -m freecad.finsnap.tests.parts` prints the jobs as
JSON, with the variable that names the part to test_cube.py, which the
tests job takes for its matrix.
"""

import json

# The variable test_cube.py reads the part it runs from; unset, it runs every check.
TEST_PART_ENV = "FINSNAP_TEST_PART"
# Every check of test_cube.py but the matrix of side fins.
CUBE_OTHERS = "others"
# The matrix of side fins, which takes longer than all other checks together:
# one part per gap pair, by its index in test_cube.MATRIX_GAP_PAIRS.
MATRIX_PARTS = {"side-fins-touching": 0, "side-fins-short": 1}
# The job that runs test_feature.py and test_gui.py instead of a part of test_cube.py.
COMMANDS = "commands"


def ci_jobs():
    """The jobs CI runs the tests in, as its matrix takes them: the name of
    each part, and whether it is a part of test_cube.py."""
    return [{"part": part, "cube": True} for part in [*MATRIX_PARTS, CUBE_OTHERS]] + [{"part": COMMANDS, "cube": False}]


if __name__ == "__main__":
    print(json.dumps({"jobs": ci_jobs(), "env": TEST_PART_ENV}))
