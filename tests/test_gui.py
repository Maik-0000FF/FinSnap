"""The commands as a user runs them, in a FreeCAD with GUI but without a screen.

Run from the repository root:
    QT_QPA_PLATFORM=offscreen freecad tests/test_gui.py

Dialogs that would wait for a click are replaced by fixed answers; everything
else, from the selection to the written file, runs as in FreeCAD.
"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App  # noqa: E402
import FreeCADGui as Gui  # noqa: E402
import Part  # noqa: E402
from PySide import QtWidgets  # noqa: E402
from support import expect, lower_left_face, run, tilted_cube  # noqa: E402

WORKBENCH = "FinSnapWorkbench"
COMMANDS = ("FinSnap_Tilt", "FinSnap_AddFins", "FinSnap_AddCounterFin", "FinSnap_MeshToSolid",
            "FinSnap_Export3MF")
DIALOG_ACCEPTED = 1


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
    panel.widgets["TineCount"].setValue(2)
    panel.preview()
    expect(fins.TineCount == 2 and fins.ResultHeight.Value < 11.2, "preview applies a changed value")
    panel.widgets["TineCount"].setValue(0)
    panel.apply()

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
