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
            "FinSnap_MeshToSolid", "FinSnap_Export3MF", "FinSnap_ExportSTEP")
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
GERMAN = "FinSnap_de.ts"  # written by freecad/finsnap/tools/update_translations.sh


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


def select(obj, *subs):
    Gui.Selection.clearSelection()
    if subs:
        for sub in subs:
            Gui.Selection.addSelection(obj, sub)
    else:
        Gui.Selection.addSelection(obj)


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
    expect(len(created) == 1 and Gui.Control.activeDialog(), "Add fins creates the object and opens the panel")
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
    select(lined, face_of_fin(0))
    before = lined.Shape.Solids[0].BoundBox.Center
    held = dict(moving.handles.draggers)
    place = moving.fin_fields[handles.ALONG].value()
    moving.handle_started(handles.ALONG)
    moving.handle_moved(handles.ALONG, FIN_SHIFT)
    expect(abs(moving.fin_fields[handles.ALONG].value() - (place + FIN_SHIFT)) < d.TOLERANCE,
           "the field follows the arrow while it is dragged")
    moving.drag_step()
    expect(abs(lined.Shape.Solids[0].BoundBox.Center.sub(before).Length - FIN_SHIFT) < d.TOLERANCE
           and feature.edits(lined, feature.MAIN)[1] == {1: FIN_SHIFT},
           "a dragged fin is built where the arrow is, while it is held")
    moving.finish_drag(handles.ALONG, FIN_SHIFT)
    expect(feature.edits(lined, feature.MAIN)[1] == {1: FIN_SHIFT}
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_NONE,
           "a fin let go stays there")
    expect(all(moving.handles.draggers[kind] is held[kind] for kind in held),
           "the arrows stay the same after a move; Coin may still hold the one let go")
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
    moving.finish_drag(handles.ALONG, onto_neighbour)
    expect(feature.edits(lined, feature.MAIN)[1] == {1: FIN_SHIFT}
           and moving.handles.preview.whichChild.getValue() == coin.SO_SWITCH_NONE,
           "let go there, it stays at its last place")
    lower = result.heights[1] - FIN_SHIFT
    moving.fin_fields[handles.UP].setValue(lower)
    moving.field_entered(handles.UP)
    lowered = lined.Proxy.results[feature.MAIN]
    expect(abs(lowered.heights[1] - lower) < d.TOLERANCE, "a height typed into the field sets the fin's height")
    moving.fin_fields[handles.ALONG].setValue(place)
    moving.field_entered(handles.ALONG)
    expect(not feature.edits(lined, feature.MAIN)[1], "a place typed into the field moves the fin there")
    lowered = lined.Proxy.results[feature.MAIN]
    expect(App.Vector(*moving.handles.places[handles.UP].translation.getValue().getValue())
           .sub(lowered.edges[1]).Length < d.TOLERANCE,
           "the arrows follow to the upright outer edge of the fin")
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
    commands._edit_new(lined)
    expect(not getattr(lined.ViewObject.Proxy, "created", False),
           "fins opened while another dialog is open are not taken as just made")
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
    reason = App.Qt.translate("FinSnap", "the selected face does not lean over the bed")
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
