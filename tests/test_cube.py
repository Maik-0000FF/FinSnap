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
from freecad.finsnap import overhang  # noqa: E402
from freecad.finsnap.params import FinParams, ParamError  # noqa: E402

import FreeCAD as App  # noqa: E402

V = App.Vector
PYRAMID_BASE = 20.0
PYRAMID_STEEP = 20.0   # sides at 63 degrees against the base
PYRAMID_FLAT = 5.0     # sides at 27 degrees, flatter than the overhang limit
PYRAMID_TILT = 30.0    # flatter than the overhang limit
ODD_TILT = 30.0        # any angle but 45, at which a right-angled edge needs its face
# First tines half a layer (0.1 mm) off the grid of 0.2 mm layers.
HALF_LAYER_STARTS = (1.1, 1.3, 1.5, 1.7)
RECESS_RADIUS = 1.5    # wider than a tine, so a tine above it touches nothing
GROOVE_TOP_GAP = 1.0   # face left above a groove, so the groove does not split the face
WIDE_NOZZLE = 0.8
WIDE_BEAD = 0.9       # two of them are thicker than the 1 mm base
GROOVE_DEPTH = 2.0     # a groove across the front of a box, splitting it
GROOVE_WIDTH = 2.0
GROOVE_FROM = 8.0
WIDE_BOX = 60.0          # long enough for a U profile with legs of a third each
SHIFT = 1.5           # how far a fin is moved along the face by hand, in mm
UP = V(0, 0, 1)
BOX_SIDE = 20.0
EDGE_ROUND = 3.0       # size of the chamfer or radius of the fillet on a box edge
FLOOR_SIZE = 1000.0    # a plane under every test part, to measure how high it rests
FLOOR_DEPTH = 100.0
FRUSTUM_BASE = 40.0
FRUSTUM_TOP = 20.0
FRUSTUM_HEIGHT = 15.0  # sides at 56 degrees against the base

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
    # A top edge alone: its two faces meet at a right angle, so it stands at 45 degrees.
    cornered = moved(box, orient.stand(box, top, orient.RIGHT_ANGLE_TILT))
    lowest = [e for e in cornered.Edges if abs(e.Length - 30) < d.TOLERANCE and e.BoundBox.ZMax < d.TOLERANCE]
    expect(abs(cornered.BoundBox.ZMin) < d.TOLERANCE and len(lowest) == 1 and len(leaning_at(cornered, 45)) == 2,
           "a top edge alone stands the box on it, both faces at 45 degrees")
    try:
        orient.stand(box, top, ODD_TILT)
    except orient.OrientError as error:
        expect("45" in str(error), "a top edge alone is refused at another angle: %s" % error)
    else:
        raise AssertionError("a top edge alone was accepted at another angle")
    chamfered = box.makeChamfer(EDGE_ROUND, [top])
    slanted = [e for e in chamfered.Edges if e.BoundBox.YMax < d.TOLERANCE
               and abs(e.BoundBox.ZMin - (10 - EDGE_ROUND)) < d.TOLERANCE and e.BoundBox.ZLength < d.TOLERANCE][0]
    try:
        orient.stand(chamfered, slanted, orient.RIGHT_ANGLE_TILT)
    except orient.OrientError as error:
        expect("not lie on the bed" in str(error), "an edge alone between slanted faces is refused: %s" % error)
    else:
        raise AssertionError("an edge alone between faces not at a right angle was accepted")

    # A vertical edge alone: the two side faces meet square, the edge comes to lie on the bed.
    vertical = [e for e in box.Edges if e.BoundBox.XMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    upended = moved(box, orient.stand(box, vertical, orient.RIGHT_ANGLE_TILT))
    on_it = [e for e in upended.Edges if abs(e.Length - 10) < d.TOLERANCE and e.BoundBox.ZMax < d.TOLERANCE]
    expect(abs(upended.BoundBox.ZMin) < d.TOLERANCE and on_it and len(leaning_at(upended, 45)) == 2,
           "a vertical edge alone stands the box on it, both side faces at 45 degrees")

    # The inner corner of an L profile: square, but hollow, so nothing rests on it.
    profile = box.cut(Part.makeBox(20, 10, 5, App.Vector(10, 0, 5)))
    hollow = [e for e in profile.Edges if abs(e.BoundBox.XMin - 10) < d.TOLERANCE
              and abs(e.BoundBox.XMax - 10) < d.TOLERANCE and abs(e.BoundBox.ZMax - 5) < d.TOLERANCE
              and e.BoundBox.YLength > d.TOLERANCE][0]
    try:
        orient.stand(profile, hollow, orient.RIGHT_ANGLE_TILT)
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "the edge of an inner corner alone is refused: %s" % error)
    else:
        raise AssertionError("the edge of an inner corner was accepted")

    # A side leaning slightly out of square, as on a solid from a mesh.
    for off, accepted in ((d.RIGHT_ANGLE_TOLERANCE / 2, True), (d.RIGHT_ANGLE_TOLERANCE * 2, False)):
        reach = 10 * math.tan(math.radians(off))
        outline = Part.makePolygon([App.Vector(0, 0, 0), App.Vector(10, 0, 0), App.Vector(10 + reach, 0, 10),
                                    App.Vector(0, 0, 10), App.Vector(0, 0, 0)])
        skewed = Part.Face(outline).extrude(App.Vector(0, 30, 0))
        ridge = [e for e in skewed.Edges if e.BoundBox.ZMin > 10 - d.TOLERANCE
                 and e.BoundBox.XMin > 10 - d.TOLERANCE][0]
        try:
            orient.stand(skewed, ridge, orient.RIGHT_ANGLE_TILT)
            taken = True
        except orient.OrientError:
            taken = False
        expect(taken == accepted, "an edge %.2f degrees out of square alone is %s"
               % (off, "taken" if accepted else "refused"))

    # The view looks along the line the part stands on.
    along_x = App.Vector(1, 0, 0)
    alone_change = orient.stand(box, top, orient.RIGHT_ANGLE_TILT)
    expect(orient.side_direction(alone_change, top).getAngle(along_x) < d.TOLERANCE,
           "the side view looks along the edge the box stands on")
    upper_and_front = (upper, front)
    expect(orient.side_direction(orient.rest_between(box, *upper_and_front), faces=upper_and_front)
           .getAngle(along_x) < d.TOLERANCE, "the side view looks along what joins two faces")
    bottom_face = [f for f in box.Faces if f.BoundBox.ZMax < d.TOLERANCE][0]
    expect(orient.side_direction(orient.lay_flat(box, bottom_face)) is None,
           "a face already on the bed gives no side view")

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


def reach_behind(result, frame):
    """How far the tines reach behind the plane of the face."""
    return max(frame.s_face(v.Point.z) - v.Point.dot(frame.out) for t in result.tines for v in t.Vertexes)


def tine_lengths(result, frame):
    """Length of each tine across the gap, measured horizontally."""
    lengths = []
    for tine in result.tines:
        ss = [v.Point.dot(frame.out) for v in tine.Vertexes]
        lengths.append(max(ss) - min(ss))
    return lengths


def check_corner_tines(part, face, name):
    """Corner tines lie whole on the face, end on it and are all equally long."""
    result = geometry.build(part, face, FinParams(placement=d.PLACEMENT_CORNERS))
    frame = geometry.frame_of(part, face)
    expect(reach_behind(result, frame) < d.TOLERANCE, "%s: no corner tine reaches past the face" % name)
    lengths = tine_lengths(result, frame)
    expect(max(lengths) - min(lengths) < d.TOLERANCE,
           "%s: all corner tines are equally long (%.3f to %.3f mm)" % (name, min(lengths), max(lengths)))
    return result, frame


def check_corners(cube, face):
    """Two fins on the face ends: each tine lies whole on the face and ends flush with its end."""
    result, frame = check_corner_tines(cube, face, "chamfered cube")
    expect(len(result.fins.Solids) == 2, "corner placement gives two fins")
    ts = [v.Point.dot(frame.along) for tine in result.tines for v in tine.Vertexes]
    expect(abs(min(ts) - frame.along_min) < d.TOLERANCE and abs(max(ts) - frame.along_max) < d.TOLERANCE,
           "the outer tines end flush with both ends of the face")
    reach = (result.thickness - FinParams().tine_width) / 2
    ends = sorted(result.positions)
    expect(abs(ends[0] - (frame.along_min - reach)) < d.TOLERANCE,
           "the corner fin reaches %.2f mm past the end of the face" % reach)

    sharp = Part.makeBox(30, 20, 20)
    edge = [e for e in sharp.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    sharp.Placement = orient.tilt(sharp, edge, d.TILT_ANGLE).multiply(sharp.Placement)
    leaning = [f for f in sharp.Faces if f.normalAt(0, 0).z < -d.TOLERANCE][0]
    check_corner_tines(sharp, leaning, "sharp box")

    try:
        geometry.build(cube, face, FinParams(placement=d.PLACEMENT_CORNERS, fin_thickness=30.0))
    except geometry.FinError as error:
        expect("too short" in str(error) or "narrower" in str(error),
               "corner fins that would collide are refused: %s" % error)
    else:
        raise AssertionError("colliding corner fins were accepted")


def solid_from_polygons(polygons):
    return Part.Solid(Part.Shell([Part.Face(Part.makePolygon(p + p[:1])) for p in polygons]))


def pyramid(height, apex_down=False):
    """Square base of PYRAMID_BASE, apex above its centre, or below with apex_down."""
    half = PYRAMID_BASE / 2
    base = [V(-half, -half, 0), V(half, -half, 0), V(half, half, 0), V(-half, half, 0)]
    apex = V(0, 0, -height if apex_down else height)
    sides = [[base[i], base[(i + 1) % 4], apex] for i in range(4)]
    shape = solid_from_polygons([base] + sides)
    shape.translate(V(0, 0, -shape.BoundBox.ZMin))
    return shape


def check_frustum():
    """A truncated pyramid stood on a base edge: fins under every face that leans
    over the bed, a clear refusal for the side faces that lean upward."""
    b, t = FRUSTUM_BASE / 2, FRUSTUM_TOP / 2
    base = [V(-b, -b, 0), V(b, -b, 0), V(b, b, 0), V(-b, b, 0)]
    top = [V(-t, -t, FRUSTUM_HEIGHT), V(t, -t, FRUSTUM_HEIGHT), V(t, t, FRUSTUM_HEIGHT), V(-t, t, FRUSTUM_HEIGHT)]
    shape = solid_from_polygons([base, top[::-1]] + [[base[i], base[(i + 1) % 4], top[(i + 1) % 4], top[i]]
                                                     for i in range(4)])
    edge = [e for e in shape.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < -b + d.TOLERANCE][0]
    shape.Placement = orient.tilt(shape, edge, d.TILT_ANGLE).multiply(shape.Placement)

    leaning, upward = [], []
    for f in shape.Faces:
        u0, u1, v0, v1 = f.ParameterRange
        (leaning if f.normalAt((u0 + u1) / 2, (v0 + v1) / 2).z < -d.MIN_NORMAL_COMPONENT else upward).append(f)
    built = [geometry.build(shape, f, FinParams()) for f in leaning]
    expect(len(built) == 2 and all(r.fins.Solids for r in built),
           "the tilted frustum gets fins under both faces leaning over the bed")
    for f in leaning:
        check_corner_tines(shape, f, "frustum")
    for f in upward:
        try:
            geometry.build(shape, f, FinParams())
        except geometry.FinError as error:
            expect("does not lean" in str(error) or "flat" in str(error),
                   "a face leaning upward is refused: %s" % error)
        else:
            raise AssertionError("fins were built under a face leaning upward")


def check_loft():
    """A frustum built as a loft has B-spline sides and edges that are still flat and straight."""
    b, t = FRUSTUM_BASE / 2, FRUSTUM_TOP / 2

    def square(half, z):
        return Part.makePolygon([V(-half, -half, z), V(half, -half, z), V(half, half, z), V(-half, half, z),
                                 V(-half, -half, z)])

    loft = Part.makeLoft([square(b, 0), square(t, FRUSTUM_HEIGHT)], True, True)
    side = [f for f in loft.Faces if isinstance(f.Surface, Part.BSplineSurface)][0]
    slanted = [e for e in side.Edges if isinstance(e.Curve, Part.BSplineCurve)][0]
    stood = loft.copy()
    stood.Placement = orient.stand(loft, slanted, d.TILT_ANGLE, side).multiply(stood.Placement)
    expect(abs(stood.BoundBox.ZMin) < d.TOLERANCE, "a loft stands on a slanted B-spline edge of its side")

    cone = Part.makeCone(t, b, FRUSTUM_HEIGHT)
    mantle = [f for f in cone.Faces if f.findPlane() is None][0]
    lying = moved(cone, orient.lay_flat(cone, mantle))
    on_bed = [f for f in lying.Faces if f.findPlane() is None][0]
    expect(abs(lying.BoundBox.ZMin) < d.TOLERANCE and abs(on_bed.BoundBox.ZMin) < d.TOLERANCE,
           "a cone frustum lies on its mantle")


def moved(shape, change):
    result = shape.copy()
    result.Placement = change.multiply(result.Placement)
    return result


def leaning_at(shape, degrees):
    """Faces that lean over the bed at `degrees` against it."""
    wanted = -math.cos(math.radians(degrees))
    return [f for f in shape.Faces if f.findPlane() is not None and abs(f.normalAt(0, 0).z - wanted) < 1e-6]


def resting_height(shape):
    """Height of the lowest point of `shape`, measured to a plane far below, not from its BoundBox."""
    floor = Part.makePlane(FLOOR_SIZE, FLOOR_SIZE, V(-FLOOR_SIZE / 2, -FLOOR_SIZE / 2, -FLOOR_DEPTH))
    return shape.distToShape(floor)[0] - FLOOR_DEPTH


def check_tight_bounds():
    """Two fillets meeting at a corner: after the part is laid on one, the BoundBox of the
    other reaches below the bed. The part must still rest on the fillet, on the bed, with
    its fins on the bed too."""
    box = Part.makeBox(30, 20, 20)
    corner = [e for e in box.Edges if e.BoundBox.ZMin > 20 - d.TOLERANCE
              and (e.BoundBox.YMax < d.TOLERANCE or e.BoundBox.XMax < d.TOLERANCE)]
    rounded = box.makeFillet(EDGE_ROUND, corner)
    long_fillet = [f for f in rounded.Faces if f.findPlane() is None and f.BoundBox.XLength > 20][0]
    lying = moved(rounded, orient.lay_flat(rounded, long_fillet))
    expect(abs(resting_height(lying)) < d.TOLERANCE,
           "a part laid on a fillet beside another rests on the bed, not above it")
    leaning = [f for f in lying.Faces if f.findPlane() is not None
               and -1 + d.TOLERANCE < f.normalAt(0, 0).z < -d.MIN_NORMAL_COMPONENT]
    built = geometry.build(lying, leaning[0], FinParams())
    expect(abs(resting_height(built.fins)) < d.TOLERANCE, "the fins of that part stand on the bed, not below it")


def check_chamfer_and_fillet():
    """A chamfer or a fillet chosen alone is laid onto the bed and carries the part."""
    box = Part.makeBox(BOX_SIDE, BOX_SIDE, BOX_SIDE)
    edge = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]

    chamfered = box.makeChamfer(EDGE_ROUND, [edge])
    chamfer = [f for f in chamfered.Faces if abs(abs(f.normalAt(0, 0).z) - math.sqrt(0.5)) < 1e-6][0]
    on_chamfer = moved(chamfered, orient.lay_flat(chamfered, chamfer))
    expect(abs(on_chamfer.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(on_chamfer, 45)) == 2,
           "a box stands at 45 degrees on its chamfer")

    filleted = box.makeFillet(EDGE_ROUND, [edge])
    fillet = [f for f in filleted.Faces if f.findPlane() is None][0]
    on_fillet = moved(filleted, orient.lay_flat(filleted, fillet))
    expect(abs(on_fillet.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(on_fillet, 45)) == 2,
           "a box stands at 45 degrees on its fillet")
    try:
        orient.stand(filleted, fillet.Edges[0], d.TILT_ANGLE, fillet)
    except orient.OrientError as error:
        expect("rounded" in str(error), "an edge with a fillet is refused with a clear reason: %s" % error)
    else:
        raise AssertionError("a part was stood on an edge of a fillet")

    # The two faces beside the fillet, or beside a sharp edge: both end up equally steep.
    sides = [f for f in filleted.Faces if f.findPlane() is not None
             and any(e.isSame(other) for e in f.Edges for other in fillet.Edges)
             and abs(f.normalAt(0, 0).dot(edge.Curve.Direction)) < d.TOLERANCE]
    beside = moved(filleted, orient.rest_between(filleted, *sides))
    expect(abs(beside.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(beside, 45)) == 2
           and abs(beside.BoundBox.ZMax - on_fillet.BoundBox.ZMax) < d.TOLERANCE,
           "the two faces beside a fillet stand the box on it, as the fillet alone does")
    sharp = [f for f in box.Faces if any(e.isSame(edge) for e in f.Edges)]
    on_edge = moved(box, orient.rest_between(box, *sharp))
    expect(abs(on_edge.BoundBox.ZMin) < d.TOLERANCE and len(leaning_at(on_edge, 45)) == 2,
           "the two faces of a sharp edge stand the box on that edge")
    opposite = [f for f in box.Faces if f.BoundBox.ZLength < d.TOLERANCE]
    try:
        orient.rest_between(box, *opposite)
    except orient.OrientError as error:
        expect("opposite" in str(error), "two faces pointing opposite ways are refused: %s" % error)
    else:
        raise AssertionError("two opposite faces were accepted")

    # An L profile rounded in its inner corner: the part cannot rest on a hollow.
    notched = box.cut(Part.makeBox(BOX_SIDE / 2, BOX_SIDE, BOX_SIDE / 2, V(BOX_SIDE / 2, 0, BOX_SIDE / 2)))
    inner = [e for e in notched.Edges if abs(e.BoundBox.ZMin - BOX_SIDE / 2) < d.TOLERANCE
             and abs(e.BoundBox.XMin - BOX_SIDE / 2) < d.TOLERANCE and e.BoundBox.YLength > d.TOLERANCE][0]
    hollow = notched.makeFillet(EDGE_ROUND, [inner])
    concave = [f for f in hollow.Faces if f.findPlane() is None][0]
    try:
        orient.lay_flat(hollow, concave)
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "an inner fillet cannot carry the part: %s" % error)
    else:
        raise AssertionError("a part was laid onto an inner fillet")
    inner_sides = [f for f in hollow.Faces if f.findPlane() is not None
                   and any(e.isSame(other) for e in f.Edges for other in concave.Edges)
                   and f.BoundBox.ZMin > d.TOLERANCE and f.BoundBox.XMin > d.TOLERANCE]
    try:
        orient.rest_between(hollow, *inner_sides[:2])
    except orient.OrientError as error:
        expect("cannot rest" in str(error), "the faces of an inner corner cannot carry the part: %s" % error)
    else:
        raise AssertionError("a part was stood between the faces of an inner corner")


def check_thickness():
    """1 mm up to 100 mm of height, then 1 mm per 100 mm, never thinner than two beads."""
    p = FinParams()
    base_height = d.FIN_THICKNESS_BASE_HEIGHT
    expect(math.isclose(geometry.thickness_for(p, base_height), d.FIN_THICKNESS_BASE)
           and math.isclose(geometry.thickness_for(p, 2 * base_height), 2 * d.FIN_THICKNESS_BASE),
           "the fin is 1 mm thick up to 100 mm and grows in proportion above")
    wide = FinParams(nozzle_diameter=WIDE_NOZZLE, bead_width=WIDE_BEAD)
    expect(math.isclose(geometry.thickness_for(wide, base_height), d.FIN_MIN_BEADS * WIDE_BEAD),
           "with wide beads the fin is at least two beads thick")


def check_one_corner(cube, face):
    """One fin on the left or the right end of the face, its tine flush with that end."""
    frame = geometry.frame_of(cube, face)
    for placement, end in ((d.PLACEMENT_CORNER_LEFT, frame.along_min), (d.PLACEMENT_CORNER_RIGHT, frame.along_max)):
        result = geometry.build(cube, face, FinParams(placement=placement))
        ts = [v.Point.dot(frame.along) for tine in result.tines for v in tine.Vertexes]
        flush = min(ts) if placement == d.PLACEMENT_CORNER_LEFT else max(ts)
        expect(len(result.fins.Solids) == 1 and abs(flush - end) < d.TOLERANCE,
               "%s gives one fin, its tine flush with that end of the face" % placement)


def check_tine_clearance(cube, face):
    """Tines end the clearance short of the face; the fin moves out as far, so
    the tines keep their length and the slicer still prints them."""
    clearance = d.GAP / 2
    touching = geometry.build(cube, face, FinParams())
    result = geometry.build(cube, face, FinParams(tine_clearance=clearance))
    distances = [tine.distToShape(face)[0] for tine in result.tines]
    expect(all(abs(distance - clearance) < d.TOLERANCE for distance in distances),
           "every tine ends %.3f mm short of the face: %s" % (clearance, distances))
    expect(all(abs(body.distToShape(face)[0] - (d.GAP + clearance)) < d.TOLERANCE for body in result.bodies),
           "the fin stands the gap plus the clearance from the face")
    expect(not result.warnings and abs(result.tines[0].Volume - touching.tines[0].Volume) < d.TOLERANCE,
           "the tines keep their length")
    try:
        FinParams(tine_clearance=-clearance).validate()
    except ParamError as error:
        expect("tine_clearance" in str(error), "a negative clearance is refused: %s" % error)
    else:
        raise AssertionError("a negative tine clearance was accepted")


def check_shortened(cube, face):
    """A fin whose top tine finds a hole ends at the tine below; a fin height given by hand stays."""
    frame = geometry.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    full = geometry.build(cube, face, FinParams())
    top_tine = full.tine_z[-1] + FinParams().tine_height / 2
    middle = (frame.along_min + frame.along_max) / 2
    on_face = frame.point(middle, frame.s_face(top_tine), top_tine)
    holed = cube.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_face - normal * RECESS_RADIUS, normal))
    holed_face = lower_left_face(holed)
    shortened = geometry.build(holed, holed_face, FinParams())
    expect(math.isclose(shortened.height, full.tine_z[-2] + FinParams().tine_height),
           "the fin ends at its highest tine left, %.2f mm" % shortened.height)
    kept = geometry.build(holed, holed_face, FinParams(fin_height=full.height))
    expect(math.isclose(kept.height, full.height), "a fin height given by hand is kept")


def check_split_face():
    """A groove across the front splits it into two faces in one plane. The fin
    reaches over the gap and carries both; the tines over the gap are left out."""
    box = Part.makeBox(30, 20, 20)
    grooved = box.cut(Part.makeBox(30, GROOVE_DEPTH, GROOVE_WIDTH, V(0, 0, GROOVE_FROM)))
    edge = [e for e in grooved.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    standing = moved(grooved, orient.tilt(grooved, edge, d.TILT_ANGLE))
    front = [f for f in standing.Faces if f.findPlane() is not None
             and abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6 and abs(f.normalAt(0, 0).y) > 0.5]
    pieces = [f for f in front if abs(f.normalAt(0, 0).dot(f.Vertexes[0].Point)
                                      - front[0].normalAt(0, 0).dot(front[0].Vertexes[0].Point)) < d.TOLERANCE]
    lower = min(pieces, key=lambda f: f.BoundBox.ZMin)
    upper = max(pieces, key=lambda f: f.BoundBox.ZMin)
    expect(len(geometry.support_of(standing, lower).Faces) == 2, "the two faces beside the groove form one support")
    result = geometry.build(standing, lower, FinParams())
    expect(max(result.tine_z) > upper.BoundBox.ZMin and any("recess" in w for w in result.warnings),
           "the fin reaches over the groove to the upper face, the tines over it are named: %s" % result.warnings)
    carried = geometry.support_of(standing, lower).Faces
    hanging = overhang.overhangs(standing, supported=carried)
    expect(not any(standing.Faces[n - 1].isSame(upper) for n in hanging),
           "the face above the groove counts as supported")

    # Where fins over the groove would run into the part, they stand under the
    # selected face alone and carry only that one.
    reaching = geometry._build

    def running_into_part(part, face, support, p, tine_count, left_out, shifts, heights):
        if support is not face:
            raise geometry.FinError("runs into the part")
        return reaching(part, face, support, p, tine_count, left_out, shifts, heights)

    geometry._build = running_into_part
    try:
        alone = geometry.build(standing, lower, FinParams())
    finally:
        geometry._build = reaching
    expect(len(alone.carried) == 1 and alone.carried[0].isSame(lower) and max(alone.tine_z) < upper.BoundBox.ZMin
           and any("runs into the part" in w for w in alone.warnings),
           "fins that cannot reach over the groove stand under the selected face alone, and say why")

    # Pieces beside each other along the face are faces of their own: the legs of
    # a U profile, the halves beside an upright slot. The fin stays under the
    # selected one, as without any other face in the plane.
    wide = Part.makeBox(WIDE_BOX, 20, 20)
    for name, cutter in (("U profile", Part.makeBox(WIDE_BOX / 3, 10, 20, V(WIDE_BOX / 3, 0, 0))),
                         ("upright slot", Part.makeBox(GROOVE_WIDTH, GROOVE_DEPTH, 20,
                                                       V(WIDE_BOX / 2, 0, 0)))):
        cut = wide.cut(cutter)
        bottom = max((e for e in cut.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE),
                     key=lambda e: e.Length)
        stood = moved(cut, orient.tilt(cut, bottom, d.TILT_ANGLE))
        side = [f for f in stood.Faces if f.findPlane() is not None
                and abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6 and f.normalAt(0, 0).y < -0.5]
        chosen = min(side, key=lambda f: f.BoundBox.XMin)
        alone = geometry.frame_of(stood, chosen)
        built = geometry.build(stood, chosen, FinParams())
        expect(len(geometry.support_of(stood, chosen).Faces) == 1
               and all(alone.along_min - d.TOLERANCE <= t <= alone.along_max for t in built.positions),
               "%s: the fin stays under the selected face" % name)
def check_quick_fins():
    """Quick fins: the face that takes fins best after standing on an edge, and
    the orientation that makes a chosen face lean over the bed."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    bottom = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    standing = moved(box, orient.tilt(box, bottom, d.TILT_ANGLE))
    best = geometry.best_face(standing, p)
    leaning = [f for f in standing.Faces if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6]
    expect(standing.Faces[best].Area == max(f.Area for f in leaning),
           "after standing on an edge the largest leaning face takes the fins")

    front = [i for i, f in enumerate(box.Faces) if f.BoundBox.YMax < d.TOLERANCE][0]
    change, edge = geometry.stand_for_face(box, front, p, d.TILT_ANGLE)
    leant = moved(box, change)
    expect(abs(leant.Faces[front].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6 and abs(edge.Length - 30) < d.TOLERANCE,
           "a chosen face is turned to lean 45 degrees over the bed, standing on its longest edge")
    expect(abs(resting_height(leant)) < d.TOLERANCE, "the part turned for that face rests on the bed")

    disc = Part.makeCylinder(10, 5)
    top = [i for i, f in enumerate(disc.Faces) if f.findPlane() is not None and f.BoundBox.ZMin > 5 - d.TOLERANCE][0]
    try:
        geometry.stand_for_face(disc, top, p, d.TILT_ANGLE)
    except geometry.FinError as error:
        expect("cannot stand" in str(error), "a face without a straight edge is refused: %s" % error)
    else:
        raise AssertionError("a round face was stood on an edge")


def check_quick_plan():
    """Quick fins with the tilt edge, a chamfer or a fillet chosen."""
    p = FinParams()
    box = Part.makeBox(30, 20, 20)
    front = [i for i, f in enumerate(box.Faces) if f.BoundBox.YMax < d.TOLERANCE][0]
    short = [e for e in box.Faces[front].Edges if abs(e.Length - 20) < d.TOLERANCE][0]
    plan = geometry.quick_plan(box, [(short, None)], [(box.Faces[front], front)], p, d.TILT_ANGLE)
    stood = moved(box, plan.change)
    on_it = [e for e in stood.Edges if abs(e.Length - 20) < d.TOLERANCE and e.BoundBox.ZMax < d.TOLERANCE]
    expect(plan.number == front and on_it and abs(stood.Faces[front].normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6,
           "a face with one of its edges stands on that edge, the face leaning 45 degrees")
    other = [e for e in box.Edges if not any(e.isSame(x) for x in box.Faces[front].Edges)][0]
    try:
        geometry.quick_plan(box, [(other, None)], [(box.Faces[front], front)], p, d.TILT_ANGLE)
    except orient.OrientError as error:
        expect("not an edge" in str(error), "an edge of another face is refused: %s" % error)
    else:
        raise AssertionError("an edge of another face was taken")

    bottom_front = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE]
    chamfered = box.makeChamfer(EDGE_ROUND, bottom_front)
    side = [i for i, f in enumerate(chamfered.Faces) if f.BoundBox.YMax < d.TOLERANCE and f.BoundBox.ZLength > 10][0]
    bevel = [i for i, f in enumerate(chamfered.Faces) if abs(f.normalAt(0, 0).z + math.sqrt(0.5)) < 1e-6][0]
    plan = geometry.quick_plan(chamfered, [], [(chamfered.Faces[side], side), (chamfered.Faces[bevel], bevel)],
                               p, d.TILT_ANGLE)
    resting = moved(chamfered, plan.change)
    expect(plan.number == side and abs(resting.Faces[bevel].normalAt(0, 0).z + 1) < 1e-6,
           "a face, then a chamfer beside it: the part rests on the chamfer, fins under the face")
    alone = geometry.quick_plan(chamfered, [], [(chamfered.Faces[bevel], bevel)], p, d.TILT_ANGLE)
    expect(geometry.is_chamfer(chamfered, chamfered.Faces[bevel]) and alone.number != bevel
           and abs(moved(chamfered, alone.change).Faces[bevel].normalAt(0, 0).z + 1) < 1e-6,
           "a chamfer alone, however wide, carries the part instead of taking the fins")
    expect(not geometry.is_chamfer(box, box.Faces[front]), "a side of a box is no chamfer")
    uneven = box.makeChamfer(EDGE_ROUND, 2 * EDGE_ROUND, bottom_front)
    slope = [f for f in uneven.Faces if f.findPlane() is not None and -0.99 < f.normalAt(0, 0).z < -0.01
             and -0.99 < f.normalAt(0, 0).y < -0.01]
    expect(len(slope) == 1 and geometry.is_chamfer(uneven, slope[0]),
           "a chamfer of unequal widths, not at 45 degrees, is a chamfer too")

    filleted = box.makeFillet(EDGE_ROUND, bottom_front)
    fillet = [i for i, f in enumerate(filleted.Faces) if f.findPlane() is None][0]
    plan = geometry.quick_plan(filleted, [], [(filleted.Faces[fillet], fillet)], p, d.TILT_ANGLE)
    expect(abs(resting_height(moved(filleted, plan.change))) < d.TOLERANCE and plan.number != fillet,
           "a fillet alone carries the part, the fins go under a leaning face")
    beside = [i for i, f in enumerate(filleted.Faces) if f.findPlane() is not None
              and any(e.isSame(x) for e in f.Edges for x in filleted.Faces[fillet].Edges)
              and abs(f.normalAt(0, 0).x) < d.TOLERANCE]
    plan = geometry.quick_plan(filleted, [], [(filleted.Faces[i], i) for i in beside], p, d.TILT_ANGLE)
    expect(len(plan.beside) == 2 and abs(resting_height(moved(filleted, plan.change))) < d.TOLERANCE,
           "the two faces beside a fillet carry the part")


def check_left_out(cube, face):
    """Fins removed by hand are not built; the others stay where they were."""
    three = FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    whole = geometry.build(cube, face, three)
    middle_gone = geometry.build(cube, face, three, left_out=(2,))
    expect(whole.numbers == [1, 2, 3] and middle_gone.numbers == [1, 3]
           and middle_gone.positions == [whole.positions[0], whole.positions[2]],
           "the middle fin removed by hand leaves the outer two where they were")
    try:
        geometry.build(cube, face, three, left_out=(1, 2, 3))
    except geometry.FinError as error:
        expect("every fin is removed" in str(error), "removing every fin is refused: %s" % error)
    else:
        raise AssertionError("fins were built with every fin removed")


def check_moved_fins(cube, face):
    """Fins moved along the face and set to their own height by hand."""
    three = FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    whole = geometry.build(cube, face, three)
    moved_one = geometry.build(cube, face, three, shifts={1: SHIFT})
    edge = whole.edges[1]
    expect(abs(edge.z - whole.heights[1] / 2) < d.TOLERANCE
           and whole.bodies[0].distToShape(Part.Vertex(edge))[0] < d.TOLERANCE,
           "the handles go on the middle of the upright outer edge of the fin: %s" % edge)
    expect(abs(moved_one.starts[1] - (whole.starts[1] + SHIFT)) < d.TOLERANCE
           and moved_one.starts[2] == whole.starts[2],
           "a fin moved by hand moves alone, the others stay")
    try:
        gap = whole.starts[2] - whole.starts[1]
        geometry.build(cube, face, three, shifts={1: gap})
    except geometry.FinError as error:
        expect("closer than" in str(error), "a fin moved onto its neighbour is refused: %s" % error)
    else:
        raise AssertionError("a fin was moved onto its neighbour")
    try:
        geometry.build(cube, face, three, shifts={1: 2 * gap})
    except geometry.FinError as error:
        expect("would pass" in str(error), "a fin moved past its neighbour is refused: %s" % error)
    else:
        raise AssertionError("a fin was moved past its neighbour")
    low = whole.tine_z[0] + FinParams().tine_height
    lowered = geometry.build(cube, face, three, heights={2: low})
    middle = lowered.bodies[1].BoundBox
    expect(abs(middle.ZMax - low) < d.TOLERANCE and abs(lowered.bodies[0].BoundBox.ZMax - whole.height) < d.TOLERANCE,
           "a fin set lower by hand stands at its own height, the others keep theirs")
    try:
        geometry.build(cube, face, three, heights={2: whole.tine_z[0] / 2})
    except geometry.FinError as error:
        expect("lower than its first tine" in str(error), "a fin below its first tine is refused: %s" % error)
    else:
        raise AssertionError("a fin lower than its first tine was built")


def check_recesses(cube, face):
    """Tines over a recess or a hole in the face are left out with a warning;
    a fin none of whose tines finds the face is left out as well."""
    frame = geometry.frame_of(cube, face)
    normal = face.normalAt(0, 0)
    middle = (frame.along_min + frame.along_max) / 2
    middle_z = geometry.build(cube, face, FinParams()).tine_z[1]
    middle_tine = middle_z + FinParams().tine_height / 2

    on_face = frame.point(middle, frame.s_face(middle_tine), middle_tine)
    pit = Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, on_face - normal * RECESS_RADIUS, normal)
    pitted = cube.cut(pit)
    result = geometry.build(pitted, lower_left_face(pitted), FinParams())
    named = "tines at %.1f mm" % middle_z
    expect(len(result.tines) == 2 and any(named in w for w in result.warnings),
           "the tine over a hole in the face is left out, the warning names its height: %s" % result.warnings)
    left_out = result.dropped[0].BoundBox.Center.z if len(result.dropped) == 1 else None
    expect(left_out is not None and abs(left_out - middle_tine) < FinParams().tine_height,
           "the tine left out is handed back as a shape, for the red mark")

    # A hole under only half of the tine: it would hang free there, so it is left out too.
    beside = frame.point(middle + RECESS_RADIUS, frame.s_face(middle_tine), middle_tine)
    half = cube.cut(Part.makeCylinder(RECESS_RADIUS, 2 * RECESS_RADIUS, beside - normal * RECESS_RADIUS, normal))
    partly = geometry.build(half, lower_left_face(half), FinParams())
    expect(len(partly.tines) == 2, "a tine only partly over a hole is left out as well")

    # A groove running up the face under the middle one of three fins: that fin has no tine left.
    uphill = (UP - normal * UP.dot(normal)).normalize()
    three = FinParams(placement=d.PLACEMENT_DISTRIBUTED, fin_count=3)
    spread = geometry.build(cube, face, three)
    centre = geometry.tine_start(three, spread.positions[1], spread.thickness) + three.tine_width / 2

    def groove(t):
        start = frame.point(t, frame.s_face(frame.bed_z), frame.bed_z) - uphill * RECESS_RADIUS
        # It stops below the top of the face, so the face stays one piece. The
        # start lies one radius below the bed, which the length makes up for.
        length = (frame.face_top_z - frame.bed_z - GROOVE_TOP_GAP) / uphill.z + RECESS_RADIUS
        return Part.makeCylinder(RECESS_RADIUS, length, start, uphill)

    grooved = cube.cut(groove(centre))
    two_left = geometry.build(grooved, lower_left_face(grooved), three)
    named = "fins at %.1f mm" % (spread.positions[1] + spread.thickness / 2 - frame.along_min)
    expect(len(two_left.positions) == 2 and any(named in w for w in two_left.warnings),
           "a fin over a groove is left out, the warning names where it stood: %s" % two_left.warnings)

    centred = cube.cut(groove(middle))
    try:
        geometry.build(centred, lower_left_face(centred), FinParams(placement=d.PLACEMENT_CENTER))
    except geometry.FinError as error:
        expect("no tine finds" in str(error), "a fin with no tine on the face at all is refused: %s" % error)
    else:
        raise AssertionError("fins were built although no tine finds the face")


def check_overhangs(cube, face):
    """Overhang detection on simple and less simple bodies."""
    expect(overhang.overhangs(Part.makeBox(30, 10, 10)) == [], "a box lying on the bed has no overhang")
    found = overhang.overhangs(cube, [face])
    expect(found == [], "the reference cube with a fin has no overhang: %s" % found)

    upright = Part.makeCylinder(5, 20)
    expect(overhang.overhangs(upright) == [], "an upright cylinder has no overhang")
    lying = Part.makeCylinder(5, 20, V(0, 0, 5), V(1, 0, 0))
    curved = [i for i, f in enumerate(lying.Faces, 1) if f.findPlane() is None]
    expect(overhang.overhangs(lying) == curved, "a cylinder on its side overhangs with its curved face")

    expect(overhang.overhangs(pyramid(PYRAMID_STEEP)) == [], "a pyramid on its base has no overhang")
    flat = pyramid(PYRAMID_FLAT, apex_down=True)
    sides = overhang.overhangs(flat)
    expect(len(sides) == 4, "a flat pyramid on its apex overhangs with all four sides: %s" % sides)
    edge = pyramid(PYRAMID_BASE / 2, apex_down=True)
    expect(overhang.overhangs(edge) == [], "sides at exactly %.0f degrees do not count" % d.OVERHANG_ANGLE)
    supported = [flat.Faces[i - 1] for i in sides[:2]]
    expect(len(overhang.overhangs(flat, supported)) == 2, "faces carried by fins do not count")

    try:
        geometry.build(lying, lying.Faces[curved[0] - 1], FinParams())
    except geometry.FinError as error:
        expect("not planar" in str(error), "fins under a curved face are refused: %s" % error)
    else:
        raise AssertionError("fins were built under a curved face")
    try:
        orient.tilt(upright, upright.Edges[0], d.TILT_ANGLE)
    except orient.OrientError as error:
        expect("straight" in str(error), "a cylinder cannot stand on its round edge: %s" % error)
    else:
        raise AssertionError("a cylinder was stood on its round edge")

    # Tilted less than the limit, the base still lies too flat; a fin under it settles that.
    standing = pyramid(PYRAMID_STEEP)
    base_edge = [e for e in standing.Edges if e.BoundBox.ZMax < d.TOLERANCE][0]
    standing.Placement = orient.tilt(standing, base_edge, PYRAMID_TILT).multiply(standing.Placement)
    expect(abs(standing.BoundBox.ZMin) < d.TOLERANCE, "a pyramid stands on a base edge")
    base = [i for i, f in enumerate(standing.Faces, 1) if len(f.Edges) == 4]
    expect(overhang.overhangs(standing) == base, "tilted by %.0f degrees its base overhangs" % PYRAMID_TILT)
    expect(overhang.overhangs(standing, [standing.Faces[base[0] - 1]]) == [],
           "with a fin under the base the tilted pyramid has no overhang")


def main():
    cube = tilted_cube()
    face = lower_left_face(cube)

    separate = geometry.build(cube, face, FinParams())
    expect(separate.tine_z == [1.0, 6.0, 11.0], "tines at 1, 6 and 11 mm: %s" % separate.tine_z)
    expect(math.isclose(separate.height, 11.2), "fin height ends on the top tine")
    expect(len(separate.positions) == 1, "one fin on a 20 mm face")
    expect(math.isclose(separate.thickness, d.FIN_THICKNESS_BASE), "a fin below 100 mm is 1 mm thick")
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

    # Tines need a free layer between them, or they merge or round onto one layer.
    params = FinParams()
    least = params.tine_height + params.layer_height
    try:
        FinParams(tine_spacing=params.layer_height / 4).validate()
    except ParamError as error:
        expect("free layer" in str(error), "tines closer than a free layer are refused: %s" % error)
    else:
        raise AssertionError("tines on top of each other were accepted")
    FinParams(tine_spacing=least).validate()
    expect(True, "tines one free layer apart are accepted")

    # A first tine set by hand half a layer off the grid: rounding must not
    # bring two tines closer than a free layer.
    frame = geometry.frame_of(cube, face)
    for offset in HALF_LAYER_STARTS:
        tall = FinParams(tine_layers=2, tine_first=offset)
        tall = FinParams(tine_layers=2, tine_first=offset, tine_spacing=tall.least_tine_spacing)
        zs = geometry.tine_heights(tall, frame, 0)[0]
        gap = min(b - a for a, b in zip(zs, zs[1:]))
        expect(gap > tall.least_tine_spacing - d.TOLERANCE,
               "first tine at %.1f mm: rounding keeps a free layer between tines (%.2f mm)" % (offset, gap))

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
    check_overhangs(cube, face)
    check_recesses(cube, face)
    check_frustum()
    check_loft()
    check_chamfer_and_fillet()
    check_tight_bounds()
    check_thickness()
    check_one_corner(cube, face)
    check_tine_clearance(cube, face)
    check_shortened(cube, face)
    check_split_face()
    check_quick_fins()
    check_quick_plan()
    check_left_out(cube, face)
    check_moved_fins(cube, face)
    print("all checks passed", file=sys.__stdout__)


run(main)
