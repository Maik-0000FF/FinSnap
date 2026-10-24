"""Build fins on the reference cube and check the result.

Run from the repository root:
    freecad --console tests/test_cube.py
"""

import math
import os
import sys

import Part

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import expect, lower_left_face, run, tilted_cube  # noqa: E402
from freecad.finsnap import defaults as d  # noqa: E402
from freecad.finsnap import geometry  # noqa: E402
from freecad.finsnap import orient  # noqa: E402
from freecad.finsnap.params import FinParams  # noqa: E402

import FreeCAD as App  # noqa: E402

# Thin horizontal slices through the fin, to measure it layer by layer.
SLICE_SIZE = 1000.0
SLICE_HEIGHT = 0.01
SLICE_LOW = 0.1


def shape_regression(cube, face):
    """Fixed measurements of the reference fin, so a change in shape shows up."""
    result = geometry.build(cube, face, FinParams())
    fin = result.fins
    expect(len(fin.Solids) == 1 and fin.isValid(), "the fin is one valid solid")
    gap = min(body.distToShape(cube)[0] for body in result.bodies)
    expect(abs(gap - d.GAP) < d.TOLERANCE, "fin and foot keep the gap of %.2f mm" % d.GAP)

    foot_top = d.FOOT_THICKNESS
    inner = []
    for z in (SLICE_LOW, foot_top / 2, foot_top - SLICE_LOW):
        layer = fin.common(Part.makeBox(SLICE_SIZE, SLICE_SIZE, SLICE_HEIGHT,
                                        App.Vector(-SLICE_SIZE / 2, -SLICE_SIZE / 2, z)))
        inner.append(layer.BoundBox.XMax)
    expect(max(inner) - min(inner) < d.TOLERANCE, "the inner end of the foot is vertical, no tip below it")

    above = fin.common(Part.makeBox(SLICE_SIZE, SLICE_SIZE, SLICE_HEIGHT,
                                    App.Vector(-SLICE_SIZE / 2, -SLICE_SIZE / 2, foot_top + SLICE_LOW)))
    foot = fin.common(Part.makeBox(SLICE_SIZE, SLICE_SIZE, SLICE_HEIGHT,
                                   App.Vector(-SLICE_SIZE / 2, -SLICE_SIZE / 2, SLICE_LOW)))
    expect(abs(foot.BoundBox.XMin - above.BoundBox.XMin) < d.TOLERANCE,
           "the foot ends at the straight outer edge of the fin")
    length = foot.BoundBox.XLength
    width = foot.BoundBox.YLength
    expect(abs(width - length * d.FOOT_WIDTH_RATIO) < d.TOLERANCE,
           "the foot is %.0f %% as wide as long (%.2f x %.2f mm)" % (d.FOOT_WIDTH_RATIO * 100, length, width))


def check_stand():
    """Any edge with one of its faces: the face is laid down first, then the part stands on the edge."""
    box = Part.makeBox(30, 10, 10)
    top = [e for e in box.Edges if e.BoundBox.ZMin > 10 - d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    front = [f for f in box.Faces if f.BoundBox.YMax < d.TOLERANCE][0]
    upper = [f for f in box.Faces if f.BoundBox.ZMin > 10 - d.TOLERANCE][0]
    try:
        orient.stand(box, top, d.TILT_ANGLE)
    except orient.OrientError:
        pass
    else:
        raise AssertionError("a top edge without a face was accepted")

    for face, name in ((front, "the side face"), (upper, "the upper face")):
        stood = box.copy()
        stood.Placement = orient.stand(box, top, d.TILT_ANGLE, face).multiply(stood.Placement)
        expect(abs(stood.BoundBox.ZMin) < d.TOLERANCE, "with %s the part rests on the bed" % name)
        moved_top = [e for e in stood.Edges if abs(e.Length - 30) < d.TOLERANCE
                     and e.BoundBox.ZMax < d.TOLERANCE]
        expect(len(moved_top) == 1, "with %s the part stands on the chosen edge" % name)
        leaning = [f for f in stood.Faces if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6]
        expect(len(leaning) == 2, "with %s two faces lean over the bed at 45 degrees" % name)

    bottom = [f for f in box.Faces if f.BoundBox.ZMax < d.TOLERANCE][0]
    on_bed = [e for e in bottom.Edges if e.BoundBox.YMax < d.TOLERANCE][0]
    alone = orient.stand(box, on_bed, d.TILT_ANGLE)
    with_face = orient.stand(box, on_bed, d.TILT_ANGLE, bottom)
    expect(alone.isSame(with_face, d.TOLERANCE), "a face already on the bed changes nothing")

    side = [f for f in box.Faces if f.BoundBox.XMax < d.TOLERANCE][0]
    try:
        orient.stand(box, top, d.TILT_ANGLE, side)
    except orient.OrientError as error:
        expect("not an edge" in str(error), "an edge of another face is refused: %s" % error)
    else:
        raise AssertionError("an edge of another face was accepted")

    # An L profile cannot rest on the inner face of its notch.
    notched = box.cut(Part.makeBox(20, 10, 5, App.Vector(10, 0, 5)))
    inner = [f for f in notched.Faces if abs(f.BoundBox.ZMin - 5) < d.TOLERANCE
             and f.BoundBox.ZLength < d.TOLERANCE][0]
    try:
        orient.lay_flat(notched, inner)
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "a face the part cannot rest on is refused: %s" % error)
    else:
        raise AssertionError("a face inside a notch was laid onto the bed")


def check_corners(cube, face):
    """Two fins centred on the face ends: each tine touches the face up to its edge."""
    result = geometry.build(cube, face, FinParams(placement=d.PLACEMENT_CORNERS))
    expect(len(result.fins.Solids) == 2, "corner placement gives two fins")
    frame = geometry.frame_of(cube, face)
    centres = sorted(t + result.thickness / 2 for t in result.positions)
    expect(abs(centres[0] - frame.along_min) < d.TOLERANCE and abs(centres[1] - frame.along_max) < d.TOLERANCE,
           "the corner fins are centred on the face ends")
    for tine in result.tines:
        ts = [v.Point.dot(frame.along) for v in tine.Vertexes
              if cube.isInside(v.Point, d.TOLERANCE, True)]
        expect(any(min(ts) < end < max(ts) for end in (frame.along_min, frame.along_max)),
               "a corner tine touches the part across the end of the face")
    try:
        geometry.build(cube, face, FinParams(placement=d.PLACEMENT_CORNERS, fin_thickness=30.0))
    except geometry.FinError as error:
        expect("too short" in str(error), "corner fins that would collide are refused: %s" % error)
    else:
        raise AssertionError("colliding corner fins were accepted")


def main():
    cube = tilted_cube()
    face = lower_left_face(cube)

    separate = geometry.build(cube, face, FinParams())
    expect(separate.tine_z == [1.0, 6.0, 11.0], "tines at 1, 6 and 11 mm: %s" % separate.tine_z)
    expect(math.isclose(separate.height, 11.2), "fin height ends on the top tine")
    expect(len(separate.positions) == 1, "one fin on a 20 mm face")
    expect(math.isclose(separate.thickness, d.FIN_MIN_BEADS * d.BEAD_WIDTH), "minimum thickness")
    expect(separate.fins.common(cube).Volume < d.TOLERANCE, "fins do not overlap the cube")
    expect(len(separate.tines) == 3, "three tines on the fin")

    narrow = geometry.build(cube, face, FinParams(gap=0.2))
    expect(narrow.warnings, "0.2 mm gap warns about short tines")

    counter = geometry.build(cube, face, FinParams(), tine_count=1)
    expect(counter.tine_z == [1.0], "counter fin with one tine")

    one = geometry.build(cube, face, FinParams(placement=d.PLACEMENT_CENTER))
    expect(len(one.positions) == 1, "centre placement gives one fin")

    two = geometry.build(cube, face, FinParams(placement=d.PLACEMENT_ENDS))
    expect(len(two.positions) == 2, "end placement gives two fins")

    joined = geometry.merged(cube, separate.fins)
    expect(len(joined.Solids) == 1, "merged mode gives one solid")

    try:
        geometry.build(cube, face, FinParams(tine_count=4))
    except geometry.FinError as error:
        expect("only 3 of 4" in str(error), "a fourth tine does not fit: %s" % error)
    else:
        raise AssertionError("four tines were accepted")

    box = Part.makeBox(30, 10, 10)
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.Length == 10][0]
    change = orient.tilt(box, bottom, d.TILT_ANGLE)
    box.Placement = change.multiply(box.Placement)
    expect(abs(box.BoundBox.ZMin) < d.TOLERANCE, "tilted part rests on the bed")
    expect(box.BoundBox.ZMax > 10 + d.TOLERANCE, "tilted part stands up over the edge")
    leaning = [f for f in box.Faces if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6]
    expect(leaning, "a face leans over the bed at 45 degrees")
    check_stand()

    steep = geometry.build(cube, face, FinParams())
    expect(not any("inclined" in w for w in steep.warnings), "45 degrees gives no angle warning")

    shape_regression(cube, face)

    opposite = geometry.opposite_face(cube, face)
    u0, u1, v0, v1 = opposite.ParameterRange
    normal = opposite.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    expect(normal.x > 0 and normal.z < 0, "the opposite face leans the other way")

    for foot in (1.0, 2.0, 3.0):
        raised = geometry.build(cube, face, FinParams(foot_thickness=foot))
        expect(raised.tine_z[0] == foot and len(raised.fins.Solids) == 1,
               "with a %.0f mm foot the lowest tine sits on it and is attached" % foot)
    low = geometry.build(cube, face, FinParams(foot_thickness=3.0, tine_first=1.0))
    expect(len(low.fins.Solids) == 1, "a tine set below the top of the foot still reaches into the fin")
    check_corners(cube, face)
    print("all checks passed", file=sys.__stdout__)


run(main)
