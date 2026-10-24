"""Workbench commands and the view provider of the FinSnap object."""

import os

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtWidgets

from . import defaults as d
from . import export_3mf
from . import feature
from . import mesh_input
from . import orient
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import global_shape, outermost
from .taskpanel import LENGTH_SUFFIX, FinSnapTaskPanel

ICONS = os.path.join(os.path.dirname(__file__), "icons")
ICON_WORKBENCH = os.path.join(ICONS, "finsnap.svg")
ICON_ADD = os.path.join(ICONS, "add_fins.svg")
ICON_MESH = os.path.join(ICONS, "mesh_to_solid.svg")
ICON_EXPORT = os.path.join(ICONS, "export_3mf.svg")
ICON_TILT = os.path.join(ICONS, "tilt.svg")
ICON_COUNTER = os.path.join(ICONS, "counter_fin.svg")
EDGE_PREFIX = "Edge"
TILT_DECIMALS = 1

FACE_PREFIX = "Face"
FILE_FILTER = QT_TRANSLATE_NOOP("FinSnap", "3MF files (*.3mf)")
FILE_EXTENSION = ".3mf"
PREFERENCES = "User parameter:BaseApp/Preferences/Mod/FinSnap"
PREF_LINEAR = "MeshLinearDeflection"
PREF_ANGULAR = "MeshAngularDeflection"
MESH_LINEAR_RANGE = (0.001, 1.0)
MESH_ANGULAR_RANGE = (0.1, 30.0)
MESH_LINEAR_DECIMALS = 3
MESH_ANGULAR_DECIMALS = 1
SOLID_SUFFIX = "_solid"
FINS_SUFFIX = "_fins"


class ViewProviderFinSnap:
    def __init__(self, vobj):
        vobj.Proxy = self

    def getIcon(self):  # noqa: N802 - FreeCAD API
        return ICON_ADD

    def attach(self, vobj):
        self.Object = vobj.Object

    def setEdit(self, vobj, mode=0):  # noqa: N802 - FreeCAD API
        Gui.Control.showDialog(FinSnapTaskPanel(vobj.Object))
        return True

    def unsetEdit(self, vobj, mode=0):  # noqa: N802 - FreeCAD API
        Gui.Control.closeDialog()
        return True

    def claimChildren(self):  # noqa: N802 - FreeCAD API
        return []

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _selected_faces():
    """(object, face name) for every selected face, in selection order."""
    faces = []
    for sel in Gui.Selection.getSelectionEx():
        for name in sel.SubElementNames:
            if name.startswith(FACE_PREFIX):
                faces.append((sel.Object, name))
    return faces


def _message(text):
    QtWidgets.QMessageBox.information(Gui.getMainWindow(), "FinSnap", text)


class TiltOntoEdge:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_TILT,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_Tilt", "Stand on edge"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_Tilt",
                    "Select a bottom edge of a part lying on the bed. The part is turned about "
                    "that edge by the tilt angle and set back onto the bed, standing on the edge.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return App.ActiveDocument is not None

    def Activated(self):  # noqa: N802 - FreeCAD API
        picked = [(sel.Object, name) for sel in Gui.Selection.getSelectionEx()
                  for name in sel.SubElementNames if name.startswith(EDGE_PREFIX)]
        if len(picked) != 1:
            _message(translate("FinSnap", "Select exactly one bottom edge of the part."))
            return
        obj, edge_name = picked[0]
        angle, ok = QtWidgets.QInputDialog.getDouble(
            Gui.getMainWindow(), translate("FinSnap", "Stand on edge"), translate("FinSnap", "Tilt angle (degrees):"),
            d.TILT_ANGLE, 1.0, 89.0, TILT_DECIMALS)
        if not ok:
            return
        try:
            shape = global_shape(obj)
            change = orient.tilt(shape, shape.getElement(edge_name), angle)
        except orient.OrientError as error:
            _message(str(error))
            return
        doc = App.ActiveDocument
        doc.openTransaction(translate("FinSnap", "Stand on edge"))
        owner = outermost(obj)
        owner.Placement = change.multiply(owner.Placement)
        doc.commitTransaction()
        doc.recompute()


class AddFins:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_ADD,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_AddFins", "Add fins"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_AddFins",
                    "Select the face that leans over the bed; optionally a second face on the "
                    "opposite side for a counter fin")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return App.ActiveDocument is not None

    def Activated(self):  # noqa: N802 - FreeCAD API
        faces = _selected_faces()
        if not faces or len(faces) > 2:
            _message(translate("FinSnap", "Select one face to support, or two faces for a counter fin."))
            return
        base, face_name = faces[0]
        counter = faces[1] if len(faces) == 2 else None
        doc = App.ActiveDocument
        doc.openTransaction(translate("FinSnap", "Add fins"))
        obj = feature.create(base, face_name, counter)
        ViewProviderFinSnap(obj.ViewObject)
        doc.commitTransaction()
        Gui.Control.showDialog(FinSnapTaskPanel(obj, created=True))


class AddCounterFin:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_COUNTER,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_AddCounterFin", "Add counter fin"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_AddCounterFin",
                    "Adds a fin on the opposite side of existing fins, against tipping away, as large as the "
                    "main fin; fewer counter tines in the panel make it smaller. "
                    "Select the fins: the face leaning the other way is found automatically. Or "
                    "select a face of the part as well to choose it yourself. To remove the counter "
                    "fin, clear its face in the property view.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return any(_is_fins(o) for o in Gui.Selection.getSelection()) or bool(_selected_faces())

    def Activated(self):  # noqa: N802 - FreeCAD API
        doc = App.ActiveDocument
        fins = [o for o in Gui.Selection.getSelection() if _is_fins(o)]
        faces = [(o, n) for o, n in _selected_faces() if not _is_fins(o)]
        if not fins and faces:
            part = faces[0][0]
            fins = [o for o in doc.Objects if _is_fins(o) and o.Base and o.Base[0] == part]
        if len(fins) != 1 or len(faces) > 1:
            _message(translate("FinSnap", "Select one fin object, and optionally one face of its part."))
            return
        doc.openTransaction(translate("FinSnap", "Add counter fin"))
        if faces:
            found = feature.add_counter(fins[0], faces[0][0], faces[0][1])
        else:
            found = feature.add_counter(fins[0])
        doc.commitTransaction()
        if found is None:
            _message(translate("FinSnap", "The part has no face leaning the other way. Select one yourself."))
            return
        doc.recompute()


class MeshToSolid:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_MESH,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_MeshToSolid", "Mesh to solid"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_MeshToSolid",
                    "Turn a selected STL mesh into a solid with planar faces, so fins can be added")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return any(o.isDerivedFrom("Mesh::Feature") for o in Gui.Selection.getSelection())

    def Activated(self):  # noqa: N802 - FreeCAD API
        doc = App.ActiveDocument
        for mesh_obj in Gui.Selection.getSelection():
            if not mesh_obj.isDerivedFrom("Mesh::Feature"):
                continue
            try:
                solid = mesh_input.solid_from_mesh(mesh_obj.Mesh)
            except ValueError as error:
                _message("%s: %s" % (mesh_obj.Label, error))
                continue
            part = doc.addObject("Part::Feature", mesh_obj.Name + SOLID_SUFFIX)
            part.Label = mesh_obj.Label + SOLID_SUFFIX
            part.Shape = solid
            mesh_obj.Visibility = False
        doc.recompute()


def _is_fins(obj):
    return getattr(obj, "Proxy", None).__class__.__name__ == "FinSnapFeature"


def _to_export():
    """The selection, or every fin object of the document when nothing is selected."""
    selected = Gui.Selection.getSelection()
    if selected or App.ActiveDocument is None:
        return selected
    return [o for o in App.ActiveDocument.Objects if _is_fins(o)]


def _export_list(objects):
    """Named shapes to export. A separate FinSnap object brings its part along."""
    shapes = []
    seen = set()
    for obj in objects:
        if _is_fins(obj) and obj.Connection == d.CONNECTION_SEPARATE:
            base = obj.Base[0]
            if base.Name not in seen:
                shapes.append((base.Label, global_shape(base)))
                seen.add(base.Name)
            shapes.append((base.Label + FINS_SUFFIX, obj.Shape))
        elif obj.Name not in seen and isinstance(getattr(obj, "Shape", None), Part.Shape):
            shapes.append((obj.Label, global_shape(obj)))
        seen.add(obj.Name)
    return shapes


def _mesh_settings():
    """Ask for the mesh fineness, starting from the last values used. None if cancelled."""
    prefs = App.ParamGet(PREFERENCES)
    dialog = QtWidgets.QDialog(Gui.getMainWindow())
    dialog.setWindowTitle(translate("FinSnap", "Mesh fineness"))
    form = QtWidgets.QFormLayout(dialog)

    linear = QtWidgets.QDoubleSpinBox()
    linear.setRange(*MESH_LINEAR_RANGE)
    linear.setDecimals(MESH_LINEAR_DECIMALS)
    linear.setSuffix(LENGTH_SUFFIX)
    linear.setValue(prefs.GetFloat(PREF_LINEAR, d.MESH_LINEAR_DEFLECTION))
    form.addRow(translate("FinSnap", "Surface deviation"), linear)

    angular = QtWidgets.QDoubleSpinBox()
    angular.setRange(*MESH_ANGULAR_RANGE)
    angular.setDecimals(MESH_ANGULAR_DECIMALS)
    angular.setSuffix(" \N{DEGREE SIGN}")
    angular.setValue(prefs.GetFloat(PREF_ANGULAR, d.MESH_ANGULAR_DEFLECTION_DEG))
    form.addRow(translate("FinSnap", "Angular deviation"), angular)

    note = QtWidgets.QLabel(translate("FinSnap", "Planar faces are exported exactly; these values only "
                                      "affect curved surfaces."))
    note.setWordWrap(True)
    form.addRow(note)
    standard = QtWidgets.QDialogButtonBox.StandardButton
    buttons = QtWidgets.QDialogButtonBox(standard.Ok | standard.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if not dialog.exec():
        return None
    prefs.SetFloat(PREF_LINEAR, linear.value())
    prefs.SetFloat(PREF_ANGULAR, angular.value())
    return linear.value(), angular.value()


class Export3MF:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_EXPORT,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_Export3MF", "Export 3MF"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_Export3MF",
                    "Export the selection to 3MF, every body as its own object for the slicer. With "
                    "nothing selected, all fins of the document are exported together with their parts.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return bool(_to_export())

    def Activated(self):  # noqa: N802 - FreeCAD API
        shapes = _export_list(_to_export())
        settings = _mesh_settings()
        if settings is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            Gui.getMainWindow(), translate("FinSnap", "Export 3MF"), "", translate("FinSnap", FILE_FILTER))
        if not path:
            return
        if not path.lower().endswith(FILE_EXTENSION):
            path += FILE_EXTENSION
        try:
            export_3mf.write(path, shapes, *settings)
        except (ValueError, OSError, Part.OCCError) as error:
            _message(str(error))
            return
        App.Console.PrintMessage("FinSnap: %d objects written to %s\n" % (len(shapes), path))


COMMANDS = (("FinSnap_Tilt", TiltOntoEdge()),
            ("FinSnap_AddFins", AddFins()),
            ("FinSnap_AddCounterFin", AddCounterFin()),
            ("FinSnap_MeshToSolid", MeshToSolid()),
            ("FinSnap_Export3MF", Export3MF()))


def register():
    for name, command in COMMANDS:
        Gui.addCommand(name, command)
    return [name for name, _ in COMMANDS]
