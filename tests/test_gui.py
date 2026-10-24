"""The commands as a user runs them, in a FreeCAD with GUI but without a screen.

Run from the repository root:
    QT_QPA_PLATFORM=offscreen freecad tests/test_gui.py

Dialogs that would wait for a click are replaced by fixed answers; everything
else, from the selection to the written file, runs as in FreeCAD.
"""

import math
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import FreeCADGui as Gui  # noqa: E402
import Part  # noqa: E402
from pivy import coin  # noqa: E402
from PySide import QtWidgets  # noqa: E402
from support import STANDARD_THICKNESS, expect, lower_left_face, run, tilted_cube  # noqa: E402

WORKBENCH = "FinSnapWorkbench"
COMMANDS = ("FinSnap_Tilt", "FinSnap_LayFlat", "FinSnap_AddFins", "FinSnap_AddCounterFin", "FinSnap_MeshToSolid",
            "FinSnap_Export3MF")
DIALOG_ACCEPTED = 1
FLAT_TILT = 30.0  # flatter than the overhang limit
CHAMFER = 3.0


def load_workbench():
    # Installed copies register themselves at start-up; a checkout does so on import.
    if WORKBENCH not in Gui.listWorkbenches():
        import freecad.finsnap.init_gui  # noqa: F401
    Gui.activateWorkbench(WORKBENCH)
    from freecad.finsnap import commands
    return commands


def answer_dialogs(commands, save_path, angle):
    """Replace every dialog that waits for the user by a fixed answer."""
    messages = []
    QtWidgets.QDialog.exec = lambda self: DIALOG_ACCEPTED
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (save_path, ""))
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (angle, True))
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
    select(box, "Edge%d" % top)
    Gui.runCommand("FinSnap_Tilt")
    expect(len(messages) == 1 and box.Placement.isIdentity(), "a top edge alone is refused with a message")
    del messages[:]
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

    # Laid flat, the fins cannot be built any more; the marks follow the part all the same.
    select(box)
    Gui.runCommand("FinSnap_LayFlat")
    doc.recompute()
    expect(not marked.isValid() and marked.Overhangs == [] and marks.getNumChildren() == 0,
           "when the fins fail, the marks still follow the part")
    marked.ViewObject.Proxy.onDelete(marked.ViewObject, [])
    doc.removeObject(marked.Name)
    QtWidgets.QInputDialog.getDouble = staticmethod(lambda *a, **k: (d.TILT_ANGLE, True))

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

    # Export with nothing selected: every fin object of the document with its part.
    Gui.Selection.clearSelection()
    whole = os.path.join(folder, "document.3mf")
    QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (whole, ""))
    Gui.runCommand("FinSnap_Export3MF")
    with zipfile.ZipFile(whole) as archive:
        model = archive.read("3D/3dmodel.model").decode()
    expect(model.count("<object ") == 2, "export without a selection takes all fins with their parts")

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
