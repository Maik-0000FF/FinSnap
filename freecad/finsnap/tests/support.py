# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared fixtures of the tests: the reference cube, checks.

The reference cube is the test print: 20 mm, 1 mm chamfer on every edge,
tilted 45 degrees onto its bottom chamfer.
"""

import os
import sys

import FreeCAD as App
import Part

EDGE = 20.0
# Group of FreeCAD's user parameters that stands in for the saved standard of new fins.
TEST_STANDARD_GROUP = "StandardUnderTest"
# A thin fin, as a saved standard for new fins might ask for.
STANDARD_THICKNESS = 0.9
CHAMFER = 1.0
TILT = 45.0
HALF_TURN = 180.0  # degrees
RECESS_RADIUS = 1.5    # wider than a tine, so a tine above it touches nothing
GROOVE_TOP_GAP = 0.5   # face left above a groove, so the groove does not split the face, too low for a tine
V = App.Vector


def tilted_cube():
    box = Part.makeBox(EDGE, EDGE, EDGE, V(-EDGE / 2, 0, -EDGE / 2))
    cube = box.makeChamfer(CHAMFER, box.Edges)
    cube.rotate(V(0, 0, 0), V(0, 1, 0), TILT)
    cube.translate(V(0, 0, -cube.BoundBox.ZMin))
    return cube


def split_cylinder(radius, height, bore=0.0):
    """A cylinder, or with `bore` a tube, upright on the origin, whose side
    and rims come in two halves, as some STEP files bring them."""
    halves = []
    for turn in (0, HALF_TURN):
        half = Part.makeCylinder(radius, height, V(0, 0, 0), V(0, 0, 1), HALF_TURN)
        if bore:
            half = half.cut(Part.makeCylinder(bore, height, V(0, 0, 0), V(0, 0, 1), HALF_TURN))
        half.rotate(V(0, 0, 0), V(0, 0, 1), turn)
        halves.append(half)
    return halves[0].fuse(halves[1])


def grooved(cube, face, t):
    """`cube` with a groove running up its face `face` at `t` along it, from
    below the bed to GROOVE_TOP_GAP short of the top, so the face stays one
    piece and a fin there finds no face for any tine."""
    from freecad.finsnap import geometry
    frame = geometry.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    uphill = (V(0, 0, 1) - normal * normal.z).normalize()
    start = frame.point(t, frame.s_face(frame.bed_z), frame.bed_z) - uphill * RECESS_RADIUS
    # The start lies one radius below the bed, which the length makes up for.
    length = (frame.face_top_z - frame.bed_z - GROOVE_TOP_GAP) / uphill.z + RECESS_RADIUS
    return cube.cut(Part.makeCylinder(RECESS_RADIUS, length, start, uphill))


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


def require_checkout(main):
    """Refuse to test another copy of FinSnap than the one the test `main` lies in.

    FreeCAD imports freecad.finsnap from whichever copy it finds installed; a
    copy from the Addon Manager beside a linked checkout would be tested in its
    place, and pass, without anyone noticing.

    INPUTS this has to withstand:
      test and package from the same checkout                ->  passes
      the same, one of them reached through a symbolic link  ->  passes
      test started by a path relative to the current folder  ->  passes
      package imported from another installed copy           ->  AssertionError naming both
    """
    import freecad.finsnap
    tested = os.path.dirname(os.path.realpath(freecad.finsnap.__file__))
    # The test lies in tests/ of the package it is meant for.
    wanted = os.path.dirname(os.path.dirname(os.path.realpath(main.__code__.co_filename)))
    if tested != wanted:
        raise AssertionError("FreeCAD loaded FinSnap from %s, not from the checkout of this test, %s; "
                             "remove or unlink the other copy from the Mod folder" % (tested, wanted))


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
        require_checkout(main)
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
