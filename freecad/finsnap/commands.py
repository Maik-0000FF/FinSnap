"""Workbench commands and the view provider of the FinSnap object."""

import dataclasses
import os
from collections import namedtuple

import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from PySide import QtWidgets

from . import defaults as d
from . import export_3mf
from . import export_step
from . import feature
from . import geometry
from . import mesh_input
from . import orient
from . import presets
from .i18n import QT_TRANSLATE_NOOP, translate
from .presets import PREFERENCES
from .shapes import FACE_PREFIX, face_name, global_shape, moved, outermost
from .taskpanel import LENGTH_SUFFIX, FinSnapTaskPanel
from .version import NAME

ICONS = os.path.join(os.path.dirname(__file__), "icons")
ICON_WORKBENCH = os.path.join(ICONS, "finsnap.svg")
ICON_ADD = os.path.join(ICONS, "add_fins.svg")
ICON_MESH = os.path.join(ICONS, "mesh_to_solid.svg")
ICON_EXPORT = os.path.join(ICONS, "export_3mf.svg")
ICON_EXPORT_STEP = os.path.join(ICONS, "export_step.svg")
ICON_QUICK = os.path.join(ICONS, "quick_fins.svg")
ICON_TILT = os.path.join(ICONS, "tilt.svg")
ICON_LAY_FLAT = os.path.join(ICONS, "lay_flat.svg")
ICON_COUNTER = os.path.join(ICONS, "counter_fin.svg")
EDGE_PREFIX = "Edge"
TILT_DECIMALS = 1
# Order in which App.Rotation keeps the given camera axes exact.
CAMERA_AXES = "ZYX"
# Direction FreeCAD's isometric view looks along.
ISOMETRIC = App.Vector(-1, 1, -1).normalize()

# File types of the exports: the filter of the save dialog, and the endings
# it accepts; the first is added to a name that has none of them.
FILTER_3MF = QT_TRANSLATE_NOOP("FinSnap", "3MF files (*.3mf)")
EXTENSIONS_3MF = (".3mf",)
FILTER_STEP = QT_TRANSLATE_NOOP("FinSnap", "STEP files (*.step *.stp)")
EXTENSIONS_STEP = (".step", ".stp")
PREF_LINEAR = "MeshLinearDeflection"
PREF_ANGULAR = "MeshAngularDeflection"
MESH_LINEAR_RANGE = (0.001, 1.0)
MESH_ANGULAR_RANGE = (0.1, 30.0)
MESH_LINEAR_DECIMALS = 3
MESH_ANGULAR_DECIMALS = 1
DEGREE_SUFFIX = " \N{DEGREE SIGN}"
SOLID_SUFFIX = "_solid"
FINS_SUFFIX = "_fins"
# Marks on faces that overhang without fins: red, half see-through, drawn
# slightly in front of the part's own faces, which lie in the same place.
OVERHANG_COLOR = (0.9, 0.1, 0.1)
OVERHANG_TRANSPARENCY = 0.4
OVERHANG_OFFSET = -1.0
OVERHANG_MESH = 0.1  # largest deviation of the marks from the face (mm)
STATUS_TIMEOUT_MS = 10000
# What an export writes, and the fins it leaves out because their part lies flat.
Export = namedtuple("Export", "shapes left_out")


class ViewProviderFinSnap:
    def __init__(self, vobj):
        vobj.Proxy = self

    def getIcon(self):  # noqa: N802 - FreeCAD API
        return ICON_ADD

    def attach(self, vobj):
        self.Object = vobj.Object
        self.marks = coin.SoSwitch()
        vobj.RootNode.addChild(self.marks)
        self.mark(vobj.Object)

    def updateData(self, obj, prop):  # noqa: N802 - FreeCAD API
        if prop == feature.OVERHANGS:
            self.mark(obj)

    def onChanged(self, vobj, prop):  # noqa: N802 - FreeCAD API
        if prop == "Visibility" and hasattr(self, "marks"):
            self.show_marks(vobj.Visibility)

    def show_marks(self, visible):
        self.marks.whichChild.setValue(coin.SO_SWITCH_ALL if visible else coin.SO_SWITCH_NONE)

    def mark(self, obj):
        """Cover the faces that overhang without fins with red marks."""
        if not hasattr(self, "marks"):
            return
        self.marks.removeAllChildren()
        names = getattr(obj, feature.OVERHANGS, [])
        if not names or not obj.Base:
            return
        try:
            shape = global_shape(obj.Base[0])
        except ValueError:
            return
        points, index = [], []
        for name in names:
            vertices, triangles = shape.getElement(name).tessellate(OVERHANG_MESH)
            first = len(points)
            points += [(v.x, v.y, v.z) for v in vertices]
            for triangle in triangles:
                index += [first + corner for corner in triangle] + [-1]

        material = coin.SoMaterial()
        material.diffuseColor.setValue(*OVERHANG_COLOR)
        material.transparency.setValue(OVERHANG_TRANSPARENCY)
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(OVERHANG_OFFSET)
        offset.units.setValue(OVERHANG_OFFSET)
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, len(points), points)
        faces = coin.SoIndexedFaceSet()
        faces.coordIndex.setValues(0, len(index), index)
        group = coin.SoSeparator()
        for node in (material, offset, coordinates, faces):
            group.addChild(node)
        self.marks.addChild(group)
        self.show_marks(obj.ViewObject.Visibility)

    def setEdit(self, vobj, mode=0):  # noqa: N802 - FreeCAD API
        Gui.Control.showDialog(FinSnapTaskPanel(vobj.Object))
        return True

    def unsetEdit(self, vobj, mode=0):  # noqa: N802 - FreeCAD API
        Gui.Control.closeDialog()
        return True

    def claimChildren(self):  # noqa: N802 - FreeCAD API
        return []

    def onDelete(self, vobj, subelements):  # noqa: N802 - FreeCAD API
        """Deleting the last fins of a part stood on an edge lays the part flat again."""
        obj = vobj.Object
        if obj.Base:
            owner = outermost(obj.Base[0])
            others = [o for o in feature.fins_of(owner, obj.Document) if o is not obj]
            if not others:
                orient.lay_back(owner)
            for other in others:
                other.touch()
        return True

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
    QtWidgets.QMessageBox.information(Gui.getMainWindow(), NAME, text)


class TiltOntoEdge:
    """Stand a part on an edge, or lay one of its faces onto the bed.

    SELECTIONS this has to withstand:
      one edge on the bed                   ->  turned about it by the asked angle
      one edge off the bed between two flat
        faces at a right angle              ->  stands on it at 45 degrees, no angle asked
      one edge off the bed, other faces     ->  message, nothing changed
      one edge and one of its faces         ->  face laid down, then turned about the edge
      one face alone (a chamfer)            ->  face laid onto the bed, no angle asked
      two faces (beside a fillet)           ->  part stands on what joins them, both
                                                faces equally steep, no angle asked
      two faces and an edge                 ->  message, nothing changed
      nothing, two edges, two faces, or
        edge and face of different parts    ->  message, nothing changed
      cancelled angle                       ->  nothing changed
      edge or face the part cannot stand on ->  message naming why, nothing changed
    """

    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_TILT,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_Tilt", "Stand on edge"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_Tilt",
                    "Select an edge of the part and the face of that edge that is to lie on the bed. "
                    "The face is laid onto the bed, the part is turned about the edge by the tilt angle "
                    "and set back onto the bed, standing on the edge. For an edge already on the bed, "
                    "the edge alone is enough; so it is for an edge between two flat faces at a right "
                    "angle, on which the part stands at 45 degrees. A face alone, a chamfer or a fillet, "
                    "is laid onto the bed and carries the part: a chamfer lies flat on it, a fillet "
                    "touches it along its middle. Two faces alone, such as the two beside a fillet, "
                    "stand the part on what joins them, both equally steep.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return App.ActiveDocument is not None

    def Activated(self):  # noqa: N802 - FreeCAD API
        picked, edges, faces = _picked()
        valid = (picked and len({id(o) for o, _ in picked}) == 1
                 and ((len(edges) == 1 and len(faces) <= 1) or (not edges and len(faces) <= 2)))
        if not valid:
            _message(translate("FinSnap", "Select one edge of the part, and the face of that edge that is "
                                          "to lie on the bed; or a face alone, a chamfer or a fillet; "
                                          "or the two faces beside it."))
            return
        obj = picked[0][0]
        try:
            shape = global_shape(obj)
            chosen = [shape.getElement(name) for _, name in faces]
            face = chosen[0] if chosen else None
            edge = None
            if len(chosen) == 2:
                change = orient.rest_between(shape, *chosen)
            elif edges:
                edge = shape.getElement(edges[0][1])
                if face is None and not orient.on_bed(shape, edge):
                    # The angle is fixed by the right angle between its faces.
                    change = orient.stand(shape, edge, orient.RIGHT_ANGLE_TILT)
                else:
                    angle, ok = QtWidgets.QInputDialog.getDouble(
                        Gui.getMainWindow(), translate("FinSnap", "Stand on edge"),
                        translate("FinSnap", "Tilt angle (degrees):"), d.TILT_ANGLE, 1.0, 89.0, TILT_DECIMALS)
                    if not ok:
                        return
                    change = orient.stand(shape, edge, angle, face)
            else:
                change = orient.lay_flat(shape, face)
        except orient.OrientError as error:
            _message(str(error))
            return
        doc = App.ActiveDocument
        doc.openTransaction(translate("FinSnap", "Stand on edge"))
        _stand(obj, change)
        doc.commitTransaction()
        doc.recompute()
        _show_on_bed(orient.side_direction(change, edge, chosen if len(chosen) == 2 else ()))
        _report_overhangs(obj)


def _picked():
    """The selected edges and faces: (all, edges, faces), each as (object, name)."""
    picked = [(sel.Object, name) for sel in Gui.Selection.getSelectionEx()
              for name in sel.SubElementNames if name.startswith((EDGE_PREFIX, FACE_PREFIX))]
    return (picked, [(o, n) for o, n in picked if n.startswith(EDGE_PREFIX)],
            [(o, n) for o, n in picked if n.startswith(FACE_PREFIX)])


def _stand(obj, change):
    """Turn the part of `obj` by `change`, keeping where it lay for Lay flat again."""
    owner = outermost(obj)
    orient.remember_flat(owner)
    owner.Placement = change.multiply(owner.Placement)


def _show_on_bed(direction=None):
    """Look at the turned part with the bed below, all of it in view.

    Along `direction`, the line the part stands on, the view shows the tilt
    angle in profile; without one it is isometric. The camera does not follow a
    placement change, so the part would otherwise turn away under it.

    The orientation is set on the camera node itself: setCameraOrientation()
    and viewIsometric() only start an animation when navigation animations are
    on, and fitAll() would then fit the part to where the camera started from.
    """
    view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
    # The active view may be a spreadsheet or a drawing, which has no camera.
    if view is None or not hasattr(view, "getCameraNode"):
        return
    # The camera looks along its -Z with +Y up: -Z onto the line of sight, +Y
    # towards the vertical, +X to the right of both.
    back = -(direction if direction is not None else ISOMETRIC)
    turn = App.Rotation(orient.UP.cross(back), orient.UP, back, CAMERA_AXES)
    view.getCameraNode().orientation.setValue(coin.SbRotation(*turn.Q))
    view.fitAll()


def _report_overhangs(obj):
    """Select the faces that overhang after the tilt and say so in the status bar.
    Faces that already carry fins are left out."""
    names = feature.overhangs_of(obj, obj.Document)
    if not names:
        return
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(obj, names)
    text = translate("FinSnap", "%d faces overhang flatter than %.0f degrees and are selected: they need "
                                "fins or support.") % (len(names), d.OVERHANG_ANGLE)
    Gui.getMainWindow().statusBar().showMessage(text, STATUS_TIMEOUT_MS)
    App.Console.PrintWarning("FinSnap: %s %s\n" % (text, ", ".join(names)))


def _owners(objects):
    """The moved containers of the selected parts; for fins, of the part they support."""
    owners = []
    for obj in objects:
        part = obj.Base[0] if feature.is_fins(obj) and obj.Base else obj
        owner = outermost(part)
        if owner not in owners:
            owners.append(owner)
    return owners


class LayFlat:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_LAY_FLAT,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_LayFlat", "Lay flat again"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_LayFlat",
                    "Puts a part stood on an edge back as it lay before. Select the part or its fins. "
                    "If the part has fins, it asks whether to delete them; kept fins move along with the "
                    "part and are rebuilt once it is moved again. Deleting the last fins of a part lays it "
                    "flat as well.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return bool(Gui.Selection.getSelection())

    def Activated(self):  # noqa: N802 - FreeCAD API
        """
        SITUATIONS this has to withstand:
          part without fins                     ->  laid flat, no question
          part with fins, answer Yes            ->  fins deleted, part laid flat
          part with fins, answer No             ->  part laid flat, fins moved along and kept
          part with fins, answer Cancel         ->  nothing changed
          part not stood with Stand on edge     ->  message, nothing changed
        """
        doc = App.ActiveDocument
        owners = [owner for owner in _owners(Gui.Selection.getSelection())
                  if orient.back_to_flat(owner) is not None]
        if not owners:
            _message(translate("FinSnap", "The selection was not stood on an edge with Stand on edge."))
            return
        delete = False
        if any(feature.fins_of(owner, doc) for owner in owners):
            answer = _ask_delete_fins()
            if answer == QtWidgets.QMessageBox.Cancel:
                return
            delete = answer == QtWidgets.QMessageBox.Yes
        doc.openTransaction(translate("FinSnap", "Lay flat again"))
        for owner in owners:
            change = orient.back_to_flat(owner)
            for fins in feature.fins_of(owner, doc):
                if delete:
                    doc.removeObject(fins.Name)
                else:
                    feature.keep_laid_flat(fins, change)
            orient.lay_back(owner)
        doc.commitTransaction()
        doc.recompute()
        _show_on_bed()


def _ask_delete_fins():
    """Yes, No or Cancel: whether the fins of a part laid flat go with it."""
    buttons = QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
    return QtWidgets.QMessageBox.question(
        Gui.getMainWindow(), NAME,
        translate("FinSnap", "Delete the fins of the part as well? No keeps them, moved along with the part, "
                             "and rebuilds them once it is moved again, for example stood on its edge."),
        buttons, QtWidgets.QMessageBox.No)


class QuickFins:
    """Stand a part up and add its fins in one step.

    The selections it takes are those of geometry.quick_plan(); faces count in
    the order selected.

    SELECTIONS this has to withstand:
      what quick_plan() takes               ->  stood, fins added, panel opened
      nothing, or elements of two parts     ->  message, nothing changed
      what quick_plan() refuses             ->  message naming why, nothing changed
    """

    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_QUICK,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_QuickFins", "Quick fins"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_QuickFins",
                    "Stands the part up and adds one fin in the middle of a face in one step, then opens "
                    "the panel to adjust it. "
                    "Select the edge the part is to stand on: the fins go under the largest face that "
                    "leans over the bed. Or select the face the fins are to support: the part is turned "
                    "so that it leans 45 degrees over the bed, on its longest edge; select one of its "
                    "edges as well to stand on that one, or, after the face, a chamfer or fillet to rest "
                    "on. A fillet alone, or the two faces beside it, carry the part as well. A counter "
                    "fin is added on the opposite face where one fits.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return App.ActiveDocument is not None

    def Activated(self):  # noqa: N802 - FreeCAD API
        picked, edges, faces = _picked()
        if not picked or len({id(o) for o, _ in picked}) != 1:
            _message(translate("FinSnap", "Select an edge or a face of one part."))
            return
        obj = picked[0][0]
        # One fin in the middle of the face; the panel can spread more along it.
        p = dataclasses.replace(presets.standard(), placement=d.PLACEMENT_CENTER)
        try:
            shape = global_shape(obj)
            plan = geometry.quick_plan(
                shape, [(shape.getElement(n), None) for _, n in edges],
                [(shape.getElement(n), int(n[len(FACE_PREFIX):]) - 1) for _, n in faces], p, d.TILT_ANGLE)
        except (orient.OrientError, geometry.FinError) as error:
            _message(str(error))
            return
        standing = moved(shape, plan.change)
        counter = geometry.opposite_face(standing, standing.Faces[plan.number])
        if counter is not None:
            try:
                geometry.build(standing, counter, p, tine_count=p.counter_tine_count or None)
                counter = (obj, feature.face_name_of(standing, counter))
            except geometry.FinError:
                counter = None
        doc = App.ActiveDocument
        doc.openTransaction(translate("FinSnap", "Quick fins"))
        _stand(obj, plan.change)
        fins = feature.create(obj, face_name(plan.number + 1), counter)
        fins.FinPlacement = p.placement
        ViewProviderFinSnap(fins.ViewObject)
        doc.commitTransaction()
        doc.recompute()
        _show_on_bed(orient.side_direction(plan.change, plan.edge, plan.beside))
        Gui.Control.showDialog(FinSnapTaskPanel(fins, created=True))


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
        return any(feature.is_fins(o) for o in Gui.Selection.getSelection()) or bool(_selected_faces())

    def Activated(self):  # noqa: N802 - FreeCAD API
        doc = App.ActiveDocument
        fins = [o for o in Gui.Selection.getSelection() if feature.is_fins(o)]
        faces = [(o, n) for o, n in _selected_faces() if not feature.is_fins(o)]
        if not fins and faces:
            part = faces[0][0]
            fins = [o for o in doc.Objects if feature.is_fins(o) and o.Base and o.Base[0] == part]
        if len(fins) != 1 or len(faces) > 1:
            _message(translate("FinSnap", "Select one fin object, and optionally one face of its part."))
            return
        if faces and fins[0].Base and faces[0][0] is not fins[0].Base[0]:
            _message(translate("FinSnap", "The face for the counter fin has to belong to the part the fins "
                                          "stand under."))
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


def _to_export():
    """The selection, or every fin object of the document when nothing is selected."""
    selected = Gui.Selection.getSelection()
    if selected or App.ActiveDocument is None:
        return selected
    return [o for o in App.ActiveDocument.Objects if feature.is_fins(o)]


def _export_list(objects):
    """What to export: named shapes, and the fins left out because their part lies flat.

    SELECTIONS this has to withstand:
      separate fins                         ->  their part, then the fins
      merged fins, or any other body        ->  that body
      fins whose part lies flat             ->  left out and named; their part
                                                only if it was selected itself
      nothing left after that               ->  ValueError saying why
    """
    shapes = []
    left_out = []
    seen = set()
    for obj in objects:
        if feature.is_fins(obj) and feature.is_laid_flat(obj):
            left_out.append(obj.Label)
        elif feature.is_fins(obj) and obj.Connection == d.CONNECTION_SEPARATE:
            base = obj.Base[0]
            if base.Name not in seen:
                shapes.append((base.Label, global_shape(base)))
                seen.add(base.Name)
            shapes.append((base.Label + FINS_SUFFIX, obj.Shape))
        elif obj.Name not in seen and isinstance(getattr(obj, "Shape", None), Part.Shape):
            shapes.append((obj.Label, global_shape(obj)))
        seen.add(obj.Name)
    if not shapes and left_out:
        raise ValueError(translate("FinSnap", "nothing to export: the parts of %s lie flat; stand them on their "
                                              "edge again") % ", ".join(left_out))
    return Export(shapes, left_out)


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
    angular.setSuffix(DEGREE_SUFFIX)
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
        export = _shapes_to_export()
        if export is None:
            return
        settings = _mesh_settings()
        if settings is None:
            return
        path = _save_path(translate("FinSnap", "Export 3MF"), FILTER_3MF, EXTENSIONS_3MF)
        if path:
            _write(export_3mf.write, path, export, *settings)


class ExportSTEP:
    def GetResources(self):  # noqa: N802 - FreeCAD API
        return {"Pixmap": ICON_EXPORT_STEP,
                "MenuText": QT_TRANSLATE_NOOP("FinSnap_ExportSTEP", "Export STEP"),
                "ToolTip": QT_TRANSLATE_NOOP(
                    "FinSnap_ExportSTEP",
                    "Export the selection to STEP, with exact surfaces instead of a mesh. The slicer "
                    "loads it as one object with a part per body: split it into objects there, so part "
                    "and fins are printed separately. With nothing selected, all fins of the document "
                    "are exported together with their parts.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return bool(_to_export())

    def Activated(self):  # noqa: N802 - FreeCAD API
        export = _shapes_to_export()
        if export is None:
            return
        path = _save_path(translate("FinSnap", "Export STEP"), FILTER_STEP, EXTENSIONS_STEP)
        if path:
            _write(export_step.write, path, export)


def _shapes_to_export():
    """What the selection exports, or None after saying why there is nothing."""
    try:
        return _export_list(_to_export())
    except ValueError as error:
        _message(str(error))
        return None


def _save_path(title, file_filter, extensions):
    """The file to write, ending in one of `extensions`; empty if the dialog was cancelled."""
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        Gui.getMainWindow(), title, "", translate("FinSnap", file_filter))
    if path and not path.lower().endswith(extensions):
        path += extensions[0]
    return path


def _write(writer, path, export, *settings):
    try:
        writer(path, export.shapes, *settings)
    except (ValueError, OSError, Part.OCCError) as error:
        _message(str(error))
        return
    App.Console.PrintMessage("FinSnap: %d objects written to %s\n" % (len(export.shapes), path))
    if export.left_out:
        _message(translate("FinSnap", "Left out, as their part lies flat: %s. Stand it on its edge again to "
                                      "export these fins.") % ", ".join(export.left_out))


COMMANDS = (("FinSnap_QuickFins", QuickFins()),
            ("FinSnap_Tilt", TiltOntoEdge()),
            ("FinSnap_LayFlat", LayFlat()),
            ("FinSnap_AddFins", AddFins()),
            ("FinSnap_AddCounterFin", AddCounterFin()),
            ("FinSnap_MeshToSolid", MeshToSolid()),
            ("FinSnap_Export3MF", Export3MF()),
            ("FinSnap_ExportSTEP", ExportSTEP()))


def register():
    for name, command in COMMANDS:
        Gui.addCommand(name, command)
    return [name for name, _ in COMMANDS]
