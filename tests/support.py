"""Shared fixtures of the tests: the package path, the reference cube, checks.

The reference cube is the test print: 20 mm, 1 mm chamfer on every edge,
tilted 45 degrees onto its bottom chamfer.
"""

import os
import sys

import FreeCAD as App
import Part

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import freecad  # noqa: E402

# Let the namespace package find this checkout as well as installed addons.
freecad.__path__.insert(0, os.path.join(ROOT, "freecad"))

EDGE = 20.0
# Group of FreeCAD's user parameters that stands in for the saved standard of new fins.
TEST_STANDARD_GROUP = "StandardUnderTest"
# A thin fin, as a saved standard for new fins might ask for.
STANDARD_THICKNESS = 0.9
CHAMFER = 1.0
TILT = 45.0
V = App.Vector


def tilted_cube():
    box = Part.makeBox(EDGE, EDGE, EDGE, V(-EDGE / 2, 0, -EDGE / 2))
    cube = box.makeChamfer(CHAMFER, box.Edges)
    cube.rotate(V(0, 0, 0), V(0, 1, 0), TILT)
    cube.translate(V(0, 0, -cube.BoundBox.ZMin))
    return cube


def lower_left_face(cube):
    wanted = V(-1, 0, -1).normalize()
    for face in cube.Faces:
        u0, u1, v0, v1 = face.ParameterRange
        if face.normalAt((u0 + u1) / 2, (v0 + v1) / 2).getAngle(wanted) < 1e-6:
            return face
    raise AssertionError("no face leaning towards -X")


def expect(condition, message):
    if not condition:
        raise AssertionError(message)
    # sys.__stdout__: with the GUI running, print() goes to the report view.
    print("ok  ", message, file=sys.__stdout__)


def run(main, gui=False):
    """Run a test and leave FreeCAD with its result. FreeCAD swallows tracebacks
    and drops buffered output on sys.exit, so both are handled here. With the
    GUI running, sys.exit only ends the script, so the process is ended directly.

    The saved standard for new fins is pointed at a group of its own while the
    test runs, and removed afterwards, so a test never reads or changes the
    standard of the person running it."""
    from freecad.finsnap import presets
    presets.STANDARD_GROUP = TEST_STANDARD_GROUP
    presets.reset()
    try:
        main()
        result = 0
    except Exception as error:
        import traceback
        traceback.print_exc(file=sys.__stdout__)
        print("FAILED:", error, file=sys.__stdout__)
        result = 1
    App.ParamGet(presets.PREFERENCES).RemGroup(TEST_STANDARD_GROUP)
    sys.__stdout__.flush()
    if gui:
        os._exit(result)
    sys.exit(result)
