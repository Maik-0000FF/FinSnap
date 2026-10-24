"""The parametric object and the 3MF export, without the GUI.

Run from the repository root:
    freecad --console tests/test_feature.py
"""

import os
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
from support import expect, lower_left_face, run, tilted_cube  # noqa: E402
from freecad.finsnap import defaults as d  # noqa: E402
from freecad.finsnap import export_3mf, feature, geometry, orient  # noqa: E402
from freecad.finsnap.params import FinParams  # noqa: E402
from freecad.finsnap.shapes import global_shape, outermost  # noqa: E402

V = App.Vector
# The version as package.xml states it, read independently of the workbench.
PACKAGE_XML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "package.xml")
PACKAGE_VERSION = ET.parse(PACKAGE_XML).getroot().findtext("{https://wiki.freecad.org/Package_Metadata}version")
BOX = (40.0, 20.0, 20.0)
XY_PLANE = 3  # index in the origin features of a Body
XZ_PLANE = 4  # index in the origin features of a Body
# A T standing on its stem, in sketch coordinates: stem 10 wide and 20 high,
# arms reaching 10 to each side.
T_PROFILE = [V(10, 0, 0), V(20, 0, 0), V(20, 20, 0), V(30, 20, 0), V(30, 30, 0), V(0, 30, 0),
             V(0, 20, 0), V(10, 20, 0)]
T_DEPTH = 10.0
T_TILT = 30.0  # flatter than the overhang limit, so the stem overhangs too
TAPER_SQUARE = 20.0
TAPER_HEIGHT = 15.0
TAPER_ANGLE = -20.0  # negative: the Pad widens


def face_name(shape, face):
    for i, candidate in enumerate(shape.Faces, 1):
        if candidate.isSame(face):
            return "Face%d" % i
    raise AssertionError("face not found")


def padded_box_in_body(doc):
    """A Pad in a Body keeps local coordinates; the fins must follow the tilted Body."""
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = [(body.Origin.OriginFeatures[XY_PLANE], "")]
    sketch.MapMode = "FlatFace"
    length, width, height = BOX
    corners = [V(0, 0, 0), V(length, 0, 0), V(length, width, 0), V(0, width, 0)]
    for i, corner in enumerate(corners):
        sketch.addGeometry(Part.LineSegment(corner, corners[(i + 1) % len(corners)]))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = height
    doc.recompute()

    shape = global_shape(pad)
    edge = [e for e in shape.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.Length == length][0]
    owner = outermost(pad)
    owner.Placement = orient.tilt(shape, edge, d.TILT_ANGLE).multiply(owner.Placement)
    doc.recompute()
    expect(owner is body, "tilting a Pad moves its Body")

    tilted = global_shape(pad)
    leaning = [i for i, f in enumerate(tilted.Faces, 1) if f.normalAt(0, 0).z < -d.TOLERANCE
               and abs(f.normalAt(0, 0).y) > d.TOLERANCE]
    fins = feature.create(pad, "Face%d" % leaning[0])
    doc.recompute()
    expect(fins.Shape.Solids and fins.Shape.common(tilted).Volume < d.TOLERANCE,
           "fins on a Pad face follow the tilted Body")

    moved = body.Placement
    moved.Base = moved.Base + V(0, 0, 5)
    body.Placement = moved
    doc.recompute()
    expect(abs(fins.Shape.BoundBox.ZMin - 5) < d.TOLERANCE,
           "moving the Body rebuilds the fins (lowest point %.3f)" % fins.Shape.BoundBox.ZMin)


def t_profile_in_part(doc):
    """A nested part: a Pad with a T profile in a Body in a Part container.

    The arms of the T overhang flat; fins under one arm carry it, the other
    stays reported. Stand on edge moves the outermost container.
    """
    container = doc.addObject("App::Part", "Assembly")
    body = doc.addObject("PartDesign::Body", "TBody")
    container.addObject(body)
    sketch = body.newObject("Sketcher::SketchObject", "TSketch")
    sketch.AttachmentSupport = [(body.Origin.OriginFeatures[XZ_PLANE], "")]
    sketch.MapMode = "FlatFace"
    for i, corner in enumerate(T_PROFILE):
        sketch.addGeometry(Part.LineSegment(corner, T_PROFILE[(i + 1) % len(T_PROFILE)]))
    pad = body.newObject("PartDesign::Pad", "TPad")
    pad.Profile = sketch
    pad.Length = T_DEPTH
    doc.recompute()

    shape = global_shape(pad)
    arms = [i for i, f in enumerate(shape.Faces, 1) if f.normalAt(0, 0).z < -1 + d.TOLERANCE
            and f.BoundBox.ZMin > shape.BoundBox.ZMin + d.TOLERANCE]
    expect(len(arms) == 2, "the T has two arms facing down")
    expect(feature.overhangs_of(pad, doc) == ["Face%d" % i for i in arms], "both arms are reported as overhangs")

    edge = [e for e in shape.Edges if e.BoundBox.ZMax < d.TOLERANCE and abs(e.Length - T_DEPTH) < d.TOLERANCE][0]
    owner = outermost(pad)
    owner.Placement = orient.stand(shape, edge, T_TILT).multiply(owner.Placement)
    doc.recompute()
    expect(owner is container, "tilting a nested Pad moves the outermost container")
    tilted = global_shape(pad)
    expect(abs(tilted.BoundBox.ZMin) < d.TOLERANCE, "the nested part rests on the bed after the tilt")

    hanging = feature.overhangs_of(pad, doc)
    expect(len(hanging) == 3, "tilted by %.0f degrees the stem and both arms overhang: %s" % (T_TILT, hanging))
    stem = min(hanging, key=lambda name: tilted.getElement(name).BoundBox.ZMin)
    fins = feature.create(pad, stem)
    doc.recompute()
    expect(fins.Shape.Solids, "fins stand under the stem of the nested part")
    expect(sorted(fins.Overhangs) == sorted(n for n in hanging if n != stem),
           "the stem with fins is no longer reported, the arms still are: %s" % fins.Overhangs)
    expect(any("overhang" in w for w in fins.Warnings), "the fins warn about the arms")


def tapered_pad(doc):
    """A frustum made with Pad and a taper angle: its sides are flat B-spline
    faces that narrow towards one end. Stood on any edge, every face that leans
    over the bed takes fins; tines where a face is too narrow are left out."""
    body = doc.addObject("PartDesign::Body", "TaperBody")
    sketch = body.newObject("Sketcher::SketchObject", "TaperSketch")
    sketch.AttachmentSupport = [(body.Origin.OriginFeatures[XY_PLANE], "")]
    sketch.MapMode = "FlatFace"
    side = TAPER_SQUARE
    corners = [V(0, 0, 0), V(side, 0, 0), V(side, side, 0), V(0, side, 0)]
    for i, corner in enumerate(corners):
        sketch.addGeometry(Part.LineSegment(corner, corners[(i + 1) % len(corners)]))
    pad = body.newObject("PartDesign::Pad", "TaperPad")
    pad.Profile = sketch
    pad.Length = TAPER_HEIGHT
    pad.TaperAngle = TAPER_ANGLE
    doc.recompute()

    shape = global_shape(pad)
    failures, left_out = [], 0
    for face in shape.Faces:
        for edge in face.Edges:
            stood = shape.copy()
            stood.Placement = orient.stand(shape, edge, d.TILT_ANGLE, face).multiply(stood.Placement)
            for leaning in stood.Faces:
                if leaning.normalAt(0, 0).z > -d.MIN_NORMAL_COMPONENT or leaning.BoundBox.ZMax < d.TOLERANCE:
                    continue
                try:
                    result = geometry.build(stood, leaning, FinParams())
                except geometry.FinError as error:
                    failures.append(str(error))
                else:
                    left_out += any("left out" in w for w in result.warnings)
    expect(not failures, "a tapered Pad takes fins under every leaning face, on any edge: %s" % failures[:3])
    expect(left_out, "tines under the narrow end of a face are left out with a warning")


def main():
    doc = App.newDocument("FinSnapTest")
    cube = doc.addObject("Part::Feature", "Cube")
    cube.Shape = tilted_cube()
    name = face_name(cube.Shape, lower_left_face(cube.Shape))

    fins = feature.create(cube, name)
    doc.recompute()
    expect(fins.Shape.Solids, "the object has a shape after recompute")
    expect(fins.ResultFinCount == 1, "result shows one fin")
    expect(abs(fins.ResultHeight.Value - 11.2) < d.TOLERANCE, "result shows the fin height")

    fins.Connection = d.CONNECTION_MERGED
    doc.recompute()
    expect(len(fins.Shape.Solids) == 1, "merged connection gives one solid")
    fins.Connection = d.CONNECTION_SEPARATE
    doc.recompute()

    path = os.path.join(tempfile.mkdtemp(), "finsnap.3mf")
    export_3mf.write(path, [("cube", cube.Shape), ("cube_fins", fins.Shape)])
    with zipfile.ZipFile(path) as archive:
        model = archive.read("3D/3dmodel.model").decode()
    expect(model.count("<object ") == 2, "3MF holds two objects")
    expect('name="cube_fins"' in model, "objects keep their names")
    from freecad.finsnap.version import application, version
    expect(version() == PACKAGE_VERSION, "the workbench reads its version from package.xml")
    expect('<metadata name="Application">%s</metadata>' % application() in model,
           "the 3MF names FinSnap and its version")
    expect('<metadata name="CreationDate">' in model, "the 3MF carries its creation date")
    padded_box_in_body(doc)
    t_profile_in_part(doc)
    tapered_pad(doc)
    print("all checks passed", file=sys.__stdout__)


run(main)
