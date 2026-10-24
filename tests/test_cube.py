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
    print("all checks passed", file=sys.__stdout__)


run(main)
