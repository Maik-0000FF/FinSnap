# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The commands as a user runs them, in a FreeCAD with GUI but without a screen.

Run in FreeCAD, with this checkout installed as an addon (see CONTRIBUTING.md):
    QT_QPA_PLATFORM=offscreen freecad freecad/finsnap/tests/test_gui.py

Dialogs that would wait for a click are replaced by fixed answers; everything
else, from the selection to the written file, runs as in FreeCAD.
"""

import math
import os
import sys
import tempfile
import zipfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from PySide import QtWidgets
from freecad.finsnap.tests.support import STANDARD_THICKNESS, expect, lower_left_face, run, tilted_cube

WORKBENCH = "FinSnapWorkbench"
COMMANDS = ("FinSnap_QuickFins", "FinSnap_Tilt", "FinSnap_LayFlat", "FinSnap_AddFins", "FinSnap_AddCounterFin",
            "FinSnap_CheckStability", "FinSnap_CheckPart", "FinSnap_IslandsWhileEditing", "FinSnap_MeshToSolid",
            "FinSnap_Export3MF", "FinSnap_ExportSTEP", "FinSnap_CheckLimits", "FinSnap_CheckBridges")
DIALOG_ACCEPTED = 1
# Answers to the questions commands ask, taken in order by answer_dialogs().
ANSWERS = []
FLAT_TILT = 30.0  # flatter than the overhang limit
# Up on the screen, in the coordinates of the camera.
SCREEN_UP = App.Vector(0, 1, 0)
ALONG_X = App.Vector(1, 0, 0)
UP = App.Vector(0, 0, 1)
VIEW_SETTINGS = "User parameter:BaseApp/Preferences/View"
NAVIGATION_ANIMATIONS = "UseNavigationAnimations"
CHAMFER = 3.0
QUICK_LENGTH = 80.0  # a face this long gets two fins with automatic placement
THICK_LAYER = 0.3  # a layer height other than the standard, to see the steps follow
FIN_SHIFT = 1.5  # how far a handle moves a fin along the face, in mm
TOO_MANY_FINS = 50  # more fins than the face takes, so the build fails
AXIS_Z_RGB = (0.2, 0.2, 0.8)  # FreeCAD's standard colour of the z axis
COLOR_TOLERANCE = 0.01
BUILD_STEP = 0.5  # how far a fin moves at each step of a counted drag, in mm
# Shares of the step between two tines a fin is dragged down, short of and past half of it.
SHORT_OF_HALF_STEP = 0.4
PAST_HALF_STEP = 0.6
TOO_HIGH = 100.0  # how far an arrow is dragged up, far above any face of the tests, in mm
GERMAN = "FinSnap_de.ts"  # written by freecad/finsnap/tools/update_translations.sh
TUBE_RADIUS = 10.0
TUBE_BORE = 6.0
TUBE_HEIGHT = 40.0
TUBE_ANGLE = 30.0  # how far the fin under the side of a tube is turned in the panel, in degrees
PLACE_STEP = 1.0  # how far a fin is moved along the face in the panel, in mm
ZOOM_OUT = 2.0  # how far the view is zoomed out to see the arc keep its size on the screen
ARROW_SIZE_TOLERANCE = 0.01  # share by which the size of an arrow may differ from the one reckoned
# A box stood this far from the bed, degrees: one face leans between the
# critical and the unprintable limit, the other is steeper than both.
CRITICAL_TILT = 40.0
# Limits raised for the test, so that face lies too flat to print (degrees).
RAISED_CRITICAL, RAISED_UNPRINTABLE = 50.0, 45.0
HOOK_REACH = 15.0  # how far the arm of a hook reaches past the side of the tilted cube, in mm
HOOK_WIDTH = 5.0  # width and thickness of its arm and leg
HOOK_DEPTH = 12.0  # how far below the top of the cube the arm comes out
HOOK_DROP = 15.0  # how far the leg hangs from the arm
ARC_TURN_TOLERANCE = 0.01  # degrees a turn read back from Coin may be off
WHITE_PACKED = 0xFFFFFFFF  # a white background of the 3D view, packed as FreeCAD keeps it
DARK_PACKED = 0x202020FF  # a dark one


def load_workbench():
    # The installed addon registered the workbench when FreeCAD started.
    Gui.activateWorkbench(WORKBENCH)
    from freecad.finsnap import commands
    return commands


def answer_dialogs(commands, save_path, angle):
    """Replace every dialog that waits for the user by a fixed answer."""
    messages = []
    QtWidgets.QDialog.exec = lambda self: DIALOG_ACCEPTED
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (save_path, ""))
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (angle, True))
    # Each question is answered from ANSWERS, in order; an unexpected one fails.
    QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: ANSWERS.pop(0))
    commands._message = messages.append
    return messages


def face_name(obj, face):
    for i, candidate in enumerate(obj.Shape.Faces, 1):
        if candidate.isSame(face):
            return "Face%d" % i
    raise AssertionError("face not found")


def rgb_close(color, wanted):
    """Whether `color`, with or without alpha, is `wanted` in red, green and blue."""
    return all(abs(a - b) < COLOR_TOLERANCE for a, b in zip(color[:3], wanted))


def fin_tinted(obj, fin, tint=None):
    """Whether the faces of `fin` are in `tint`, red without, and every other face green."""
    from freecad.finsnap import feature, handles
    own = set(feature.fin_faces(obj, *fin))
    colors = [material.DiffuseColor for material in obj.ViewObject.ShapeAppearance]
    return bool(own) and len(colors) == len(obj.Shape.Faces) and all(
        rgb_close(color, (tint or handles.INVALID_COLOR) if index in own else handles.VALID_COLOR)
        for index, color in enumerate(colors))


def select(obj, *subs):
    Gui.Selection.clearSelection()
    if subs:
        for sub in subs:
            Gui.Selection.addSelection(obj, sub)
    else:
        Gui.Selection.addSelection(obj)


def moved_beside_groove(doc):
    """A fin planned over a groove stands beside it; typed into its field or
    dragged, it moves on from where it stands, not from where it was planned."""
    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature, geometry, handles
    from freecad.finsnap.taskpanel import FinSnapTaskPanel
    from freecad.finsnap.tests.support import grooved
    cube = tilted_cube()
    face = lower_left_face(cube)
    frame = geometry.frame_of(cube, face)
    part = doc.addObject("Part::Feature", "Grooved")
    part.Shape = grooved(cube, face, (frame.along_min + frame.along_max) / 2)
    fins = feature.create(part, face_name(part, lower_left_face(part.Shape)))
    fins.FinPlacement = d.PLACEMENT_CENTER
    doc.recompute()
    panel = FinSnapTaskPanel(fins)
    panel.handled = (feature.MAIN, 1)
    stood = panel.fin_values()[handles.ALONG]
    moved = fins.Proxy.results[feature.MAIN].moved.get(1)
    expect(moved, "the fin over the groove is moved beside it")
    # On away from the groove, the way it was moved.
    step = math.copysign(PLACE_STEP, moved)
    panel.fin_fields[handles.ALONG].setValue(stood + step)
    panel.field_entered(handles.ALONG)
    typed = panel.fin_values()[handles.ALONG]
    panel.handle_started(handles.ALONG)
    panel.finish_drag(handles.ALONG, step)
    dragged = panel.fin_values()[handles.ALONG]
    expect(abs(typed - stood - step) < d.TOLERANCE and abs(dragged - typed - step) < d.TOLERANCE,
           "typed and dragged, a fin moved beside a groove moves on from where it stands: %.3f, %.3f, %.3f"
           % (stood, typed, dragged))
    panel.reject()
    doc.removeObject(fins.Name)
    doc.removeObject(part.Name)
    doc.recompute()


def quick_on_split_tube(doc):
    """Quick fins on half the side of a tube that a STEP file split in two,
    and on half its rim: it stands on its rim, with its fin under the side."""
    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature, orient
    from freecad.finsnap.tests.support import split_cylinder
    tube = doc.addObject("Part::Feature", "SplitTube")
    tube.Shape = split_cylinder(TUBE_RADIUS, TUBE_HEIGHT, TUBE_BORE)
    flat = App.Placement(tube.Placement)
    for kind, pieces in (("Face", tube.Shape.Faces), ("Edge", tube.Shape.Edges)):
        number = next(i for i, piece in enumerate(pieces, 1) if orient.is_piece(piece)
                      and abs((piece.Surface if kind == "Face" else piece.Curve).Radius - TUBE_RADIUS) < d.TOLERANCE)
        select(tube, "%s%d" % (kind, number))
        Gui.runCommand("FinSnap_QuickFins")
        fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is tube]
        expect(len(fins) == 1 and feature.on_round_side(fins[0]) and fins[0].ResultFinCount == 1,
               "Quick fins on half the %s of a split tube stands it on its rim, its fin under the side"
               % ("side" if kind == "Face" else "rim"))
        fins[0].ViewObject.Proxy.panel.reject()
        doc.recompute()
        expect(tube.Placement.isSame(flat, d.TOLERANCE), "Cancel lays the split tube back as it lay")
    doc.removeObject(tube.Name)
    doc.recompute()


def added_on_tube(doc):
    """Add fins under the side of a tube already standing on its rim, turned
    in the panel: Cancel deletes the fins and turns the tube back."""
    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature, geometry, handles
    from freecad.finsnap.params import FinParams
    shape = Part.makeCylinder(TUBE_RADIUS, TUBE_HEIGHT).cut(Part.makeCylinder(TUBE_BORE, TUBE_HEIGHT))
    side = [i for i, f in enumerate(shape.Faces) if isinstance(f.Surface, Part.Cylinder)
            and abs(f.Surface.Radius - TUBE_RADIUS) < d.TOLERANCE][0]
    tube = doc.addObject("Part::Feature", "AddedTube")
    tube.Shape = shape
    tube.Placement = geometry.quick_plan(shape, [], [(shape.Faces[side], side)], FinParams(), d.TILT_ANGLE).change
    doc.recompute()
    standing = App.Placement(tube.Placement)
    select(tube, "Face%d" % (side + 1))
    Gui.runCommand("FinSnap_AddFins")
    fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is tube][0]
    panel = fins.ViewObject.Proxy.panel
    panel.fin_fields[handles.ALONG].setValue(TUBE_ANGLE)
    panel.field_entered(handles.ALONG)
    turned = not tube.Placement.isSame(standing, d.TOLERANCE)
    name = fins.Name
    panel.reject()
    doc.recompute()
    expect(turned and tube.Placement.isSame(standing, d.TOLERANCE)
           and not [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is tube],
           "Cancel of Add fins on a tube turned in the panel deletes the fins and turns the tube back")
    doc.undo()
    expect(doc.getObject(name) is not None and not tube.Placement.isSame(standing, d.TOLERANCE),
           "one Undo of that Cancel brings the fins back and the tube turned with them")
    doc.removeObject(name)
    doc.removeObject(tube.Name)
    doc.recompute()


def turned_tube(doc):
    """Quick fins on the side of a tube: the fin is first put at 0 degrees of
    the side; its angle typed in the panel, or the arc round the axis dragged,
    turns the tube about its axis, the fin stays under the lowest line; Reset
    fins and Cancel turn it back."""
    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature, geometry, handles
    tube = doc.addObject("Part::Feature", "Tube")
    tube.Shape = Part.makeCylinder(TUBE_RADIUS, TUBE_HEIGHT).cut(Part.makeCylinder(TUBE_BORE, TUBE_HEIGHT))
    side = [i for i, f in enumerate(tube.Shape.Faces, 1) if isinstance(f.Surface, Part.Cylinder)
            and f.Surface.Radius == TUBE_RADIUS][0]
    select(tube, "Face%d" % side)
    Gui.runCommand("FinSnap_QuickFins")
    fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is tube][0]
    panel = fins.ViewObject.Proxy.panel
    standing = App.Placement(tube.Placement)
    fin_middle = fins.Shape.BoundBox.Center

    def turned():
        """How far the tube is turned from where it was stood, the shorter way round, in degrees."""
        degrees = math.degrees(tube.Placement.multiply(standing.inverse()).Rotation.Angle)
        return min(degrees, geometry.FULL_CIRCLE - degrees)

    def angle():
        return panel.fin_values()[handles.ALONG]

    expect(panel.turns_part() and panel.handles.turning(),
           "the fin under the side of a tube turns the tube when moved, by an arc round its axis")
    expect(abs(angle()) < d.TOLERANCE, "the fin is first put at 0 degrees of the side")
    arc = panel.handles
    camera = Gui.ActiveDocument.ActiveView.getCameraNode()
    unit = arc.arc_unit
    camera.height.setValue(camera.height.getValue() * ZOOM_OUT)
    arc._zoomed()
    # The middle of every piece of the shaft, in the arc's own frame about the axis.
    middles = [piece.getChild(0).translation.getValue() for bodies in arc.arc_bodies.values()
               for body in bodies.values() for piece in list(body.getChildren())[:handles.ARC_PIECES]]
    reaches = [math.hypot(x, y) for x, y, _ in middles]
    expect(abs(arc.arc_unit - ZOOM_OUT * unit) < ARROW_SIZE_TOLERANCE * arc.arc_unit
           and max(reaches) - min(reaches) < d.TOLERANCE and max(abs(z) for _, _, z in middles) < d.TOLERANCE
           and min(reaches) > feature.round_side(fins).Surface.Radius,
           "zoomed out, the arc is drawn as large on the screen, round the axis outside the side")
    camera.height.setValue(camera.height.getValue() / ZOOM_OUT)
    arc._zoomed()
    panel.fin_fields[handles.ALONG].setValue(TUBE_ANGLE)
    panel.field_entered(handles.ALONG)
    expect(abs(turned() - TUBE_ANGLE) < d.TOLERANCE and fins.Shape.BoundBox.Center.isEqual(fin_middle, d.TOLERANCE)
           and abs(angle() - TUBE_ANGLE) < d.TOLERANCE,
           "an angle typed for the fin turns the tube that far round its axis, the fin stays")
    arc._held(handles.ALONG, None)
    arc._moved(handles.ALONG, None)
    # A copy: the field gives its own vector, which follows it.
    unturned = coin.SbVec3f(arc.value_at.translation.getValue())
    arc.turner.rotation.setValue(coin.SbRotation(coin.SbVec3f(0, 0, 1), math.radians(-TUBE_ANGLE)))
    arc._moved(handles.ALONG, None)
    expect(_on_arc(arc, unturned) and _on_arc(arc, arc.value_at.translation.getValue())
           and abs(_turned_by(arc, unturned, arc.value_at.translation.getValue()) - TUBE_ANGLE) < ARC_TURN_TOLERANCE,
           "the value of the arc stands past its tip, round the axis, and turns with it")
    expect(abs(panel.fin_fields[handles.ALONG].value() - 2 * TUBE_ANGLE) < d.TOLERANCE,
           "while the arc is dragged, the field shows the angle the fin goes to")
    arc.held = False
    panel.finish_drag(handles.ALONG, arc._mm(handles.ALONG))
    expect(abs(turned() - 2 * TUBE_ANGLE) < d.TOLERANCE and abs(angle() - 2 * TUBE_ANGLE) < d.TOLERANCE,
           "dragging the arc turns the tube further, as near as Coin reads its turn")
    released_without_button(arc, "a tube")
    panel.fin_fields[handles.ALONG].setValue(geometry.FULL_CIRCLE - TUBE_ANGLE)
    panel.field_entered(handles.ALONG)
    expect(abs(turned() - TUBE_ANGLE) < d.TOLERANCE
           and abs(angle() - (geometry.FULL_CIRCLE - TUBE_ANGLE)) < d.TOLERANCE,
           "an angle typed past 0 turns the tube the shorter way round")
    # A build that fails once the tube is turned, which leaves no build behind:
    # the turn is taken back all the same.
    before_failure = App.Placement(tube.Placement)

    def failing():
        fins.Proxy.results = {}
        raise ValueError("a build that fails")

    panel.apply = failing
    panel.fin_fields[handles.ALONG].setValue(TUBE_ANGLE)
    panel.field_entered(handles.ALONG)
    del panel.apply
    panel.preview()
    expect(tube.Placement.isSame(before_failure, d.TOLERANCE),
           "a turn whose build fails is taken back, also with no build left to ask")
    panel.reset()
    expect(tube.Placement.isSame(standing, d.TOLERANCE), "Reset fins turns the tube back")
    panel.fin_fields[handles.ALONG].setValue(TUBE_ANGLE)
    panel.field_entered(handles.ALONG)
    shift = feature.round_shift(fins)
    panel.accept()
    Gui.ActiveDocument.setEdit(fins)
    reopened = fins.ViewObject.Proxy.panel
    reopened.fin_fields[handles.ALONG].setValue(2 * TUBE_ANGLE)
    reopened.field_entered(handles.ALONG)
    reopened.reject()
    expect(abs(turned() - TUBE_ANGLE) < d.TOLERANCE and feature.round_shift(fins) == shift
           and abs(abs(shift) - math.radians(TUBE_ANGLE) * TUBE_RADIUS) < d.TOLERANCE,
           "Cancel turns the tube back to where the panel found it")
    rim = [i for i, e in enumerate(tube.Shape.Edges, 1) if isinstance(e.Curve, Part.Circle)
           and abs(e.Curve.Radius - TUBE_RADIUS) < d.TOLERANCE][0]
    # Quick fins stands the tube anew, which forgets how far it was turned;
    # its Cancel puts the tube back and notes the turn again.
    select(tube, "Edge%d" % rim)
    Gui.runCommand("FinSnap_QuickFins")
    quick = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is tube and o is not fins][0]
    quick.ViewObject.Proxy.panel.reject()
    doc.recompute()
    expect(feature.round_shift(fins) == shift and abs(turned() - TUBE_ANGLE) < d.TOLERANCE,
           "Cancel of Quick fins on the tube keeps how far it was turned for the fins already there")
    select(tube, "Edge%d" % rim)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    expect(not feature.round_shift(fins), "stood anew, the fin forgets how far the tube was turned")
    doc.removeObject(fins.Name)
    doc.removeObject(tube.Name)
    doc.recompute()


def quick_on_pad(doc):
    """Quick fins on a face of a Pad, then another row chosen: the fins stand
    under the face of its Body, which follows the features added after them."""
    from freecad.finsnap import feature
    body = doc.addObject("PartDesign::Body", "QuickBody")
    box = body.newObject("PartDesign::AdditiveBox", "QuickBox")
    doc.recompute()
    side = next(i for i, f in enumerate(box.Shape.Faces, 1) if f.normalAt(0, 0).y < -0.9)
    select(box, "Face%d" % side)
    Gui.runCommand("FinSnap_QuickFins")
    fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is body]
    panel = fins[0].ViewObject.Proxy.panel if fins else None
    # A face of a box stands on any of its edges: a table of at least two ways.
    rows = panel.stand_list.rowCount() if panel is not None and panel.stands is not None else 0
    if rows > 1:
        panel.stand_list.setCurrentCell(1, 0)
    expect(rows > 1 and fins[0].Base[0] is body and fins[0].isValid() and panel.stands.current == 1,
           "Quick fins on a face of a Pad stand the fins under the face of its Body, also after another row: %d"
           % rows)
    if fins:
        fins[0].ViewObject.Proxy.panel.reject()
    for name in (box.Name, body.Name):
        doc.removeObject(name)


def checked_on_switch(doc):
    """Quick fins with the checks while editing off lists its ways unchecked;
    switched on, they are rated in place, the row standing still marked, and
    the fins are rebuilt with the checks."""
    from freecad.finsnap import feature
    box = doc.addObject("Part::Feature", "Unchecked")
    box.Shape = Part.makeBox(30, 20, 20)
    doc.recompute()
    side = next(i for i, f in enumerate(box.Shape.Faces, 1) if f.normalAt(0, 0).y < -0.9)
    Gui.runCommand("FinSnap_IslandsWhileEditing", 0)
    try:
        select(box, "Face%d" % side)
        Gui.runCommand("FinSnap_QuickFins")
        fins = next(o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is box)
        panel = fins.ViewObject.Proxy.panel
        table = panel.stand_list
        panel.stand_list.setCurrentCell(1, 0)
        blank = all(table.item(row, 2).text() == "" for row in range(table.rowCount()))
        Gui.runCommand("FinSnap_IslandsWhileEditing", 1)
        expect(blank and all(table.item(row, 2).text() == "0" for row in range(table.rowCount()))
               and not panel.stands.unrated() and panel.stands.current == 1 and table.currentRow() == 1,
               "the ways found unchecked are rated once the checks are switched on, the row standing kept")
        panel.reject()
    finally:
        Gui.runCommand("FinSnap_IslandsWhileEditing", 1)
    doc.removeObject(box.Name)


def chosen_stands(doc, quick, facing, messages):
    """Quick fins on a face of the box `quick` lying flat: the panel lists the
    edges the part can stand on, a click on a row stands it so, it asks before
    dropping changes by hand, and Cancel lays the part back whichever way it
    stands. The part is cut for its islands once for each way, by Quick
    fins; the fins take them from there, also after a click on a row."""
    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature, orient, overhang, taskpanel
    lying = orient.snapshot(quick)
    select(quick, "Face%d" % facing)
    real, cuts = overhang.islands, []
    overhang.islands = lambda *args: cuts.append(args) or real(*args)
    try:
        Gui.runCommand("FinSnap_QuickFins")
        first_cuts = len(cuts)
        ways = len(quick.Shape.Faces[facing - 1].Edges)
        fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick][0]
        fins.ViewObject.Proxy.panel.stand_list.setCurrentCell(1, 0)
    finally:
        overhang.islands = real
    expect(first_cuts == ways and len(cuts) == first_cuts,
           "Quick fins cuts the part once for each way, the fins take the islands from there, also after a "
           "click on a row: %d, %d" % (first_cuts, len(cuts)))
    fins.ViewObject.Proxy.panel.stand_list.setCurrentCell(0, 0)
    fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick][0]
    panel = fins.ViewObject.Proxy.panel
    face = fins.Base[1][0]
    edges = quick.Shape.Faces[facing - 1].Edges
    table = panel.stand_list if panel.stands is not None else None

    def marked(row):
        return table.currentRow() == row and panel.stands.current == row

    def standing():
        leaning = quick.Shape.Faces[facing - 1].normalAt(0, 0).z
        return (abs(leaning + math.sqrt(0.5)) < d.TOLERANCE and abs(quick.Shape.BoundBox.ZMin) < d.TOLERANCE
                and fins.Base[1][0] == face and fins.isValid() and fins.Shape.Solids)

    lengths = sorted((edge.Length for edge in edges), reverse=True)
    names = ["Edge%d" % i for i, e in enumerate(quick.Shape.Edges, 1) if any(e.isSame(x) for x in edges)]
    expect(not messages and table is not None and table.rowCount() == len(edges) and marked(0)
           and sorted(table.item(row, 0).text() for row in range(len(edges))) == sorted(names)
           and [table.item(row, 1).text() for row in range(len(edges))]
           == ["%.1f%s" % (length, taskpanel.LENGTH_SUFFIX) for length in lengths]
           and all(table.item(row, 2).text() == "0" for row in range(len(edges)))
           and table.columnCount() == len(taskpanel.STAND_HEADERS[True])
           and all(table.item(row, 4).text() == "0" for row in range(len(edges))),
           "after Quick fins on a face the panel lists each edge it can stand on by its name, its length, "
           "no islands, its overhangs and no bridge: %s"
           % messages)
    first = App.Placement(quick.Placement)
    table.setCurrentCell(2, 0)
    expect(not quick.Placement.isSame(first, d.TOLERANCE) and marked(2) and standing(),
           "a click on a row stands the part on that edge, the face leaning 45 degrees, the fins under it")
    feature.shift_fin(fins, feature.MAIN, 1, PLACE_STEP)
    panel.edited()
    before = App.Placement(quick.Placement)
    ANSWERS.append(QtWidgets.QMessageBox.No)
    table.setCurrentCell(1, 0)
    expect(not ANSWERS and quick.Placement.isSame(before, d.TOLERANCE) and marked(2)
           and feature.changed_by_hand(fins), "No to the question keeps the part, the mark and the fin moved by hand")
    ANSWERS.append(QtWidgets.QMessageBox.Yes)
    table.setCurrentCell(0, 0)
    expect(not ANSWERS and quick.Placement.isSame(first, d.TOLERANCE) and marked(0) and standing()
           and not feature.changed_by_hand(fins), "Yes stands the part as in the row clicked, the fins planned anew")
    panel.reject()
    expect(fins.Name not in [o.Name for o in doc.Objects] and quick.Placement.isSame(lying[0], d.TOLERANCE)
           and (orient.FLAT_PLACEMENT in quick.PropertiesList) == lying[1],
           "Cancel after choosing deletes the fins and lays the part back as it was")

    short = [i for i, e in enumerate(quick.Shape.Edges, 1)
             if any(e.isSame(x) for x in quick.Shape.Faces[facing - 1].Edges)][0]
    select(quick, "Face%d" % facing, "Edge%d" % short)
    Gui.runCommand("FinSnap_QuickFins")
    fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick][0]
    expect(fins.ViewObject.Proxy.panel.stands is None, "a face with its edge stands one way: no table to choose from")
    fins.ViewObject.Proxy.panel.reject()


def saved_while_editing():
    """Fins saved with their task panel open are saved as they looked before
    editing, not see-through green; after, they look as while editing again."""
    from freecad.finsnap import commands, feature
    from freecad.finsnap.taskpanel import FinSnapTaskPanel
    doc = App.newDocument("SavedWhileEditing")
    cube = doc.addObject("Part::Feature", "Cube")
    cube.Shape = tilted_cube()
    fins = feature.create(cube, face_name(cube, lower_left_face(cube.Shape)))
    commands.ViewProviderFinSnap(fins.ViewObject)
    doc.recompute()
    before = fins.ViewObject.Transparency
    panel = FinSnapTaskPanel(fins)
    editing = fins.ViewObject.Transparency
    path = os.path.join(tempfile.mkdtemp(), "saved_while_editing.FCStd")
    doc.saveAs(path)
    after = fins.ViewObject.Transparency
    with zipfile.ZipFile(path) as saved:
        gui = saved.read("GuiDocument.xml").decode()
    provider = gui[gui.index('<ViewProvider name="%s"' % fins.Name):]
    provider = provider[:provider.index("</ViewProvider>")]
    stored = provider[provider.index('name="Transparency"'):]
    stored = int(stored[stored.index('value="') + len('value="'):].split('"')[0])
    panel.release_handles()
    App.closeDocument(doc.Name)
    expect(editing != before and stored == before and after == editing,
           "fins saved with the task panel open keep their look from before editing in the file, "
           "and look as while editing after: %s, %s, %s, %s" % (before, editing, stored, after))


def released_without_button(arrows, name):
    """Every arrow of `arrows`, a Handles, that Coin left active after its
    release, moved with no mouse button down, is let go at once, as the
    release would: made inactive, so it follows the mouse no more, its held
    look in its colour at rest, until it is grabbed again. `name` says which
    arrows these are."""
    from freecad.finsnap import handles
    # Grabbing and letting go are noted only: the panel is not drawn into it.
    done, real_start, real_done = [], arrows.on_start, arrows.on_done
    arrows.on_start = lambda kind: None
    arrows.on_done = lambda kind, mm: done.append(kind)
    try:
        for kind in handles.KINDS:
            turning = kind == handles.ALONG and arrows.turning()
            arrow = arrows.turner if turning else arrows.draggers[kind]
            look = arrows.looks[(handles.TURNING, handles.TURN_PARTS[1]) if turning
                                else (kind, handles.TRANSLATE_PARTS[1])]
            del done[:]
            arrows._held(kind, None)
            # As Coin left it after a lost release.
            arrow.isActive.setValue(True)
            # No button is down while the tests run: the move is one without it.
            arrows._dragged(kind, arrow)
            at_rest = coin.SbColor(look.getChild(0).rgb[0])
            arrows._held(kind, None)
            again = coin.SbColor(look.getChild(0).rgb[0])
            arrows.held = False
            expect(not arrow.isActive.getValue() and done == [kind]
                   and rgb_close(at_rest.getValue(), arrows._rest_color(kind))
                   and rgb_close(again.getValue(), handles.HELD_COLOR),
                   "%s, %s: moved with no button down, let go at once, inactive, in its colour at rest until "
                   "grabbed again" % (name, "arc" if turning else kind))
    finally:
        arrows.on_start, arrows.on_done = real_start, real_done


def value_colors():
    """The value of a dragged arrow is written yellow over a dark background
    of the 3D view, nearly black over a light one, a gradient by the mean of
    its colours, its middle colour as well where that is on. Every setting
    the cases depend on is set here, so FreeCAD's own make no difference,
    and put back as it was after."""
    from freecad.finsnap import handles
    view = App.ParamGet(handles.VIEW_PARAMETERS)
    flags = [name for name, _ in handles.BACKGROUND_FLAGS] + [handles.BACKGROUND_USE_MIDDLE[0]]
    colors = [handles.BACKGROUND_SINGLE[0], handles.BACKGROUND_MIDDLE[0]] + [
        name for name, _ in handles.BACKGROUND_GRADIENT]
    had_bools, had_colors = set(view.GetBools()), set(view.GetUnsigneds())
    saved_bools = {name: view.GetBool(name) for name in flags if name in had_bools}
    saved_colors = {name: view.GetUnsigned(name) for name in colors if name in had_colors}
    gradient, _, middle = flags
    try:
        for flag in flags:
            view.SetBool(flag, False)
        view.SetUnsigned(handles.BACKGROUND_SINGLE[0], WHITE_PACKED)
        on_white = handles.value_color()
        view.SetUnsigned(handles.BACKGROUND_SINGLE[0], DARK_PACKED)
        on_dark = handles.value_color()
        view.SetBool(gradient, True)
        for name, _ in handles.BACKGROUND_GRADIENT:
            view.SetUnsigned(name, WHITE_PACKED)
        on_light_gradient = handles.value_color()
        # A dark middle colour pulls the mean of a light gradient below the limit.
        view.SetUnsigned(handles.BACKGROUND_GRADIENT[1][0], DARK_PACKED)
        view.SetUnsigned(handles.BACKGROUND_MIDDLE[0], DARK_PACKED)
        view.SetBool(middle, True)
        through_dark_middle = handles.value_color()
    finally:
        for name in flags:
            if name in saved_bools:
                view.SetBool(name, saved_bools[name])
            else:
                view.RemBool(name)
        for name in colors:
            if name in saved_colors:
                view.SetUnsigned(name, saved_colors[name])
            else:
                view.RemUnsigned(name)
    expect(on_white == handles.VALUE_ON_LIGHT and on_dark == handles.HELD_COLOR
           and on_light_gradient == handles.VALUE_ON_LIGHT and through_dark_middle == handles.HELD_COLOR,
           "the value is written nearly black over a light background, yellow over a dark one, a gradient "
           "by the mean of its colours, its middle colour too where it is on")


def _on_arc(arc, point):
    """Whether `point` (an SbVec3f) lies on the circle the arc of `arc`, a
    Handles, is drawn round."""
    from freecad.finsnap import defaults as d
    foot, turn = arc.turn_place.translation.getValue(), arc.turn_place.rotation.getValue()
    axis = turn.multVec(coin.SbVec3f(0, 0, 1))
    off = point - foot
    return abs((off - axis * off.dot(axis)).length() - arc.arc_radius) < d.TOLERANCE


def _turned_by(arc, start, end):
    """How far round the axis of the arc of `arc` `end` lies from `start` (degrees)."""
    foot, turn = arc.turn_place.translation.getValue(), arc.turn_place.rotation.getValue()
    axis = turn.multVec(coin.SbVec3f(0, 0, 1))
    first, second = start - foot, end - foot
    first, second = first - axis * first.dot(axis), second - axis * second.dot(axis)
    return math.degrees(math.acos(max(-1.0, min(1.0, first.dot(second) / (first.length() * second.length())))))


def _value_shown(arrows):
    """The value standing at the dragged arrow of `arrows`, a Handles; None
    while none is shown."""
    if arrows.value.whichChild.getValue() == coin.SO_SWITCH_NONE:
        return None
    found = coin.SoSearchAction()
    found.setType(coin.SoText2.getClassTypeId())
    found.apply(arrows.value)
    path = found.getPath()
    return None if path is None else path.getTail().string[0]


def _balls(marks, over=False):
    """How many balls the Coin node `marks` holds; with `over`, only those
    drawn over everything else, in an SoAnnotation."""
    found = coin.SoSearchAction()
    found.setType(coin.SoSphere.getClassTypeId())
    found.setInterest(coin.SoSearchAction.ALL)
    found.apply(marks)
    paths = found.getPaths()
    annotation = coin.SoAnnotation.getClassTypeId()
    return sum(1 for i in range(paths.getLength())
               if not over or any(paths[i].getNode(j).isOfType(annotation) for j in range(paths[i].getLength())))


def _layer_marked(marks):
    """Whether the Coin node `marks` holds a mark in the red a fin shows where
    it cannot stand, as see-through as islands are drawn: the first layer of an
    island."""
    from freecad.finsnap import handles
    found = coin.SoSearchAction()
    found.setType(coin.SoMaterial.getClassTypeId())
    found.setInterest(coin.SoSearchAction.ALL)
    found.apply(marks)
    paths = found.getPaths()
    materials = [paths[i].getTail() for i in range(paths.getLength())]
    return any(rgb_close(material.diffuseColor[0].getValue(), handles.INVALID_COLOR)
               and abs(material.transparency[0] - handles.ISLAND_TRANSPARENCY) < COLOR_TOLERANCE
               for material in materials)


def bridges_checked(doc, messages):
    """Check bridges from the toolbar: the bridge of a slab across a gap is
    said and kept as a check of its own, which shows it on the underside."""
    from freecad.finsnap import check, limits, taskpanel
    width, depth, height, gap, slab = 5.0, 10.0, 10.0, 8.0, 2.0
    part = doc.addObject("Part::Feature", "Bridged")
    part.Shape = Part.makeBox(width, depth, height).fuse(
        [Part.makeBox(width, depth, height, App.Vector(width + gap, 0, 0)),
         Part.makeBox(2 * width + gap, depth, slab, App.Vector(0, 0, height))]).removeSplitter()
    doc.recompute()
    select(part)
    Gui.runCommand("FinSnap_CheckBridges")
    spanned = check.find(part, check.BRIDGES)
    expect(spanned is not None and not spanned.CriticalBridges.isNull() and taskpanel.check_nodes(spanned)
           and "%.1f" % limits.current().bridge_critical in messages[-1],
           "Check bridges says the bridge of the part and keeps it as a check, shown on the underside: %s"
           % messages[-1])
    doc.removeObject(spanned.Name)
    doc.removeObject(part.Name)


def limits_page(doc):
    """The page of the limits in the preferences fills them by strictness and
    keeps them in order, and saved, rebuilds the fins so their marks follow: a
    face rated critical, marked yellow, turns too flat to print, marked red."""
    from freecad.finsnap import commands, feature, handles, limits, orient
    from freecad.finsnap import defaults as d
    from freecad.finsnap.preferences import LimitsPage

    expect(not Gui.getIcon("preferences-finsnap").isNull(),
           "the group of FinSnap in Edit > Preferences has an icon, not a question mark")
    # Check limits in the menu opens the preferences on the page.
    opened = []
    show = Gui.showPreferences
    Gui.showPreferences = lambda *args: opened.append(args)
    try:
        Gui.runCommand("FinSnap_CheckLimits")
    finally:
        Gui.showPreferences = show
    expect(opened == [("FinSnap", 0)], "Check limits opens the preferences on the page of FinSnap: %s" % opened)
    page = LimitsPage()
    page.loadSettings()
    expect(page.shown() == limits.current(), "the page shows the limits saved")
    def strictness():
        return page.strictness.currentData()

    expect(strictness() == limits.NORMAL, "the built-in limits are those of the normal strictness")
    page.fields["overhang_critical"].setValue(limits.Limits().overhang_unprintable - 1)
    expect(page.fields["overhang_unprintable"].value() <= page.fields["overhang_critical"].value()
           and strictness() == limits.CUSTOM,
           "lowering the critical limit takes the unprintable one along, and the limits are custom")
    page.strictness.activated.emit(page.strictness.findData(limits.STRICT))
    expect(page.shown() == limits.STRICTNESS[limits.STRICT] and strictness() == limits.STRICT,
           "choosing strict fills its limits")
    page.strictness.activated.emit(page.strictness.findData(limits.CUSTOM))
    expect(page.shown() == limits.STRICTNESS[limits.STRICT], "choosing custom leaves the limits as they are")
    page.strictness.activated.emit(page.strictness.findData(limits.NORMAL))
    expect(page.shown() == limits.Limits() and strictness() == limits.NORMAL,
           "choosing normal fills the built-in limits")

    box = doc.addObject("Part::Feature", "Rated")
    box.Shape = Part.makeBox(20, 20, 20)
    edge = next(e for e in box.Shape.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE)
    box.Placement = orient.tilt(box.Shape, edge, CRITICAL_TILT)
    doc.recompute()
    leaning = sorted((i for i, f in enumerate(box.Shape.Faces, 1) if f.normalAt(0, 0).z < -d.TOLERANCE
                      and f.BoundBox.ZMax > box.Shape.BoundBox.ZMin + d.TOLERANCE),
                     key=lambda i: -box.Shape.Faces[i - 1].normalAt(0, 0).z)
    fins = feature.create(box, "Face%d" % leaning[0])
    commands.ViewProviderFinSnap(fins.ViewObject)
    doc.recompute()
    marks = fins.ViewObject.Proxy.marks
    expect(fins.Overhangs == ["Face%d" % leaning[1]] and fins.UnprintableOverhangs == []
           and marks.getNumChildren() == 1,
           "the face leaning %.0f degrees from the bed is critical, marked once: %s" % (CRITICAL_TILT, fins.Overhangs))
    try:
        page.fields["overhang_critical"].setValue(RAISED_CRITICAL)
        page.fields["overhang_unprintable"].setValue(RAISED_UNPRINTABLE)
        page.saveSettings()
        expect(limits.current().overhang_unprintable == RAISED_UNPRINTABLE
               and fins.UnprintableOverhangs == fins.Overhangs,
               "saved, the limits rebuild the fins: the face is too flat to print now")
        color = marks.getChild(0).getChild(0).diffuseColor[0].getValue()
        expect(all(abs(a - b) < COLOR_TOLERANCE for a, b in zip(color, handles.OVERHANG_COLORS[limits.UNPRINTABLE])),
               "the face too flat to print is marked red: %s" % (color,))
        expect(strictness() == limits.CUSTOM, "limits set by hand are custom")
    finally:
        limits.reset()
    doc.removeObject(fins.Name)
    doc.removeObject(box.Name)


def island_marks(doc):
    """Fins added by hand to the tilted cube with a hook hanging from its side,
    whose foot would start printing in the air: a warning says so, and the
    island is marked in the 3D view, over the part."""
    from freecad.finsnap import analysis, commands, feature
    from freecad.finsnap import defaults as d
    cube = tilted_cube()
    box = cube.BoundBox
    # An arm out of the cube near its top, and a leg hanging from its far end
    # beside the cube, its foot far above the bed.
    arm = Part.makeBox(box.XMax + HOOK_REACH, HOOK_WIDTH, HOOK_WIDTH, App.Vector(0, 0, box.ZMax - HOOK_DEPTH))
    foot = box.ZMax - HOOK_DEPTH - HOOK_DROP + HOOK_WIDTH
    leg = Part.makeBox(HOOK_WIDTH, HOOK_WIDTH, HOOK_DROP, App.Vector(box.XMax + HOOK_REACH - HOOK_WIDTH, 0, foot))
    hooked = doc.addObject("Part::Feature", "Hooked")
    hooked.Shape = cube.fuse([arm, leg]).removeSplitter()
    fins = feature.create(hooked, face_name(hooked, lower_left_face(hooked.Shape)))
    commands.ViewProviderFinSnap(fins.ViewObject)
    doc.recompute()
    marks = fins.ViewObject.Proxy.marks
    expect(len(fins.Islands) == 1 and abs(fins.Islands[0].z - foot) < d.TOLERANCE
           and any(hooked.Label in warning and warning.startswith("1 ") for warning in fins.Warnings)
           and not fins.IslandLayers.isNull() and abs(fins.IslandLayers.BoundBox.ZMin - foot) < d.TOLERANCE
           and _layer_marked(marks),
           "fins on a part with an island warn of it and show its first layer in the air see-through red: %s, %s"
           % (list(fins.Islands), list(fins.Warnings)))
    expect(_balls(marks) == 0, "an island shown by its first layer has no ball beside it")
    # The kernel failing to cut the first layer out: the island is marked by a
    # ball at its lowest point instead.
    from freecad.finsnap import overhang
    real = overhang._first_layer
    overhang._first_layer = lambda *args: None
    try:
        analysis._kept.clear()
        fins.touch()
        doc.recompute()
    finally:
        overhang._first_layer = real
        analysis._kept.clear()
    expect(len(fins.Islands) == 1 and fins.IslandLayers.isNull() and list(fins.IslandsUncut) == list(fins.Islands)
           and _balls(marks, over=True) == 1,
           "an island whose first layer cannot be cut out is marked by a ball at its lowest point, over the part")
    doc.removeObject(fins.Name)
    doc.removeObject(hooked.Name)


def stability_checked(doc, messages):
    """Check stability and Check part from the toolbar, for a part without
    fins and with, and from the task panel: the result is said and kept as a
    check in the tree, one for each part and kind, which shows it while it is
    up to date; once the part moves it is out of date, its marks gone, and a
    double click checks again. Deleting it removes it; saved, it shows again."""
    from freecad.finsnap import analysis, check, commands, feature, orient, paths, taskpanel
    from freecad.finsnap import defaults as d
    slab = Part.makeBox(30, 20, 10)
    bottom = [e for e in slab.Edges if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    part = doc.addObject("Part::Feature", "Leaning")
    part.Shape = slab
    part.Placement = orient.tilt(slab, bottom, d.TILT_ANGLE)
    doc.recompute()
    del messages[:]
    select(part)
    Gui.runCommand("FinSnap_CheckStability")
    stable = check.find(part, check.STABILITY)
    # What sets the note apart from the others: its words after the height.
    needs_fins = App.Qt.translate("FinSnap", analysis.NOTE_NEEDS_FINS).rsplit("mm)", 1)[1]
    expect(len(messages) == 1 and needs_fins in messages[0] and stable is not None and stable.Result == messages[0]
           and not stable.OutOfDate and isinstance(stable.ViewObject.Proxy, taskpanel.ViewProviderCheck)
           and stable.ViewObject.Proxy.root.getNumChildren() > 0,
           "Check stability says a leaning part without fins tips and keeps it as a check in the tree, shown: %s"
           % messages)
    for selected in (None, doc.addObject("App::DocumentObjectGroup", "NoShape")):
        Gui.Selection.clearSelection()
        if selected is not None:
            select(selected)
        Gui.runCommand("FinSnap_CheckStability")
        expect(messages[-1] == App.Qt.translate("FinSnap", commands.NOTE_SELECT_PART),
               "with nothing selected, or an object without a shape, a part is asked for")
        if selected is not None:
            doc.removeObject(selected.Name)
    del messages[1:]

    fins = feature.create(part, face_name(part, lower_left_face_of(part.Shape)))
    doc.recompute()
    select(fins)
    Gui.runCommand("FinSnap_CheckStability")
    said = messages[-1]
    checks = [obj for obj in doc.Objects if check.is_check(obj)]
    expect(len(messages) == 2 and needs_fins not in said and checks == [stable] and stable.Result == said
           and fins in stable.Fins, "checked again with fins, the same check holds what they do: %s" % said)
    panel = taskpanel.FinSnapTaskPanel(fins)
    panel.check_stability()
    shown = panel.stability.text()
    panel.preview()
    expect(shown == said and panel.stability.text() == App.Qt.translate("FinSnap", taskpanel.NOTE_STABILITY_OUTDATED),
           "the task panel says the same, and once the fins change, that it is out of date")
    panel.release_handles()
    select(part)
    Gui.runCommand("FinSnap_CheckPart")
    whole = check.find(part, check.PART)
    lines = messages[-1].split("\n")
    marks = whole.ViewObject.Proxy.root
    expect(whole is not None and whole is not stable and len(lines) == 5 and messages[-1].endswith(said)
           and _coloured_by_height(marks) and _layer_cut_shown(marks),
           "Check part keeps a check of its own: overhangs, bridges, islands and stability, coloured by height: %s"
           % lines)

    part.Placement = App.Placement(App.Vector(1, 0, 0), App.Rotation()).multiply(part.Placement)
    doc.recompute()
    expect(stable.OutOfDate and whole.OutOfDate and stable.ViewObject.Proxy.root.getNumChildren() == 0
           and stable.ViewObject.Proxy.getIcon() == paths.ICON_CHECK_OUTDATED,
           "once the part moves its checks are out of date, their marks gone, their icon a warning")
    information = QtWidgets.QMessageBox.information
    QtWidgets.QMessageBox.information = staticmethod(lambda *args: messages.append(args[2]))
    proxy = stable.ViewObject.Proxy
    draws, real_draw = [], proxy.draw
    # Noted only where it draws marks, not where it finds the check out of date.
    proxy.draw = lambda: draws.append(not stable.OutOfDate) or real_draw()
    try:
        stable.ViewObject.Proxy.doubleClicked(stable.ViewObject)
    finally:
        QtWidgets.QMessageBox.information = information
        proxy.draw = real_draw
    expect(not stable.OutOfDate and stable.ViewObject.Proxy.root.getNumChildren() > 0
           and messages[-1] == stable.Result and sum(draws) == 1,
           "a double click checks again, draws its marks once, and says what it found: %d" % sum(draws))

    # A copy: the document itself stays as it is, and opens as a second one.
    path = os.path.join(tempfile.mkdtemp(), "checked.FCStd")
    doc.saveCopy(path)
    reopened = App.openDocument(path)
    again = [obj for obj in reopened.Objects if check.is_check(obj)]
    kept = next((obj for obj in again if obj.Kind == check.STABILITY), None)
    expect(len(again) == 2 and kept is not None and kept.Result == stable.Result and not kept.OutOfDate
           and kept.ViewObject.Proxy.root.getNumChildren() > 0,
           "saved and opened again, the checks show as they were")
    App.closeDocument(reopened.Name)
    App.setActiveDocument(doc.Name)
    doc.removeObject(whole.Name)
    expect(check.find(part, check.PART) is None and check.find(part, check.STABILITY) is stable,
           "deleting a check removes it alone")
    Gui.runCommand("FinSnap_IslandsWhileEditing", 0)
    off = analysis.checks_while_editing()
    Gui.runCommand("FinSnap_IslandsWhileEditing", 1)
    expect(not off and analysis.checks_while_editing(),
           "Islands and bridges while editing switches the checks off and on")
    doc.removeObject(fins.Name)
    doc.removeObject(part.Name)
    QtWidgets.QMessageBox.information = staticmethod(lambda *args: messages.append(args[2]))
    try:
        stable.ViewObject.Proxy.doubleClicked(stable.ViewObject)
    finally:
        QtWidgets.QMessageBox.information = information
    expect(messages[-1] == App.Qt.translate("FinSnap", taskpanel.NOTE_PART_GONE),
           "a double click on a check whose part is gone says so")
    doc.removeObject(stable.Name)


def _coloured_by_height(node):
    """Whether `node` colours faces corner by corner, as the part by height."""
    found = coin.SoSearchAction()
    found.setType(coin.SoMaterialBinding.getClassTypeId())
    found.setInterest(coin.SoSearchAction.ALL)
    found.apply(node)
    paths = found.getPaths()
    return any(paths[i].getTail().value.getValue() == coin.SoMaterialBinding.PER_VERTEX
               for i in range(paths.getLength()))


def _layer_cut_shown(node):
    """Whether `node` shows faces drawn over everything else, as the layer cut out."""
    found = coin.SoSearchAction()
    found.setType(coin.SoAnnotation.getClassTypeId())
    found.setInterest(coin.SoSearchAction.ALL)
    found.apply(node)
    paths = found.getPaths()
    faces = coin.SoIndexedFaceSet.getClassTypeId()
    return any(paths[i].getTail().getNumChildren() and paths[i].getTail().getChild(0).getNumChildren() > 3
               and paths[i].getTail().getChild(0).getChild(3).isOfType(faces) for i in range(paths.getLength()))


def lower_left_face_of(shape):
    """The face of `shape` leaning most over the bed, its normal furthest down."""
    return min(shape.Faces, key=lambda face: face.normalAt(*face.ParameterRange[::2]).z)


def check_typed_fields(panel, fins, place):
    """A value typed into a field of the fin with the arrows is taken once
    typing pauses, where the fin can stand, and the field is left as typed;
    Enter takes it at once and leaves the panel open."""
    from PySide import QtCore, QtGui
    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature, handles
    box = panel.fin_fields[handles.ALONG]
    box.setValue(place + FIN_SHIFT)
    expect(panel.field_timer.isActive() and panel.typed_field == handles.ALONG
           and not feature.edits(fins, feature.MAIN)[1], "a place typed waits for typing to pause")
    # What the timer does once typing pauses.
    panel.field_entered(panel.typed_field)
    expect(feature.edits(fins, feature.MAIN)[1] and not panel.field_timer.isActive(),
           "once typing pauses, the place typed moves the fin")
    box.setValue(place)
    # The panel is built here without a task dialog; that Enter reaches none
    # shows in the event being taken.
    taken = []
    for key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier)
        QtWidgets.QApplication.sendEvent(box, event)
        taken.append(event.isAccepted())
    expect(not feature.edits(fins, feature.MAIN)[1] and not panel.field_timer.isActive() and all(taken),
           "Enter takes the place typed at once and is not passed on to close the panel")
    nowhere = place + TOO_HIGH
    box.setValue(nowhere)
    panel.field_entered(panel.typed_field, paused=True)
    expect(not feature.edits(fins, feature.MAIN)[1] and abs(box.value() - nowhere) < d.TOLERANCE
           and not panel.notes.isHidden(),
           "typing paused where the fin cannot stand: nothing moves, the reason shows, the field keeps what is typed")
    panel.field_entered(handles.ALONG)
    expect(abs(box.value() - place) < d.TOLERANCE,
           "left where the fin cannot stand, the field shows where it stands again")
    box.setValue(place + FIN_SHIFT)
    panel.handle_started(handles.ALONG)
    expect(feature.edits(fins, feature.MAIN)[1] and not panel.field_timer.isActive(),
           "a place still waiting for typing to pause is taken before an arrow is grabbed")
    panel.finish_drag(handles.ALONG, 0.0)
    box.setValue(place)
    panel.field_entered(handles.ALONG)


def check_sections(panel):
    """Each section of the panel folds away and opens again as it was left;
    its header is marked while a field in it differs from the standard."""
    from freecad.finsnap import feature, taskpanel
    section = panel.sections[feature.GROUP_FIN]
    opened = section.header.isChecked()
    section.header.setChecked(not opened)
    kept = App.ParamGet(taskpanel.SECTION_PREFERENCES).GetBool(feature.GROUP_FIN, opened)
    expect(kept == (not opened) and section.content.isHidden() == opened,
           "a section folded or opened is kept so for the next time")
    section.header.setChecked(opened)
    prop = [p for p in feature.PROPERTIES if p.group == feature.GROUP_FIN
            and isinstance(panel.widgets[p.name], QtWidgets.QDoubleSpinBox)][0]
    widget = panel.widgets[prop.name]
    before = widget.value()
    widget.setValue(before + widget.singleStep())
    marked = taskpanel.MODIFIED_HEADER_STYLE in section.header.styleSheet()
    widget.setValue(before)
    expect(marked and taskpanel.MODIFIED_HEADER_STYLE not in section.header.styleSheet(),
           "the header of a section is marked while a field in it differs from the standard")


def main():
    commands = load_workbench()
    registered = Gui.listCommands()
    expect(all(c in registered for c in COMMANDS), "all commands are registered")

    from freecad.finsnap import defaults as d
    from freecad.finsnap import feature
    from freecad.finsnap import orient
    from freecad.finsnap.commands import ISOMETRIC
    from freecad.finsnap.taskpanel import FinSnapTaskPanel

    folder = tempfile.mkdtemp()
    target = os.path.join(folder, "fins")  # without extension on purpose
    messages = answer_dialogs(commands, target, d.TILT_ANGLE)
    doc = App.newDocument("FinSnapGui")

    # Stand on edge: a box lying flat ends up standing on its bottom edge.
    box = doc.addObject("Part::Feature", "Box")
    box.Shape = Part.makeBox(20, 20, 20)
    bottom = [i for i, e in enumerate(box.Shape.Edges, 1)
              if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    select(box, "Edge%d" % bottom)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    expect(not messages and box.Shape.BoundBox.ZMax > 20 + d.TOLERANCE, "Stand on edge tilts the box")
    select(box)
    Gui.runCommand("FinSnap_LayFlat")
    doc.recompute()
    expect(not messages and box.Placement.isIdentity(), "Lay flat again puts the box back")

    # Any edge with one of its faces: the face goes onto the bed first.
    top = [i for i, e in enumerate(box.Shape.Edges, 1)
           if e.BoundBox.ZMin > 20 - d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    front = [i for i, f in enumerate(box.Shape.Faces, 1) if f.BoundBox.YMax < d.TOLERANCE][0]
    # A top edge alone: its faces meet at a right angle, so it stands at 45 degrees unasked.
    ask_angle = QtWidgets.QInputDialog.getDouble
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a right-angled edge alone must not ask for an angle")))
    # Navigation animations on, as by default: the view has to be right when
    # the command returns, not only once an animation has run. The start view
    # is set without animation, so no turn of its own is still running.
    view = Gui.ActiveDocument.ActiveView
    view_settings = App.ParamGet(VIEW_SETTINGS)
    animated = view_settings.GetBool(NAVIGATION_ANIMATIONS, True)
    view_settings.SetBool(NAVIGATION_ANIMATIONS, False)
    view.viewTop()
    view_settings.SetBool(NAVIGATION_ANIMATIONS, True)
    select(box, "Edge%d" % top)
    try:
        Gui.runCommand("FinSnap_Tilt")
        doc.recompute()
        expect(not messages and abs(box.Shape.BoundBox.ZMin) < d.TOLERANCE
               and box.Shape.BoundBox.ZMax > 20 + d.TOLERANCE, "Stand on edge takes a right-angled top edge alone")
        # The top edge runs along X: the view looks along it, the bed below.
        up = view.getCameraOrientation().multVec(SCREEN_UP)
        expect(view.getViewDirection().getAngle(ALONG_X) < d.TOLERANCE
               and up.getAngle(UP) < d.TOLERANCE, "the view looks along the edge, the bed below")
        select(box)
        Gui.runCommand("FinSnap_LayFlat")
        doc.recompute()
        expect(view.getViewDirection().getAngle(ISOMETRIC) < d.TOLERANCE, "Lay flat again shows the part isometric")
    finally:
        QtWidgets.QInputDialog.getDouble = ask_angle
        view_settings.SetBool(NAVIGATION_ANIMATIONS, animated)
    select(box, "Edge%d" % top, "Face%d" % front)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    expect(not messages and abs(box.Shape.BoundBox.ZMin) < d.TOLERANCE
           and box.Shape.BoundBox.ZMax > 20 + d.TOLERANCE, "Stand on edge takes a top edge with its face")

    # A chamfer alone: laid onto the bed without asking for an angle.
    chamfered = doc.addObject("Part::Feature", "Chamfered")
    plain = Part.makeBox(20, 20, 20)
    chamfered.Shape = plain.makeChamfer(CHAMFER, [e for e in plain.Edges if e.BoundBox.ZMax < d.TOLERANCE
                                                  and e.BoundBox.YMax < d.TOLERANCE])
    slope = [i for i, f in enumerate(chamfered.Shape.Faces, 1)
             if abs(abs(f.normalAt(0, 0).z) - math.sqrt(0.5)) < d.TOLERANCE][0]
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a face alone must not ask for an angle")))
    select(chamfered, "Face%d" % slope)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    expect(not messages and chamfered.Shape.Faces[slope - 1].normalAt(0, 0).z < -1 + d.TOLERANCE,
           "Stand on edge lays a chamfer chosen alone onto the bed")
    select(chamfered)
    Gui.runCommand("FinSnap_LayFlat")
    doc.recompute()
    beside = [i for i, f in enumerate(chamfered.Shape.Faces, 1) if f.findPlane() is not None
              and any(e.isSame(o) for e in f.Edges for o in chamfered.Shape.Faces[slope - 1].Edges)
              and abs(f.normalAt(0, 0).x) < d.TOLERANCE and i != slope]
    select(chamfered, *["Face%d" % i for i in beside])
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    expect(not messages and chamfered.Shape.Faces[slope - 1].normalAt(0, 0).z < -1 + d.TOLERANCE,
           "Stand on edge with the two faces beside a chamfer stands the part on it")
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (d.TILT_ANGLE, True))
    doc.removeObject(chamfered.Name)

    # Deleting the last fins of the box lays it flat again; other fins keep it standing.
    leaning = [i for i, f in enumerate(box.Shape.Faces, 1) if f.normalAt(0, 0).z < -d.TOLERANCE]
    first = feature.create(box, "Face%d" % leaning[0])
    second = feature.create(box, "Face%d" % leaning[1])
    for fins in (first, second):
        commands.ViewProviderFinSnap(fins.ViewObject)
    first.ViewObject.Proxy.onDelete(first.ViewObject, [])
    doc.removeObject(first.Name)
    expect(not box.Placement.isIdentity(), "deleting fins while others remain keeps the box standing")
    second.ViewObject.Proxy.onDelete(second.ViewObject, [])
    doc.removeObject(second.Name)
    doc.recompute()
    expect(box.Placement.isIdentity(), "deleting the last fins lays the box flat again")

    # Overhangs: tilted flatter than the limit, the bottom face is selected and
    # reported; fins under the other face leave it marked in red.
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (FLAT_TILT, True))
    select(box, "Edge%d" % bottom)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    selected = Gui.Selection.getSelectionEx()
    hanging = [n for s in selected for n in s.SubElementNames]
    expect(len(hanging) == 1, "after a flat tilt the overhanging face is selected: %s" % hanging)
    steep = [i for i, f in enumerate(box.Shape.Faces, 1) if f.normalAt(0, 0).z < -d.TOLERANCE
             and "Face%d" % i not in hanging]
    marked = feature.create(box, "Face%d" % steep[0])
    commands.ViewProviderFinSnap(marked.ViewObject)
    doc.recompute()
    expect(marked.Overhangs == hanging, "the fins list the face that still overhangs")
    from freecad.finsnap import taskpanel
    noted = FinSnapTaskPanel(marked)
    expect(not noted.notes.isHidden()
           and taskpanel.WARNING_COLOR in noted.notes.styleSheet() and marked.Warnings[0] in noted.notes.text(),
           "the panel shows the warnings in a framed box of their own")
    # A note that names a place is a link: a click selects what it is about,
    # as Check Geometry does, and fits the view to it.
    overhang_note = next(i for i, w in enumerate(marked.Warnings) if hanging[0] in w)
    linked = "href='%d'" % overhang_note in noted.notes.text()
    camera = Gui.ActiveDocument.ActiveView.getCamera()
    noted.show_note(str(overhang_note))
    picked = [(s.Object, n) for s in Gui.Selection.getSelectionEx() for n in s.SubElementNames]
    expect(linked and picked == [(box, hanging[0])] and Gui.ActiveDocument.ActiveView.getCamera() != camera,
           "a click on the overhang note selects the face and fits the view to it: %s" % picked)
    # A note naming a fin, as one moved beside a hole names it: its faces are
    # selected, the arrows on it.
    fin = noted.built_fins()[-1]
    marked.Proxy.note_targets[overhang_note] = feature.NoteTarget(fin[0], [fin[1]], [], [], [])
    noted.show_note(str(overhang_note))
    picked = {feature.fin_at(marked, n) for s in Gui.Selection.getSelectionEx() for n in s.SubElementNames}
    expect(noted.handled == fin and picked == {fin}, "a click on a note naming a fin selects it, the arrows on it")
    # Tines left out are no faces of any object: marked in the selection colour.
    # Islands whose first layer could not be cut out: balls at their lowest points.
    for marks, points in (([Part.makeBox(1, 1, 1)], []), ([], [App.Vector(1, 2, 3)])):
        marked.Proxy.note_targets[overhang_note] = feature.NoteTarget(None, [], [], marks, points)
        camera = Gui.ActiveDocument.ActiveView.getCamera()
        noted.show_note(str(overhang_note))
        expect(noted.handles.noted.whichChild.getValue() == coin.SO_SWITCH_ALL and not Gui.Selection.hasSelection()
               and Gui.ActiveDocument.ActiveView.getCamera() != camera,
               "a click on a note naming what cannot be selected marks it and fits the view to it: %s, %s"
               % (len(marks), len(points)))
    noted.show_note("99")
    expect(noted.handles.noted.whichChild.getValue() == coin.SO_SWITCH_NONE and not Gui.Selection.hasSelection(),
           "a click without a place to show clears the selection and the marks")
    noted.reject()
    marks = marked.ViewObject.Proxy.marks
    expect(marks.getNumChildren() == 1 and marks.whichChild.getValue() == coin.SO_SWITCH_ALL,
           "the overhanging face is marked in the 3D view")
    marked.ViewObject.Visibility = False
    expect(marks.whichChild.getValue() == coin.SO_SWITCH_NONE, "hiding the fins hides the marks")
    marked.ViewObject.Visibility = True
    box.ViewObject.Visibility = False
    expect(marks.whichChild.getValue() == coin.SO_SWITCH_NONE, "hiding the part hides the marks on it")
    box.ViewObject.Visibility = True
    expect(marks.whichChild.getValue() == coin.SO_SWITCH_ALL, "showing the part shows them again")
    # A part inside containers: hiding the container it lies in, or the one
    # around that, hides its marks as well.
    outer = doc.addObject("App::Part", "Outer")
    inner = doc.addObject("App::Part", "Inner")
    outer.addObject(inner)
    held = doc.addObject("Part::Feature", "Held")
    held.Shape = box.Shape.copy()
    held.Placement = box.Placement
    inner.addObject(held)
    nested = feature.create(held, "Face%d" % steep[0])
    commands.ViewProviderFinSnap(nested.ViewObject)
    doc.recompute()
    nested_marks = nested.ViewObject.Proxy.marks
    for container in (inner, outer):
        container.ViewObject.Visibility = False
        hidden = nested_marks.whichChild.getValue() == coin.SO_SWITCH_NONE
        container.ViewObject.Visibility = True
        expect(hidden and nested_marks.whichChild.getValue() == coin.SO_SWITCH_ALL,
               "hiding %s, which holds the part, hides its marks, showing it shows them" % container.Label)
    # Shown or hidden, an object no fins depend on is not checked against
    # every object of the document.
    checked = []
    real_is_fins = feature.is_fins

    def counting_is_fins(obj):
        checked.append(obj)
        return real_is_fins(obj)

    lone = doc.addObject("Part::Feature", "Lone")
    lone.Shape = Part.makeBox(1, 1, 1)
    doc.recompute()
    feature.is_fins = counting_is_fins
    try:
        lone.ViewObject.Visibility = False
    finally:
        feature.is_fins = real_is_fins
    expect(not checked, "hiding an object no fins depend on checks no other object: %d" % len(checked))
    for name in (lone.Name, nested.Name, held.Name, inner.Name, outer.Name):
        doc.removeObject(name)

    # Fins under the overhanging face as well: the report after a tilt leaves it out.
    carried = feature.create(box, hanging[0])
    commands.ViewProviderFinSnap(carried.ViewObject)
    doc.recompute()
    Gui.Selection.clearSelection()
    commands._report_overhangs(box)
    expect(not Gui.Selection.getSelectionEx(), "faces that carry fins are not reported as overhangs")
    carried.ViewObject.Proxy.onDelete(carried.ViewObject, [])
    doc.removeObject(carried.Name)
    doc.recompute()

    # Lay flat again with fins. Cancel changes nothing; No keeps the fins, moved
    # along with the part and not rebuilt; moving the part again, by hand or with
    # Stand on edge, rebuilds them; Yes deletes them.
    from freecad.finsnap.i18n import translate
    standing = box.Placement
    ANSWERS.append(QtWidgets.QMessageBox.Cancel)
    select(box)
    Gui.runCommand("FinSnap_LayFlat")
    expect(box.Placement.isSame(standing) and not feature.is_laid_flat(marked),
           "Cancel leaves the part standing and its fins as they are")
    ANSWERS.append(QtWidgets.QMessageBox.No)
    open_when_kept = FinSnapTaskPanel(marked)
    marked.ViewObject.Proxy.panel = open_when_kept
    select(box)
    Gui.runCommand("FinSnap_LayFlat")
    doc.recompute()
    expect(open_when_kept.released, "No also closes a panel open on the fins, which it changes")
    expect(box.Placement.isIdentity() and marked.isValid() and feature.is_laid_flat(marked)
           and marked.Overhangs == [] and marks.getNumChildren() == 0
           and translate("FinSnap", feature.NOTE_LAID_FLAT) in marked.Warnings,
           "No lays the part flat and keeps its fins, marked as laid flat, without overhang marks")
    expect(marked.Shape.distToShape(box.Shape)[0] < d.TOLERANCE, "the kept fins moved along with the part")
    select(marked)
    Gui.runCommand("FinSnap_Export3MF")
    expect(len(messages) == 1 and not os.path.exists(target + ".3mf"),
           "fins of a part laid flat alone give nothing to export: %s" % messages)
    del messages[:]
    select(box)
    Gui.Selection.addSelection(marked)
    Gui.runCommand("FinSnap_Export3MF")
    with zipfile.ZipFile(target + ".3mf") as archive:
        model = archive.read("3D/3dmodel.model").decode()
    expect(model.count("<object ") == 1 and len(messages) == 1 and marked.Label in messages[0],
           "beside other bodies, fins of a part laid flat are left out and named: %s" % messages)
    os.remove(target + ".3mf")
    del messages[:]
    select(box, "Edge%d" % bottom)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    expect(not feature.is_laid_flat(marked) and marked.isValid() and marked.Overhangs == hanging,
           "standing the part again with Stand on edge rebuilds the kept fins")
    ANSWERS.append(QtWidgets.QMessageBox.No)
    select(box)
    Gui.runCommand("FinSnap_LayFlat")
    doc.recompute()
    # Set back by hand, not with Stand on edge: the fins are rebuilt all the same.
    box.Placement = standing
    doc.recompute()
    expect(not feature.is_laid_flat(marked) and marked.isValid() and marked.Overhangs == hanging,
           "the part stood again by hand rebuilds the kept fins")
    # Laid flat by hand, then stood with Stand on edge, so Lay flat again knows it.
    box.Placement = App.Placement()
    select(box, "Edge%d" % bottom)
    Gui.runCommand("FinSnap_Tilt")
    doc.recompute()
    ANSWERS.append(QtWidgets.QMessageBox.Yes)
    open_on_marked = FinSnapTaskPanel(marked)
    marked.ViewObject.Proxy.panel = open_on_marked
    select(box)
    Gui.runCommand("FinSnap_LayFlat")
    doc.recompute()
    expect(box.Placement.isIdentity() and marked.Name not in [o.Name for o in doc.Objects]
           and open_on_marked.released,
           "Yes lays the part flat and deletes its fins, closing a panel open on them first")
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (d.TILT_ANGLE, True))

    # Quick fins: an edge stands the part and adds fins; a face turns the part
    # so that face leans over the bed. Both open the panel.
    quick = doc.addObject("Part::Feature", "Quick")
    # Long enough that automatic placement would put two fins under it.
    quick.Shape = Part.makeBox(QUICK_LENGTH, 20, 20)
    on_bed = [i for i, e in enumerate(quick.Shape.Edges, 1)
              if e.BoundBox.ZMax < d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE][0]
    facing = [i for i, f in enumerate(quick.Shape.Faces, 1) if f.BoundBox.YMax < d.TOLERANCE][0]
    for what, sub in (("an edge", "Edge%d" % on_bed), ("a face", "Face%d" % facing)):
        select(quick, sub)
        Gui.runCommand("FinSnap_QuickFins")
        made = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick]
        expect(not messages and len(made) == 1 and made[0].isValid() and made[0].Shape.Solids
               and not made[0].CounterFace and made[0].ResultFinCount == 1
               and made[0].FinPlacement == d.PLACEMENT_CENTER and not quick.Placement.isIdentity()
               and Gui.Control.activeDialog(),
               "Quick fins on %s stands the part, adds the main fin alone and opens the panel: %s"
               % (what, messages))
        if what == "a face":
            leaning = quick.Shape.Faces[facing - 1].normalAt(0, 0).z
            expect(abs(leaning + math.sqrt(0.5)) < d.TOLERANCE, "the chosen face leans 45 degrees over the bed")
        if what == "an edge":
            # Cancel undoes Quick fins whole: the fins go, the part lies as before.
            made[0].ViewObject.Proxy.panel.reject()
            expect(made[0].Name not in [o.Name for o in doc.Objects] and quick.Placement.isIdentity()
                   and orient.FLAT_PLACEMENT not in quick.PropertiesList,
                   "Cancel after Quick fins deletes the fins and lays the part back as it was")
            expect(doc.UndoNames and doc.UndoNames[0] == App.Qt.translate("FinSnap", "Cancel fins"),
                   "the Cancel is one step of its own on the undo stack: %s" % doc.UndoNames[:2])
            continue
        Gui.Control.closeDialog()
        doc.removeObject(made[0].Name)
        quick.Placement = App.Placement()
        doc.recompute()
    chosen_stands(doc, quick, facing, messages)
    quick_on_pad(doc)
    checked_on_switch(doc)
    island_marks(doc)
    limits_page(doc)
    value_colors()
    stability_checked(doc, messages)
    bridges_checked(doc, messages)
    saved_while_editing()
    # Fins of the part laid flat keep their mark and shape over a Quick fins
    # cancelled: standing the part rebuilt them, Cancel gives them back.
    select(quick, "Edge%d" % on_bed)
    Gui.runCommand("FinSnap_QuickFins")
    kept = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick][0]
    kept.ViewObject.Proxy.panel.accept()
    # Laid flat keeping its fins, as Lay flat again does with No.
    feature.keep_laid_flat(kept, orient.back_to_flat(quick))
    orient.lay_back(quick)
    doc.recompute()
    flat_box = kept.Shape.BoundBox
    # Over the opposite edge on the bed: the face over the first is carried already.
    bounds = quick.Shape.BoundBox
    opposite = [i for i, e in enumerate(quick.Shape.Edges, 1) if e.BoundBox.ZMax < bounds.ZMin + d.TOLERANCE
                and e.BoundBox.YMin > bounds.YMax - d.TOLERANCE]
    expect(opposite, "the part lies flat again, with an edge on the bed opposite the first")
    opposite = opposite[0]
    select(quick, "Edge%d" % opposite)
    Gui.runCommand("FinSnap_QuickFins")
    rebuilt = not feature.is_laid_flat(kept)
    others = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick and o is not kept]
    expect(others, "Quick fins runs again on the part with fins laid flat: %s" % messages)
    second = others[0]
    second.ViewObject.Proxy.panel.reject()
    expect(rebuilt and feature.is_laid_flat(kept) and kept.Shape.BoundBox.isInside(flat_box)
           and flat_box.isInside(kept.Shape.BoundBox) and quick.Placement.isIdentity(),
           "Cancel after Quick fins leaves other fins laid flat as they were, mark and shape")
    doc.removeObject(kept.Name)
    doc.recompute()
    # Without a 3D view the panel cannot open, so there is no Cancel: the
    # fins go again and the part lies as before, at once, with a message.
    from freecad.finsnap import handles as handles_module
    real_handles = handles_module.Handles

    def without_view(*args):
        raise handles_module.NoView("no 3D view")

    handles_module.Handles = without_view
    try:
        select(quick, "Edge%d" % on_bed)
        Gui.runCommand("FinSnap_QuickFins")
    finally:
        handles_module.Handles = real_handles
    left = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] is quick]
    expect(not left and quick.Placement.isIdentity() and messages and "no 3D view" in messages[-1]
           and not Gui.Control.activeDialog(),
           "Quick fins without a 3D view leaves no fins and the part as it lay: %s" % messages)
    del messages[:]
    doc.removeObject(quick.Name)
    # An edge off the bed between faces not at a right angle: Quick fins points to Stand on edge.
    beveled = doc.addObject("Part::Feature", "Beveled")
    plain_box = Part.makeBox(30, 20, 20)
    top_front = [e for e in plain_box.Edges if e.BoundBox.ZMin > 20 - d.TOLERANCE and e.BoundBox.YMax < d.TOLERANCE]
    beveled.Shape = plain_box.makeChamfer(CHAMFER, top_front)
    slanted = [i for i, e in enumerate(beveled.Shape.Edges, 1) if e.BoundBox.YMax < d.TOLERANCE
               and e.BoundBox.ZLength < d.TOLERANCE and abs(e.BoundBox.ZMin - (20 - CHAMFER)) < d.TOLERANCE][0]
    select(beveled, "Edge%d" % slanted)
    Gui.runCommand("FinSnap_QuickFins")
    stand_on_edge = App.Qt.translate("FinSnap", "Stand on edge")
    expect(len(messages) == 1 and stand_on_edge in messages[0] and beveled.Placement.isIdentity()
           and not Gui.Control.activeDialog(), "an edge Quick fins cannot use points to Stand on edge: %s" % messages)
    del messages[:]
    doc.removeObject(beveled.Name)

    # Add fins: selecting a leaning face creates the object and opens the panel.
    cube = doc.addObject("Part::Feature", "Cube")
    cube.Shape = tilted_cube()
    select(cube, face_name(cube, lower_left_face(cube.Shape)))
    Gui.runCommand("FinSnap_AddFins")
    created = [o for o in doc.Objects if o.TypeId == "Part::FeaturePython"]
    expect(len(created) == 1 and Gui.Control.activeDialog() and not Gui.Selection.getSelection(),
           "Add fins creates the object and opens the panel, the selection that made it used up")
    Gui.Control.closeDialog()
    fins = created[0]
    doc.recompute()
    expect(fins.Shape.Solids, "the fins have a shape")

    # Counter fin afterwards: selecting the fins finds the opposite face itself.
    select(fins)
    Gui.runCommand("FinSnap_AddCounterFin")
    doc.recompute()
    expect(not messages and fins.CounterFace and len(fins.Shape.Solids) == 2,
           "Add counter fin finds the opposite face and adds a fin there")
    other = doc.addObject("Part::Feature", "OtherPart")
    other.Shape = tilted_cube()
    counter_before = fins.CounterFace
    select(fins)
    Gui.Selection.addSelection(other, face_name(other, lower_left_face(other.Shape)))
    Gui.runCommand("FinSnap_AddCounterFin")
    expect(len(messages) == 1 and fins.CounterFace == counter_before,
           "a counter fin on a face of another part is refused with a message")
    del messages[:]
    doc.removeObject(other.Name)
    heights = sorted(round(s.BoundBox.ZLength, 3) for s in fins.Shape.Solids)
    expect(heights[0] == heights[1], "the counter fin is as large as the main fin: %s" % heights)
    fins.CounterTineCount = 1
    doc.recompute()
    heights = sorted(round(s.BoundBox.ZLength, 3) for s in fins.Shape.Solids)
    expect(heights[0] < heights[1], "fewer counter tines make the counter fin smaller: %s" % heights)
    fins.CounterFace = None
    doc.recompute()
    expect(len(fins.Shape.Solids) == 1, "clearing the counter face removes the counter fin")

    # Task panel: one field per parameter, preview and accept write them back.
    panel = FinSnapTaskPanel(fins)
    expect(len(panel.widgets) == len(feature.PROPERTIES), "the panel has a field for every parameter")
    expect(panel.drawings and all(not p.pixmap().isNull() for p in panel.drawings),
           "the panel shows its drawings")
    from freecad.finsnap.version import application
    expect(application() in panel.form.windowTitle(), "the panel title names the version")
    panel.widgets["TineCount"].setValue(2)
    panel.preview()
    expect(fins.TineCount == 2 and fins.ResultHeight.Value < 11.2, "preview applies a changed value")
    panel.widgets["TineCount"].setValue(0)
    panel.apply()

    # Fields without effect are greyed out, and a change starts the preview by itself.
    expect(not panel.widgets["FinCount"].isEnabled() and not panel.widgets["CounterTineCount"].isEnabled(),
           "fin count and counter tines are greyed out with automatic placement and no counter fin")
    placement = panel.widgets["FinPlacement"]
    placement.setCurrentIndex(placement.findData(d.PLACEMENT_DISTRIBUTED))
    expect(panel.widgets["FinCount"].isEnabled() and not panel.widgets["FaceLengthPerFin"].isEnabled(),
           "distributed placement enables the fin count and greys out the face length per fin")
    expect(panel.timer.isActive(), "a change starts the automatic preview")
    panel.timer.timeout.emit()
    expect(fins.FinPlacement == d.PLACEMENT_DISTRIBUTED and not panel.timer.isActive(),
           "the automatic preview applies the change")
    expect(panel.timer.parent() is panel.form, "the preview timer goes with the panel")
    expect(panel.notes.isHidden() == (not fins.Warnings), "the notes box shows only when there are warnings")
    foot = panel.widgets["FootShape"]
    foot.setCurrentIndex(foot.findData(d.FOOT_NONE))
    expect(not panel.widgets["FootThickness"].isEnabled()
           and App.Qt.translate("FinSnap", feature.NOTE_NO_FOOT) in panel.widgets["FootThickness"].toolTip(),
           "without a foot its fields are greyed out and the tooltip says why")
    placement.setCurrentIndex(placement.findData(d.PLACEMENT_AUTO))
    foot.setCurrentIndex(foot.findData(d.FOOT_SHAPE))
    panel.preview()

    # Cancel on fins that already existed puts back what they had before the panel opened.
    reopened = FinSnapTaskPanel(fins)
    before = fins.TineCount
    reopened.widgets["TineCount"].setValue(before + 1)
    reopened.timer.timeout.emit()
    expect(fins.TineCount == before + 1, "the reopened panel writes a change at once")
    reopened.reject()
    expect(fins.TineCount == before and fins.isValid(), "Cancel puts back the values the fins had")

    # Fields that differ from the standard are marked; their button puts the standard back.
    from freecad.finsnap import presets
    from freecad.finsnap.params import FinParams
    built_in = FinParams().fin_thickness
    marking = FinSnapTaskPanel(fins)
    expect(isinstance(marking.widgets["TineRestart"], QtWidgets.QCheckBox),
           "the tine restart is a checkbox in the panel")
    thickness, reset = marking.widgets["FinThickness"], marking.resets["FinThickness"]
    label = marking.labels["FinThickness"]
    expect(reset.isHidden() and not label.styleSheet(), "a field at its standard value is not marked")
    thickness.setValue(STANDARD_THICKNESS)
    expect(not reset.isHidden() and label.styleSheet() == taskpanel.MODIFIED_STYLE,
           "a changed field is marked and gets a button back to the standard")
    reset.click()
    expect(abs(thickness.value() - built_in) < d.TOLERANCE and reset.isHidden(),
           "the button puts the standard value back and clears the mark")
    thickness.setValue(STANDARD_THICKNESS)
    marking.save_standard()
    expect(abs(presets.standard().fin_thickness - STANDARD_THICKNESS) < d.TOLERANCE and reset.isHidden(),
           "Save as standard makes the value the standard for new fins and clears the mark")
    QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes)
    marking.factory_settings()
    expect(presets.standard() == FinParams() and abs(thickness.value() - built_in) < d.TOLERANCE
           and reset.isHidden(), "Factory settings forget the saved standard and reset the fields")
    marking.reject()

    # Single fins: the Delete key on a face of one fin removes that fin only;
    # the panel removes and brings back fins and the counter fin, and Cancel
    # puts it all back.
    row = doc.addObject("Part::Feature", "Row")
    row.Shape = tilted_cube()
    lined = feature.create(row, face_name(row, lower_left_face(row.Shape)))
    commands.ViewProviderFinSnap(lined.ViewObject)
    lined.FinPlacement = d.PLACEMENT_DISTRIBUTED
    lined.FinCount = 3
    doc.recompute()

    def face_of_fin(index):
        target = lined.Shape.Solids[index].Faces[0]
        return "Face%d" % [i for i, f in enumerate(lined.Shape.Faces, 1) if f.isSame(target)][0]

    kept = lined.ViewObject.Proxy.onDelete(lined.ViewObject, [face_of_fin(1)])
    expect(kept is False and lined.Name in [o.Name for o in doc.Objects] and lined.ResultFinCount == 2,
           "the Delete key on one fin removes that fin and keeps the others")
    editing = FinSnapTaskPanel(lined)
    gap_field = editing.widgets["Gap"]
    expect(abs(gap_field.singleStep() - feature.STEP_PROFILE) < d.TOLERANCE
           and gap_field.toolTip().startswith("<p>"),
           "fields step in sizes that suit them, and their tooltips wrap")
    editing.widgets["LayerHeight"].setValue(THICK_LAYER)
    expect(abs(editing.widgets["TineFirst"].singleStep() - THICK_LAYER) < d.TOLERANCE,
           "fields on the layer grid step by the layer height entered")
    editing.reset()
    expect(lined.ResultFinCount == 3, "the panel brings removed fins back")
    select(lined, face_of_fin(0))
    editing.remove_selected()
    editing.add_counter()
    expect(lined.ResultFinCount == 2 and lined.CounterFace, "the panel removes the selected fin and adds a counter fin")
    editing.fin_list.setCurrentRow(editing.fin_list.count() - 1)
    expect(editing.listed_fins[-1][0] == feature.COUNTER and editing.handled == editing.listed_fins[-1]
           and editing.selected_fins() == [editing.handled],
           "the list names the counter fins last; one picked there gets the arrows and is selected: %s"
           % editing.listed_fins)
    gone_before = feature.removed(lined, feature.MAIN)
    editing.fin_list.setCurrentRow(0)
    picked = editing.handled
    editing.remove_selected()
    expect(picked[0] == feature.MAIN and feature.removed(lined, feature.MAIN) == sorted(gone_before + [picked[1]]),
           "Remove selected fin takes the fin picked in the list")
    # A face lying on the bed, selected for the counter fin, is refused with a
    # note, and the counter fin stays where it was.
    counter_face = lined.CounterFace
    on_bed = [f for f in row.Shape.Faces if f.BoundBox.ZLength < d.TOLERANCE][0]
    select(row, face_name(row, on_bed))
    editing.add_counter()
    expect(lined.CounterFace == counter_face and not editing.notes.isHidden()
           and taskpanel.WARNING_COLOR in editing.notes.styleSheet(),
           "a face on the bed is refused for the counter fin, with a note: %s" % editing.notes.text())
    editing.reject()
    expect(lined.ResultFinCount == 2 and not lined.CounterFace and feature.removed(lined, feature.MAIN) == [2],
           "Cancel puts back the fins as they were when the panel opened")
    # Through the Delete command itself, as the key runs it: one step undoes it.
    feature.reset_fins(lined)
    doc.recompute()
    select(lined, face_of_fin(2))
    Gui.runCommand("Std_Delete")
    doc.recompute()
    removed_by_key = lined.ResultFinCount
    doc.undo()
    doc.recompute()
    expect(removed_by_key == 2 and lined.ResultFinCount == 3,
           "Delete on a fin removes it, and Undo brings it back in one step")
    # Merged into the part, single fins cannot be picked: a message, nothing deleted.
    lined.Connection = d.CONNECTION_MERGED
    doc.recompute()
    kept = lined.ViewObject.Proxy.onDelete(lined.ViewObject, ["Face1"])
    expect(kept is False and len(messages) == 1 and lined.Name in [o.Name for o in doc.Objects],
           "merged fins refuse to lose a single fin, with a message: %s" % messages)
    del messages[:]
    lined.Connection = d.CONNECTION_SEPARATE
    doc.recompute()
    # Removed for the first time in the panel, then Cancel: nothing stays removed.
    feature.reset_fins(lined)
    lined.removeProperty(feature.REMOVED[feature.MAIN])
    lined.removeProperty(feature.EDITED_OF[feature.MAIN])
    doc.recompute()
    fresh = FinSnapTaskPanel(lined)
    select(lined, face_of_fin(0))
    fresh.remove_selected()
    fresh.reject()
    expect(lined.ResultFinCount == 3 and not feature.removed(lined, feature.MAIN),
           "Cancel also forgets a fin removed for the first time in the panel")
    # Handles: on the first fin from the start, on a fin clicked after; dragged,
    # the fin is previewed and then moved.
    from freecad.finsnap import handles
    select(lined)
    look = (lined.ViewObject.ShapeAppearance[0].DiffuseColor, lined.ViewObject.Transparency)
    moving = FinSnapTaskPanel(lined)
    expect(moving.handled == (feature.MAIN, 1) and moving.handles.arrows.whichChild.getValue() == coin.SO_SWITCH_ALL,
           "the panel opens with two arrows on the first fin")
    expect(lined.ViewObject.Transparency == round(handles.PREVIEW_TRANSPARENCY * handles.PERCENT),
           "the fins are see-through while the panel is open")
    select(lined, face_of_fin(2))
    expect(moving.handled == (feature.MAIN, 3), "a fin clicked gets the handles")
    expect(moving.fin_list.count() == 3 and moving.fin_list.currentRow() == 2,
           "the list shows the fins one below the other and marks the one clicked in the 3D view")
    moving.fin_list.setCurrentRow(1)
    expect(moving.handled == (feature.MAIN, 2) and moving.fin_label.text().endswith("2")
           and moving.selected_fins() == [(feature.MAIN, 2)],
           "a fin picked in the list gets the arrows, its name and the selection")
    Gui.Selection.clearSelection()
    moving.fin_list.itemClicked.emit(moving.fin_list.item(1))
    expect(moving.selected_fins() == [(feature.MAIN, 2)],
           "a click on the row already marked selects its fin again")
    select(lined, face_of_fin(0))
    before = lined.Shape.Solids[0].BoundBox.Center
    held = dict(moving.handles.draggers)
    place = moving.fin_fields[handles.ALONG].value()
    moving.handle_started(handles.ALONG)
    moving.handle_moved(handles.ALONG, FIN_SHIFT)
    expect(abs(moving.fin_fields[handles.ALONG].value() - (place + FIN_SHIFT)) < d.TOLERANCE,
           "the field follows the arrow while it is dragged")
    expect(_value_shown(moving.handles) == moving.fin_fields[handles.ALONG].text(),
           "the value stands at the arrow while it is dragged, as the field shows it: %s"
           % _value_shown(moving.handles))
    moving.drag_step()
    expect(abs(lined.Shape.Solids[0].BoundBox.Center.sub(before).Length - FIN_SHIFT) < d.TOLERANCE
           and feature.edits(lined, feature.MAIN)[1] == {1: FIN_SHIFT},
           "a dragged fin is built where the arrow is, while it is held")
    moving.finish_drag(handles.ALONG, FIN_SHIFT)
    expect(feature.edits(lined, feature.MAIN)[1] == {1: FIN_SHIFT}
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_NONE,
           "a fin let go stays there")
    expect(_value_shown(moving.handles) is None, "let go, the value at the arrow goes")
    expect(all(moving.handles.draggers[kind] is held[kind] for kind in held),
           "the arrows stay the same after a move; Coin may still hold the one let go")
    released_without_button(moving.handles, "a box")
    expect(all(abs(a - b) < COLOR_TOLERANCE for a, b in zip(handles.axis_color("z"), AXIS_Z_RGB)),
           "the arrow up has the colour of the z axis: %s" % (handles.axis_color("z"),))
    result = lined.Proxy.results[feature.MAIN]
    onto_neighbour = result.starts[2] - result.starts[1]
    moving.handle_started(handles.ALONG)
    moving.handle_moved(handles.ALONG, onto_neighbour)
    moving.drag_step()
    expect(feature.edits(lined, feature.MAIN)[1] == {1: FIN_SHIFT}
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_ALL
           and taskpanel.ERROR_COLOR in moving.notes.styleSheet(),
           "a fin dragged onto its neighbour stays at its last place, shown red where the arrow is")
    expect(fin_tinted(lined, moving.handled), "while the fin cannot stand where the arrow is, it alone is "
           "red, not mixed with green; the other fins stay green")
    expect(lined.isValid(), "a place where the fin cannot stand is never built into the object")
    # After one fin alone was red, the whole object turns red and green again
    # with one material, whatever number of faces it has by then.
    moving.handles.tint(False)
    red_once = list(lined.ViewObject.ShapeAppearance)
    moving.handles.tint(True)
    expect(len(red_once) == 1 and rgb_close(red_once[0].DiffuseColor, handles.INVALID_COLOR)
           and len(lined.ViewObject.ShapeAppearance) == 1, "after one fin alone was red, the whole object can turn red")
    moving.drag_step()
    moving.finish_drag(handles.ALONG, onto_neighbour)
    snapped = feature.edits(lined, feature.MAIN)[1].get(1, 0.0)
    # The drag started with the fin moved by FIN_SHIFT already.
    nearest = FIN_SHIFT + onto_neighbour - result.thickness - d.FOOT_CLEARANCE
    expect(nearest - taskpanel.SNAP_RESOLUTION - d.TOLERANCE <= snapped <= nearest + d.TOLERANCE
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_NONE
           and rgb_close(lined.ViewObject.ShapeColor, handles.VALID_COLOR),
           "let go there, it goes as near to its neighbour as it can stand, green again: %.3f of %.3f mm"
           % (snapped, nearest))
    moving.update_ends()
    expect(moving.handles.ends[handles.ALONG] == (handles.BACK,),
           "at its neighbour, the arrow along the face shows no end towards it")
    expect(all(switch.whichChild.getValue() == coin.SO_SWITCH_NONE
               for halves in moving.handles.halves[handles.ALONG].values() for end, switch in halves.items()
               if end == handles.FORTH), "the end left out is hidden, at rest and held")
    # Dragged up or down, the fin follows the arrow: near a tine it is built
    # ending with it, green; between tines it is built as high as the arrow,
    # yellow, with no second fin over it; far above the face, where it cannot
    # stand, it stays and is red. Let go, it goes to the nearest tine.
    tops = moving.tine_tops()
    high = moving.built_value(handles.UP)
    pitch = tops[-1] - tops[-2]
    between = tops[-2] + pitch / 2
    moving.handle_started(handles.UP)
    moving.handle_moved(handles.UP, between - high)
    moving.drag_step()
    expect(len(tops) > 1 and fin_tinted(lined, moving.handled, handles.BETWEEN_COLOR)
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_NONE
           and abs(moving.built_value(handles.UP) - between) < d.TOLERANCE,
           "dragged between two tines, the fin is built as high as the arrow, yellow, alone: %s" % tops)
    moving.handle_moved(handles.UP, tops[-2] + taskpanel.HEIGHT_REACH / 2 - high)
    moving.drag_step()
    expect(abs(moving.built_value(handles.UP) - tops[-2]) < d.TOLERANCE
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_NONE
           and len(lined.ViewObject.ShapeAppearance) == 1,
           "dragged near a tine, the fin is built ending with it, green")
    moving.handle_moved(handles.UP, TOO_HIGH)
    moving.drag_step()
    expect(fin_tinted(lined, moving.handled) and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_ALL
           and abs(moving.built_value(handles.UP) - tops[-2]) < d.TOLERANCE,
           "dragged far above the face, the fin stays at its last place, red")
    moving.finish_drag(handles.UP, TOO_HIGH)
    tallest = moving.built_value(handles.UP)
    expect(abs(tallest - tops[-1]) < d.TOLERANCE and len(lined.ViewObject.ShapeAppearance) == 1,
           "let go far above the face, the fin ends with its highest tine, green: %.3f mm" % tallest)
    moving.update_ends()
    expect(moving.handles.ends[handles.UP] == (handles.BACK,), "at its highest tine, the arrow up shows no end up")
    moving.handle_started(handles.UP)
    moving.finish_drag(handles.UP, -SHORT_OF_HALF_STEP * pitch)
    kept = moving.built_value(handles.UP)
    moving.handle_started(handles.UP)
    moving.finish_drag(handles.UP, -PAST_HALF_STEP * pitch)
    expect(abs(kept - tops[-1]) < d.TOLERANCE and abs(moving.built_value(handles.UP) - tops[-2]) < d.TOLERANCE,
           "let go less than half a step down the height stays, more than half it ends with the tine below")
    moving.update_ends()
    expect(moving.handles.ends[handles.UP] == ((handles.BACK, handles.FORTH) if len(tops) > 2 else (handles.FORTH,)),
           "between its tines, the arrow up shows both ends")
    # Dragged over the corner of the face, let go it stands at the corner.
    moving.handle_started(handles.ALONG)
    moving.handle_moved(handles.ALONG, -TOO_HIGH)
    moving.finish_drag(handles.ALONG, -TOO_HIGH)
    cornered = moving.built_value(handles.ALONG)
    expect(cornered < FIN_SHIFT and not moving.can_stand(handles.ALONG, cornered - taskpanel.SNAP_RESOLUTION),
           "let go beyond the corner of the face, the fin stands at the corner: %.3f mm" % cornered)
    moving.update_ends()
    expect(moving.handles.ends[handles.ALONG] == (handles.FORTH,),
           "at the corner, the arrow along the face shows no end beyond it")
    moving.fin_fields[handles.ALONG].setValue(place + FIN_SHIFT)
    moving.field_entered(handles.ALONG)
    moving.fin_fields[handles.UP].setValue(high)
    moving.field_entered(handles.UP)
    lower = result.heights[1] - FIN_SHIFT
    moving.fin_fields[handles.UP].setValue(lower)
    moving.field_entered(handles.UP)
    lowered = lined.Proxy.results[feature.MAIN]
    expect(abs(lowered.heights[1] - lower) < d.TOLERANCE, "a height typed into the field sets the fin's height")
    moving.handle_started(handles.UP)
    moving.finish_drag(handles.UP, 0.0)
    expect(abs(moving.built_value(handles.UP) - lower) < d.TOLERANCE,
           "a click on the arrow up keeps a height typed by hand, off the tines")
    moving.fin_fields[handles.ALONG].setValue(place)
    moving.field_entered(handles.ALONG)
    expect(not feature.edits(lined, feature.MAIN)[1], "a place typed into the field moves the fin there")
    check_typed_fields(moving, lined, place)
    check_sections(moving)
    lowered = lined.Proxy.results[feature.MAIN]
    off_edge = App.Vector(*moving.handles.offsets[handles.UP].translation.getValue().getValue())
    expect(App.Vector(*moving.handles.places[handles.UP].translation.getValue().getValue())
           .sub(lowered.edges[1]).Length < d.TOLERANCE
           and abs(off_edge.Length - handles.CLEARANCE) < d.TOLERANCE,
           "the arrows follow to the upright outer edge of the fin, just outside it")
    # A drag builds each place once: the trial of a step serves its real
    # build, and nothing is built twice. Afterwards every build is new, and
    # the arrow ends are tried once for each place of the fin.
    from freecad.finsnap import geometry
    real_build = geometry.build
    builds = []

    def counting(*args, **kwargs):
        builds.append(args)
        return real_build(*args, **kwargs)

    geometry.build = counting
    try:
        moving.handle_started(handles.ALONG)
        steps = []
        for step in (1, 2):
            moving.handle_moved(handles.ALONG, step * BUILD_STEP)
            del builds[:]
            moving.drag_step()
            steps.append(len(builds))
        moving.finish_drag(handles.ALONG, 2 * BUILD_STEP)
        reuse_after = lined.Proxy.reuse
        del builds[:]
        moving.update_ends()
        first_ends = len(builds)
        del builds[:]
        moving.update_ends()
        same_ends = len(builds)
        tine_count = moving.widgets["TineCount"]
        tine_count.setValue(tine_count.value() + 1)
        moving.preview()
        del builds[:]
        moving.update_ends()
        changed_ends = len(builds)
        tine_count.setValue(tine_count.value() - 1)
        moving.preview()
    finally:
        geometry.build = real_build
    expect(steps == [1, 1], "each step of a drag builds once, not as trial and again for real: %s" % steps)
    expect(reuse_after is None, "after the drag, every build is made afresh")
    expect(first_ends == len(handles.KINDS) * 2 and same_ends == 0 and changed_ends > 0,
           "the arrow ends are tried once for each place, again after a parameter changed: %d, %d, %d"
           % (first_ends, same_ends, changed_ends))
    # A drag that fails on letting go still ends: every later build is made afresh.
    real_drag_to = moving.drag_to

    def failing(*args):
        raise RuntimeError("a drag failing on purpose")

    moving.drag_to = failing
    moving.handle_started(handles.ALONG)
    try:
        moving.finish_drag(handles.ALONG, BUILD_STEP)
    except RuntimeError:
        pass
    moving.drag_to = real_drag_to
    expect(lined.Proxy.reuse is None, "a drag that fails on letting go still ends, nothing is kept")
    # A value typed just before an arrow is grabbed is built first.
    tines = moving.widgets["TineCount"]
    typed = tines.value() + 1
    tines.setValue(typed)
    moving.handle_started(handles.ALONG)
    moving.finish_drag(handles.ALONG, 0.0)
    expect(lined.TineCount == typed, "a value typed just before an arrow is grabbed is built first")
    tines.setValue(typed - 1)
    moving.preview()
    # A click on an arrow without a move, and a field left as it is, change nothing.
    feature.reset_fins(lined)
    lined.recompute()
    moving.place_handles()
    moving.handle_started(handles.UP)
    moving.finish_drag(handles.UP, 0.0)
    expect(feature.edits(lined, feature.MAIN) == ([], {}, {}), "a click on an arrow alone changes nothing")
    shown = moving.fin_fields[handles.ALONG].value()
    moving.fin_fields[handles.ALONG].setValue(shown)
    moving.field_entered(handles.ALONG)
    expect(feature.edits(lined, feature.MAIN) == ([], {}, {}), "a field left as it is shows, changes nothing")
    # A drag that started on no fin is passed over, without a jump or an error.
    moving.drag_base = {}
    moving.handle_moved(handles.UP, FIN_SHIFT)
    moving.finish_drag(handles.UP, FIN_SHIFT)
    expect(feature.edits(lined, feature.MAIN) == ([], {}, {}), "a drag that never started on a fin changes nothing")
    # A build that fails leaves no old result for the arrows.
    lined.FinCount = TOO_MANY_FINS
    lined.recompute()
    expect(not lined.Proxy.results, "a failed build leaves no old result behind")
    lined.FinCount = 3
    lined.recompute()
    moving.reject()
    expect(not lined.Proxy.results and not lined.Proxy.editing, "without a panel, no build is kept")
    expect(feature.edits(lined, feature.MAIN) == ([], {}, {})
           and moving.handles.arrows.whichChild.getValue() == coin.SO_SWITCH_NONE,
           "Cancel undoes the moves and takes the handles away")
    expect((lined.ViewObject.ShapeAppearance[0].DiffuseColor, lined.ViewObject.Transparency) == look,
           "Cancel gives the fins their look back")
    # Edit mode left another way than OK or Cancel: the panel cleans up all the same.
    leaving = FinSnapTaskPanel(lined)
    lined.ViewObject.Proxy.panel = leaving
    lined.ViewObject.Proxy.unsetEdit(lined.ViewObject)
    expect(leaving.released and lined.ViewObject.Transparency == look[1],
           "leaving edit mode another way takes the arrows away and gives the fins their look back")
    # Another task dialog open: double click opens no fins panel and changes nothing.
    blocker = FinSnapTaskPanel(lined)
    blocker.release_handles()
    Gui.Control.showDialog(blocker)
    expect(lined.ViewObject.Proxy.setEdit(lined.ViewObject) is False and lined.ViewObject.Transparency == look[1],
           "with another task dialog open no panel opens, and the fins keep their look")
    # Fins just made cannot be edited then: they go again, with a message,
    # as there would be no Cancel for them.
    del messages[:]
    blocked = feature.create(row, face_name(row, lower_left_face(row.Shape)))
    commands.ViewProviderFinSnap(blocked.ViewObject)
    doc.recompute()
    blocked_name = blocked.Name
    commands._edit_new(blocked)
    expect(blocked_name not in [o.Name for o in doc.Objects] and len(messages) == 1
           and App.Qt.translate("FinSnap", commands.NOTE_BUSY) in messages[0],
           "new fins that cannot be edited while another task panel is open go again, with a message")
    del messages[:]
    Gui.Control.closeDialog()
    # No 3D view to show the fins in: double click says so instead of failing.
    from freecad.finsnap import handles as handles_module
    real_handles = handles_module.Handles

    def no_view(*args):
        raise handles_module.NoView("no 3D view")

    handles_module.Handles = no_view
    try:
        opened = lined.ViewObject.Proxy.setEdit(lined.ViewObject)
    finally:
        handles_module.Handles = real_handles
    expect(opened is False and messages and "no 3D view" in messages[-1] and not Gui.Control.activeDialog(),
           "without a 3D view no panel opens, and a message says why: %s" % messages)
    # Read from the German file itself: the language FreeCAD runs in may be English.
    # Audited: Parses the German file of this repository.
    import xml.etree.ElementTree as ET  # nosec B405
    from freecad.finsnap.paths import TRANSLATIONS
    no_view_text = "No 3D view of %s is open to edit the fins in."
    # Audited: File of this repository.
    german = ET.parse(os.path.join(TRANSLATIONS, GERMAN)).getroot()  # nosec B314
    expect(any(m.findtext("source") == no_view_text and m.find("translation").get("type") is None
               and m.findtext("translation") for m in german.iter("message")),
           "the message without a 3D view has a German translation")
    del messages[:]
    expect(lined.ViewObject.Proxy.onDelete(lined.ViewObject, ["Vertex1"]) is False
           and lined.Name in [o.Name for o in doc.Objects], "a pick that is no fin deletes nothing")
    # The whole object deleted in the tree while its panel is open: the panel closes first.
    open_panel = FinSnapTaskPanel(lined)
    lined.ViewObject.Proxy.panel = open_panel
    expect(lined.ViewObject.Proxy.onDelete(lined.ViewObject, []) is True and open_panel.released,
           "deleting the object with its panel open closes the panel first")
    lined.ViewObject.Proxy.panel = None
    # The Delete key on every fin: the object goes as a whole, as from the tree.
    every = [face_of_fin(i) for i in range(len(lined.Shape.Solids))]
    expect(lined.ViewObject.Proxy.onDelete(lined.ViewObject, every) is True and lined.FinTags,
           "the Delete key on the last fins deletes the object instead of leaving it broken")
    # The same with the panel open: FreeCAD deletes nothing in edit mode, the panel asks and does it.
    asking = FinSnapTaskPanel(lined)
    lined.ViewObject.Proxy.panel = asking
    question = QtWidgets.QMessageBox.question
    QtWidgets.QMessageBox.question = lambda *args: QtWidgets.QMessageBox.Yes
    try:
        lined.ViewObject.Proxy.onDelete(lined.ViewObject, every)
        # The panel deletes once the Delete command is through.
        QtWidgets.QApplication.processEvents()
    finally:
        QtWidgets.QMessageBox.question = question
    expect(lined.Name not in [o.Name for o in doc.Objects], "with the panel open it asks, then deletes the fins")
    doc.removeObject(row.Name)

    # A face the fins cannot stand under: the panel says why instead of keeping the old result.
    upward = [i for i, f in enumerate(cube.Shape.Faces, 1) if f.normalAt(0, 0).z > 1 - d.TOLERANCE][0]
    wrong = feature.create(cube, "Face%d" % upward)
    wrong_panel = FinSnapTaskPanel(wrong, created=True)
    reason = App.Qt.translate("FinSnap", geometry.NOT_OVERHANGING)
    expect(reason in wrong_panel.notes.text() and not wrong_panel.notes.isHidden()
           and taskpanel.ERROR_COLOR in wrong_panel.notes.styleSheet(),
           "the panel shows in a red box why no fins can be built: %s" % wrong_panel.notes.text())
    expect(not wrong_panel.accept(), "OK is refused while no fins can be built")
    wrong_panel.reject()

    # Export: the file is written, gets its extension and holds two objects.
    select(cube)
    Gui.Selection.addSelection(fins)
    Gui.runCommand("FinSnap_Export3MF")
    written = target + ".3mf"
    expect(not messages, "export reports no error: %s" % messages)
    expect(os.path.exists(written), "export writes the file and adds .3mf")
    with zipfile.ZipFile(written) as archive:
        model = archive.read("3D/3dmodel.model").decode()
    expect(model.count("<object ") == 2, "the file holds part and fins as two objects")

    # STEP: the same selection, exact surfaces, part and fins under their names.
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (target, ""))
    Gui.runCommand("FinSnap_ExportSTEP")
    stepped = target + ".step"
    expect(not messages and os.path.exists(stepped), "STEP export writes the file and adds .step")
    import Import
    reread = App.newDocument("StepReread", hidden=True, temp=True)
    Import.insert(stepped, reread.Name)
    names = sorted(o.Label for o in reread.Objects if o.TypeId == "Part::Feature")
    App.closeDocument(reread.Name)
    expect(names == sorted([cube.Label, cube.Label + commands.FINS_SUFFIX]),
           "the STEP file holds part and fins under their names: %s" % names)

    # Export with nothing selected: every fin object of the document with its part.
    Gui.Selection.clearSelection()
    whole = os.path.join(folder, "document.3mf")
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (whole, ""))
    Gui.runCommand("FinSnap_Export3MF")
    with zipfile.ZipFile(whole) as archive:
        model = archive.read("3D/3dmodel.model").decode()
    expect(model.count("<object ") == 2, "export without a selection takes all fins with their parts")
    turned_tube(doc)
    added_on_tube(doc)
    quick_on_split_tube(doc)
    moved_beside_groove(doc)

    empty = doc.addObject("Part::Feature", "Empty")
    select(empty)
    Gui.runCommand("FinSnap_Export3MF")
    expect(len(messages) == 1, "exporting an object without a shape shows a message: %s" % messages)
    del messages[:]
    doc.removeObject(empty.Name)

    # Mesh to solid: a mesh of the cube becomes a solid with planar faces.
    import Mesh
    import MeshPart
    mesh = doc.addObject("Mesh::Feature", "CubeMesh")
    mesh.Mesh = MeshPart.meshFromShape(Shape=cube.Shape, LinearDeflection=0.1)
    select(mesh)
    Gui.runCommand("FinSnap_MeshToSolid")
    doc.recompute()
    solids = [o for o in doc.Objects if o.Name.startswith("CubeMesh") and o.TypeId == "Part::Feature"]
    expect(solids and solids[0].Shape.isValid(), "Mesh to solid creates a valid solid")
    # Small corner faces may stay split in two triangles; the faces that carry
    # fins must come back whole.
    converted = solids[0]
    leaning = lower_left_face(converted.Shape)
    expect(abs(leaning.Area - lower_left_face(cube.Shape).Area) < d.TOLERANCE,
           "the leaning face of the mesh comes back as one face")
    on_mesh = feature.create(converted, face_name(converted, leaning))
    doc.recompute()
    expect(on_mesh.Shape.Solids, "fins can be built on a converted mesh")
    del Mesh

    print("all checks passed", file=sys.__stdout__)


run(main, gui=True)
