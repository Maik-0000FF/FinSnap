# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The parametric object and the 3MF export, without the GUI.

Run in FreeCAD, with this checkout installed as an addon (see CONTRIBUTING.md):
    freecad --console freecad/finsnap/tests/test_feature.py
"""

import os
import sys
import tempfile
# Audited: Parses package.xml and files the tests wrote.
import xml.etree.ElementTree as ET  # nosec B405
import zipfile

import FreeCAD as App
import Part
from freecad.finsnap.tests.support import STANDARD_THICKNESS, expect, lower_left_face, run, split_cylinder, tilted_cube
from freecad.finsnap import defaults as d
from freecad.finsnap import export_3mf, export_step, feature, geometry, orient
from freecad.finsnap import presets
from freecad.finsnap.params import FinParams, ParamError
from freecad.finsnap.paths import PACKAGE_XML
from freecad.finsnap.shapes import global_shape, outermost

V = App.Vector
# The version as package.xml states it, read independently of the workbench.
# Audited: package.xml of this repository.
PACKAGE_ROOT = ET.parse(PACKAGE_XML).getroot()  # nosec B314
PACKAGE_VERSION = PACKAGE_ROOT.findtext("{https://wiki.freecad.org/Package_Metadata}version")
BOX = (40.0, 20.0, 20.0)
XY_PLANE = 3  # index in the origin features of a Body
FIN_SHIFT = 1.5  # how far a fin is moved along the face by hand, in mm
MANY_FIN_WIDTHS = 3  # far enough to run a fin into its neighbour
XZ_PLANE = 4  # index in the origin features of a Body
# A T standing on its stem, in sketch coordinates: stem 10 wide and 20 high,
# arms reaching 10 to each side.
T_PROFILE = [V(10, 0, 0), V(20, 0, 0), V(20, 20, 0), V(30, 20, 0), V(30, 30, 0), V(0, 30, 0),
             V(0, 20, 0), V(10, 20, 0)]
T_DEPTH = 10.0
# Flatter than the overhang limit: the stem of the T overhangs too, and of a
# box stood on an edge one face overhangs.
FLAT_TILT = 30.0
TAPER_SQUARE = 20.0
TAPER_HEIGHT = 15.0
TAPER_ANGLE = -20.0  # negative: the Pad widens
SHORT_TINE_GAP = 0.2  # tines shorter than TINE_MIN_LENGTH_BEADS beads
# A block with a pocket offset around an ellipse (major and minor radius).
BLOCK = (30.0, 20.0, 10.0)
POCKET_ELLIPSE = (8.0, 4.0)
POCKET_OFFSET = 1.5
POCKET_DEPTH = 4.0
STEP_VOLUME_TOLERANCE = 1e-3  # mm3, what reading the file back may differ by
TUBE_RADIUS = 10.0
TUBE_BORE = 6.0
TUBE_HEIGHT = 40.0
TUBE_TURN = 5.0  # how far the fin under the side of a tube is moved by hand, in mm round it
FINE_TURN = 1.23456789  # a turn finer than the shift is kept, in mm round the side
EXACT_DISTANCE = 1e-9  # how far a point of the tube may move and it still stands alike, in mm


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
    owner.Placement = orient.stand(shape, edge, FLAT_TILT).multiply(owner.Placement)
    doc.recompute()
    expect(owner is container, "tilting a nested Pad moves the outermost container")
    tilted = global_shape(pad)
    expect(abs(tilted.BoundBox.ZMin) < d.TOLERANCE, "the nested part rests on the bed after the tilt")

    hanging = feature.overhangs_of(pad, doc)
    expect(len(hanging) == 3, "tilted by %.0f degrees the stem and both arms overhang: %s" % (FLAT_TILT, hanging))
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
    failures, left_out, fixed_checked = [], 0, False
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
                    narrow = any("narrower" in w for w in result.warnings)
                    left_out += narrow
                    if narrow and not fixed_checked:
                        # The same face with every tine asked for by number: still built, with the warning.
                        frame = geometry.frame_of(stood, leaning)
                        asked = len(geometry.tine_heights(FinParams(), frame, 0)[0])
                        fixed = geometry.build(stood, leaning, FinParams(tine_count=asked))
                        fixed_checked = any("narrower" in w for w in fixed.warnings)
    expect(not failures, "a tapered Pad takes fins under every leaning face, on any edge: %s" % failures[:3])
    expect(left_out, "tines under the narrow end of a face are left out with a warning")
    expect(fixed_checked, "with a fixed tine count the narrow face is built as well, with the warning")


def lost_face(doc):
    """Fins whose face the part has lost do not stop the other fins of that part."""
    part = doc.addObject("Part::Feature", "LostFacePart")
    part.Shape = tilted_cube()
    name = face_name(part.Shape, lower_left_face(part.Shape))
    kept = feature.create(part, name)
    lost = feature.create(part, name)
    lost.Base = (part, ["Face%d" % (len(part.Shape.Faces) + 1)])
    doc.recompute()
    expect(kept.isValid() and kept.Shape.Solids and not lost.isValid(),
           "fins on a face the part no longer has fail alone, the others are still built")
    for obj in (lost, kept, part):
        doc.removeObject(obj.Name)


def marks_without_face(doc):
    """Fins that lose their face still mark the overhangs of the part as it is now."""
    part = doc.addObject("Part::Feature", "MarkedPart")
    box = Part.makeBox(*BOX)
    edge = [e for e in box.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.Length == BOX[0]][0]

    def standing(angle):
        shape = box.copy()
        shape.Placement = orient.tilt(box, edge, angle).multiply(shape.Placement)
        return shape

    part.Shape = standing(FLAT_TILT)
    steep = [i for i, f in enumerate(part.Shape.Faces, 1) if -0.6 < f.normalAt(0, 0).z < -0.4][0]
    fins = feature.create(part, "Face%d" % steep)
    doc.recompute()
    expect(fins.Overhangs, "tilted flat, the other face overhangs: %s" % fins.Overhangs)
    part.Shape = standing(d.TILT_ANGLE)
    fins.Base = (part, ["Face%d" % (len(part.Shape.Faces) + 1)])
    doc.recompute()
    expect(not fins.isValid() and fins.Overhangs == [],
           "with its face lost the fins fail, and the marks follow the part: %s" % fins.Overhangs)
    for obj in (fins, part):
        doc.removeObject(obj.Name)


def edit_fins(doc):
    """Single fins are picked by a face, removed, brought back; the counter fin
    is added and removed."""
    part = doc.addObject("Part::Feature", "EditedPart")
    part.Shape = tilted_cube()
    fins = feature.create(part, face_name(part.Shape, lower_left_face(part.Shape)))
    fins.FinPlacement = d.PLACEMENT_DISTRIBUTED
    fins.FinCount = 3
    doc.recompute()
    expect(list(fins.FinTags) == ["main:1", "main:2", "main:3"], "each fin solid knows its fin: %s" % fins.FinTags)
    middle = fins.Shape.Solids[1].Faces[0]
    picked = [i for i, f in enumerate(fins.Shape.Faces, 1) if f.isSame(middle)][0]
    expect(feature.fin_at(fins, "Face%d" % picked) == (feature.MAIN, 2), "a face picked on the middle fin finds it")
    feature.remove_fin(fins, feature.MAIN, 2)
    doc.recompute()
    expect(fins.ResultFinCount == 2 and list(fins.FinTags) == ["main:1", "main:3"],
           "the removed fin is gone, the others stay")
    feature.reset_fins(fins)
    doc.recompute()
    expect(fins.ResultFinCount == 3, "removed fins come back")
    from freecad.finsnap.i18n import translate
    feature.remove_fin(fins, feature.MAIN, 2)
    fins.FinCount = 2
    doc.recompute()
    expect(fins.ResultFinCount == 2 and not feature.removed(fins, feature.MAIN)
           and translate("FinSnap", feature.NOTE_EDITS_DROPPED) in fins.Warnings,
           "with another number of fins the removed ones come back, and a note says so")
    fins.FinCount = 3
    doc.recompute()
    before = fins.Shape.Solids[0].BoundBox
    feature.shift_fin(fins, feature.MAIN, 1, FIN_SHIFT)
    feature.set_fin_height(fins, feature.MAIN, 3, fins.Shape.Solids[2].BoundBox.ZLength / 2)
    doc.recompute()
    after = fins.Shape.Solids[0].BoundBox
    expect(fins.ResultFinCount == 3 and abs(after.Center.sub(before.Center).Length - FIN_SHIFT) < d.TOLERANCE,
           "a fin moved by hand stands that far along the face")
    expect(feature.edits(fins, feature.MAIN)[2].keys() == {3}, "a fin keeps a height of its own: %s"
           % (feature.edits(fins, feature.MAIN),))
    feature.shift_fin(fins, feature.MAIN, 1, -FIN_SHIFT)
    expect(not feature.edits(fins, feature.MAIN)[1], "moved back to where it was planned, the shift is gone")
    # A shift that no longer fits once the count changes is dropped with the others, not refused.
    feature.shift_fin(fins, feature.MAIN, 2, fins.ResultThickness.Value * MANY_FIN_WIDTHS)
    fins.FinCount = 2
    doc.recompute()
    expect(fins.ResultFinCount == 2 and feature.edits(fins, feature.MAIN) == ([], {}, {})
           and translate("FinSnap", feature.NOTE_EDITS_DROPPED) in fins.Warnings,
           "a fin moved onto its neighbour is dropped with the count, as the other changes are")
    fins.FinCount = 3
    doc.recompute()
    fins.FinCount = 2
    doc.recompute()
    expect(feature.edits(fins, feature.MAIN) == ([], {}, {}),
           "with another number of fins the heights of their own are dropped as well")
    fins.FinCount = 3
    doc.recompute()
    feature.add_counter(fins)
    doc.recompute()
    expect(any(tag.startswith(feature.COUNTER) for tag in fins.FinTags), "a counter fin is added and tagged")
    feature.remove_counter(fins)
    doc.recompute()
    expect(not fins.CounterFace and not any(tag.startswith(feature.COUNTER) for tag in fins.FinTags),
           "the counter fin is removed")
    # A counter fin moved to another face loses its changes by hand there.
    feature.add_counter(fins)
    feature.shift_fin(fins, feature.COUNTER, 1, FIN_SHIFT)
    feature.add_counter(fins, part, fins.Base[1][0])
    expect(feature.edits(fins, feature.COUNTER) == ([], {}, {}),
           "a counter fin moved to another face starts without changes by hand")
    feature.remove_counter(fins)
    doc.recompute()
    for obj in (fins, part):
        doc.removeObject(obj.Name)


def saved_standard(doc):
    """The standard for new fins: saved values, built-in ones, and what does not fit."""
    expect(presets.standard() == FinParams(), "without a saved standard new fins start with the built-in values")
    thin = FinParams(fin_thickness=STANDARD_THICKNESS, placement=d.PLACEMENT_CORNERS)
    presets.save(thin)
    expect(presets.standard() == thin, "a saved standard comes back as it was saved")
    box = doc.addObject("Part::Feature", "StandardBox")
    box.Shape = tilted_cube()
    fins = feature.create(box, face_name(box.Shape, lower_left_face(box.Shape)))
    expect(abs(fins.FinThickness.Value - STANDARD_THICKNESS) < d.TOLERANCE
           and fins.FinPlacement == d.PLACEMENT_CORNERS, "new fins start with the saved standard")
    doc.removeObject(fins.Name)
    doc.removeObject(box.Name)

    group = App.ParamGet("%s/%s" % (presets.PREFERENCES, presets.STANDARD_GROUP))
    group.RemFloat("fin_thickness")
    group.SetString("fin_thickness", "thin")
    expect(presets.standard().fin_thickness == FinParams().fin_thickness
           and presets.standard().placement == d.PLACEMENT_CORNERS,
           "a field saved with another type falls back to its built-in value, the rest stays")
    group.SetString("placement", "nowhere")
    expect(presets.standard() == FinParams(), "saved values that do not validate give the built-in standard")
    try:
        presets.save(FinParams(gap=0.0))
    except ParamError:
        pass
    else:
        raise AssertionError("an invalid standard was saved")
    presets.reset()
    expect(presets.standard() == FinParams(), "factory settings bring back the built-in standard")


def warnings_and_old_files(doc):
    """Each warning names the fin it is about; a file from before a parameter
    existed gets it with its built-in value."""
    from freecad.finsnap.i18n import translate
    cube = doc.addObject("Part::Feature", "WarnedCube")
    cube.Shape = tilted_cube()
    main_face = lower_left_face(cube.Shape)
    fins = feature.create(cube, face_name(cube.Shape, main_face))
    # Removing several fins at once, as the Delete key does.
    feature.add_counter(fins)
    doc.recompute()
    every_main = [(feature.MAIN, n) for n in (1, 2, 3)]
    expect(feature.remove_fins(fins, every_main + [(feature.COUNTER, 1)]) is True
           and feature.edits(fins, feature.MAIN) == ([], {}, {}) and fins.CounterFace,
           "removing every main fin changes nothing and asks for the object to be deleted")
    expect(feature.remove_fins(fins, [(feature.MAIN, 2), (feature.MAIN, 2), (feature.COUNTER, 1)]) is False
           and feature.removed(fins, feature.MAIN) == [2] and not fins.CounterFace,
           "one main fin and the only counter fin: that fin left out, the counter fin dropped")
    expect(feature.remove_fins(fins, []) is False and feature.removed(fins, feature.MAIN) == [2],
           "nothing picked changes nothing")
    feature.reset_fins(fins)
    doc.recompute()
    # Saved before the count was kept: changes stay, and a failing build says why.
    feature.remove_fin(fins, feature.MAIN, 2)
    fins.removeProperty(feature.EDITED_OF[feature.MAIN])
    fins.FinCount = 2
    doc.recompute()
    expect(feature.removed(fins, feature.MAIN) == [2] and fins.ResultFinCount == 1,
           "without the count they were made for, changes by hand stay")
    feature.remove_fin(fins, feature.MAIN, 1)
    fins.removeProperty(feature.EDITED_OF[feature.MAIN])
    doc.recompute()
    expect("every fin is removed" in fins.getStatusString() or
           translate("FinSnap", "every fin is removed; delete the fins instead, or bring them back")
           in fins.getStatusString(),
           "without the count, a build that fails says why: %s" % fins.getStatusString())
    fins.FinCount = 3
    feature.reset_fins(fins)
    feature.remove_fin(fins, feature.MAIN, 1)
    fins.removeProperty(feature.EDITED_OF[feature.MAIN])
    fins.addProperty("App::PropertyInteger", feature.REMOVED_OF[feature.MAIN])
    setattr(fins, feature.REMOVED_OF[feature.MAIN], 3)
    fins.Proxy.onDocumentRestored(fins)
    expect(getattr(fins, feature.EDITED_OF[feature.MAIN], None) == 3
           and feature.REMOVED_OF[feature.MAIN] not in fins.PropertiesList,
           "a file from when fins could only be removed keeps the count they were removed from")
    feature.reset_fins(fins)
    doc.recompute()
    feature.add_counter(fins)
    # A gap this narrow makes the tines of both fins short, so both warn.
    fins.Gap = SHORT_TINE_GAP
    doc.recompute()
    main_prefix = translate("FinSnap", "Main fin: %s") % ""
    counter_prefix = translate("FinSnap", "Counter fin: %s") % ""
    expect(any(w.startswith(main_prefix) for w in fins.Warnings)
           and any(w.startswith(counter_prefix) for w in fins.Warnings),
           "warnings say whether they are about the main or the counter fin: %s" % list(fins.Warnings))

    fins.removeProperty("TineClearance")
    fins.Proxy.onDocumentRestored(fins)
    expect("TineClearance" in fins.PropertiesList and fins.TineClearance.Value == d.TINE_CLEARANCE,
           "fins saved before the tine clearance existed get it, touching as before")


def step_with_offset_curves():
    """A pocket whose outline runs at a distance around an ellipse has edges on
    offset curves. Written plainly, those faces do not come back from the STEP
    file and the slicer drops the whole part; the export has to bring it back."""
    rim = Part.Face(Part.Wire(Part.Ellipse(V(0, 0, 0), *POCKET_ELLIPSE).toShape())).makeOffset2D(POCKET_OFFSET)
    block = Part.makeBox(*BLOCK, V(-BLOCK[0] / 2, -BLOCK[1] / 2, 0))
    pocketed = block.cut(rim.extrude(V(0, 0, BLOCK[2])).translated(V(0, 0, BLOCK[2] - POCKET_DEPTH)))
    expect(pocketed.isValid() and any(isinstance(e.Curve, Part.OffsetCurve) for e in pocketed.Edges),
           "the pocketed block is a valid solid with edges on offset curves")
    folder = tempfile.mkdtemp()
    for meshed in (False, True):
        if meshed:
            # The 3MF export meshes the same shape first. On a PartDesign part
            # with pockets through a chamfer that broke the STEP export; this
            # block does not show it, so the case only guards the order.
            export_3mf.write(os.path.join(folder, "pocketed.3mf"), [("pocketed", pocketed)])
        path = os.path.join(folder, "pocketed.step")
        export_step.write(path, [("pocketed", pocketed)])
        back = Part.read(path)
        after = ", also after a 3MF export" if meshed else ""
        expect(len(back.Solids) == 1 and abs(back.Volume - pocketed.Volume) < STEP_VOLUME_TOLERANCE,
               "the STEP export brings the pocketed block back whole%s" % after)


def split_tube(doc):
    """A tube whose side and rims a STEP file split in halves: its rim stands
    it, and fins under half its side are built under the whole side, named on
    the tube by both halves."""
    shape = split_cylinder(TUBE_RADIUS, TUBE_HEIGHT, TUBE_BORE)
    tube = doc.addObject("Part::Feature", "SplitTube")
    tube.Shape = shape
    arc = next(i for i, e in enumerate(shape.Edges, 1) if orient.is_piece(e)
               and abs(e.Curve.Radius - TUBE_RADIUS) < d.TOLERANCE)
    joined, (rim,), name_of = feature.whole_elements(tube, ["Edge%d" % arc])
    plan = geometry.quick_plan(joined, [(rim, None)], [], FinParams(), d.TILT_ANGLE)
    tube.Placement = plan.change
    fins = feature.create(tube, name_of(plan.number))
    doc.recompute()
    halves = [i for i, f in enumerate(tube.Shape.Faces, 1) if isinstance(f.Surface, Part.Cylinder)
              and abs(f.Surface.Radius - TUBE_RADIUS) < d.TOLERANCE]
    expect(orient.is_rim(rim) and fins.ResultFinCount == 1 and fins.isValid() and feature.on_round_side(fins)
           and sorted(fins.CarriedFaces) == sorted("Face%d" % i for i in halves),
           "a split tube stands on its rim, one fin under its side, carried by both halves: %s" % fins.CarriedFaces)
    feature.set_round_shift(fins, TUBE_TURN)
    doc.recompute()
    expect(abs(feature.round_shift(fins) - TUBE_TURN) < d.TOLERANCE and fins.isValid(),
           "the fin under the split side turns the tube as under a whole one")
    doc.removeObject(fins.Name)
    doc.removeObject(tube.Name)
    doc.recompute()


def turned_tube(doc):
    """A fin under the side of a tube moved by hand turns the tube about its
    axis; the fin stays under the lowest line, and the turn is undone again."""
    tube = Part.makeCylinder(TUBE_RADIUS, TUBE_HEIGHT).cut(Part.makeCylinder(TUBE_BORE, TUBE_HEIGHT))
    side = [i for i, f in enumerate(tube.Faces)
            if orient.is_round_side(f) and abs(f.Surface.Radius - TUBE_RADIUS) < d.TOLERANCE][0]
    plan = geometry.quick_plan(tube, [], [(tube.Faces[side], side)], FinParams(), d.TILT_ANGLE)
    part = doc.addObject("Part::Feature", "Tube")
    part.Shape = tube
    part.Placement = plan.change
    fins = feature.create(part, "Face%d" % (side + 1))
    doc.recompute()
    standing = App.Placement(part.Placement)
    fin_box = fins.Shape.BoundBox
    expect(fins.ResultFinCount == 1 and feature.on_round_side(fins), "a tube stood on its rim takes one fin")

    feature.set_round_shift(fins, TUBE_TURN)
    doc.recompute()
    turned = part.Placement.multiply(standing.inverse()).Rotation.Angle
    expect(abs(turned - TUBE_TURN / TUBE_RADIUS) < 1e-6 and feature.round_shift(fins) == TUBE_TURN,
           "moving the fin %.0f mm turns the tube by that much round its side" % TUBE_TURN)
    expect(fins.Shape.BoundBox.isInside(fin_box.Center) and abs(fins.Shape.BoundBox.XLength - fin_box.XLength)
           < d.TOLERANCE and abs(fins.Shape.BoundBox.YLength - fin_box.YLength) < d.TOLERANCE,
           "the fin stays under the lowest line")
    feature.set_round_shift(fins, 0.0)
    doc.recompute()
    expect(part.Placement.isSame(standing, d.TOLERANCE) and not feature.round_shift(fins),
           "moved back, the tube stands as before")
    # A turn finer than the shift is kept: the part turns by the kept shift,
    # so turned back it stands exactly where it stood.
    feature.set_round_shift(fins, FINE_TURN)
    feature.set_round_shift(fins, 0.0)
    # Measured on the outer rim, a tube radius from its axis in its own
    # coordinates, where the turn shows as a distance; an angle this small
    # rounds away in the rotation.
    probe = App.Vector(TUBE_RADIUS, 0, 0)
    drift = (part.Placement.multVec(probe) - standing.multVec(probe)).Length
    expect(drift < EXACT_DISTANCE,
           "turned finer than the shift is kept and back, the tube stands exactly as before: %r mm" % drift)
    # A change smaller than the tolerance is neither turned nor kept, so none
    # adds up unturned.
    feature.set_round_shift(fins, TUBE_TURN)
    turned = App.Placement(part.Placement)
    feature.set_round_shift(fins, TUBE_TURN + d.TOLERANCE / 2)
    expect(feature.round_shift(fins) == TUBE_TURN and part.Placement.isSame(turned, EXACT_DISTANCE),
           "a change below the tolerance neither turns the tube nor is kept")
    feature.set_round_shift(fins, 0.0)

    side_name = "Face%d" % (side + 1)
    try:
        feature.add_counter(fins, part, side_name)
    except geometry.FinError as error:
        expect("counter fin goes under a flat face" in str(error) and not fins.CounterFace,
               "a counter fin chosen under the side of a tube is refused, nothing changed: %s" % error)
    else:
        raise AssertionError("a counter fin was added under the side of a tube")
    count = len(doc.Objects)
    try:
        feature.create(part, side_name, (part, side_name))
    except geometry.FinError as error:
        expect("counter fin goes under a flat face" in str(error) and len(doc.Objects) == count,
               "fins made with a counter fin under the side of a tube are refused, nothing made: %s" % error)
    else:
        raise AssertionError("fins were made with a counter fin under the side of a tube")
    stood = part.Shape
    up = max((i for i, f in enumerate(stood.Faces) if f.findPlane() is not None),
             key=lambda i: stood.Faces[i].CenterOfMass.z)
    try:
        feature.create(part, side_name, (part, "Face%d" % (up + 1)))
    except geometry.FinError as error:
        expect(len(doc.Objects) == count,
               "fins made with a counter face facing up are refused, nothing made: %s" % error)
    else:
        raise AssertionError("fins were made with a counter face facing up")
    # Set some other way, as an older file may have it: left out with a note,
    # the main fin still built.
    fins.CounterFace = (part, [side_name])
    doc.recompute()
    expect(fins.isValid() and fins.ResultFinCount == 1
           and any("counter fin goes under a flat face" in w for w in fins.Warnings),
           "a counter fin under the side of a tube is left out with a note, the main fin stays")
    fins.CounterFace = None
    doc.recompute()

    feature.set_round_shift(fins, TUBE_TURN)
    # A count of its own, which a build would not give: it has to stay as it is.
    made_for = getattr(fins, feature.PLANNED[feature.MAIN]) + 1
    setattr(fins, feature.EDITED_OF[feature.MAIN], made_for)
    feature.keep_laid_flat(fins, App.Placement())
    expect(not feature.round_shift(fins) and getattr(fins, feature.EDITED_OF[feature.MAIN]) == made_for,
           "laid flat, the fin keeps no turn of the tube, and the count its changes were made for")


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
    saved_standard(doc)
    lost_face(doc)
    marks_without_face(doc)
    edit_fins(doc)
    turned_tube(doc)
    split_tube(doc)
    tapered_pad(doc)
    warnings_and_old_files(doc)
    step_with_offset_curves()
    print("all checks passed", file=sys.__stdout__)


run(main)
