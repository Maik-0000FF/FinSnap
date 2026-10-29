# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Workbench commands and the view provider of the FinSnap object."""

import dataclasses
import functools
from collections import namedtuple

import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from PySide import QtCore, QtWidgets

from . import defaults as d
from . import export_3mf
from . import export_step
from . import feature
from . import geometry
from . import handles
from . import mesh_input
from . import orient
from . import presets
from .i18n import QT_TRANSLATE_NOOP, translate
from .paths import (ICON_ADD, ICON_COUNTER, ICON_EXPORT, ICON_EXPORT_STEP, ICON_LAY_FLAT, ICON_MESH,
                    ICON_QUICK, ICON_TILT)
from .presets import PREFERENCES
from .shapes import FACE_PREFIX, global_shape, outermost
from .taskpanel import DEGREE_SUFFIX, LENGTH_SUFFIX, FinSnapTaskPanel, discard_created
from .version import NAME

EDGE_PREFIX = "Edge"
# Containers that move what they hold: App::Part, PartDesign::Body.
GROUP_EXTENSION = "App::GeoFeatureGroupExtension"
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
# Said when new fins cannot be edited because another task panel is open.
NOTE_BUSY = QT_TRANSLATE_NOOP("FinSnap", "Another task panel is open. Close it first, then make the fins again.")
EXTENSIONS_STEP = (".step", ".stp")
PREF_LINEAR = "MeshLinearDeflection"
PREF_ANGULAR = "MeshAngularDeflection"
MESH_LINEAR_RANGE = (0.001, 1.0)
MESH_ANGULAR_RANGE = (0.1, 30.0)
MESH_LINEAR_DECIMALS = 3
MESH_ANGULAR_DECIMALS = 1
SOLID_SUFFIX = "_solid"
FINS_SUFFIX = "_fins"
# Marks on faces that overhang without fins: red, half see-through, drawn
# slightly in front of the part's own faces, which lie in the same place.
OVERHANG_COLOR = (0.9, 0.1, 0.1)
OVERHANG_TRANSPARENCY = 0.4
# Marks on the islands, where the part would start printing in the air: a
# filled circle the same size on the screen at any zoom, drawn over the part,
# in a colour of its own beside the red of the overhangs.
ISLAND_COLOR = (1.0, 0.0, 1.0)
ISLAND_MARKER = "CIRCLE_FILLED_9_9"
STATUS_TIMEOUT_MS = 10000
# What an export writes, and the fins it leaves out because their part lies flat.
Export = namedtuple("Export", "shapes left_out")


def _shown(obj):
    """Whether `obj` is shown: it and every container it lies in, such as a Body."""
    while obj is not None:
        if not obj.Visibility:
            return False
        obj = obj.getParentGeoFeatureGroup()
    return True


def _holds(obj, part):
    """Whether hiding `obj` hides `part`: it is the part, or a container it lies in."""
    while part is not None:
        if part is obj:
            return True
        part = part.getParentGeoFeatureGroup()
    return False


def _fins_under(obj):
    """The FinSnap objects whose part `obj` is or may hold, found through what
    links to it instead of through the whole document: fins link their part
    (Base) and its outermost container (Container); a container in between
    holds the part, so its contents are asked as well.

    INPUTS this has to withstand:
      the part of fins                      ->  those fins, through Base
      the outermost container of the part   ->  those fins, through Container
      a container between the two           ->  those fins, through the part it holds
      an object no fins depend on           ->  none, after its own few links
    """
    held = [obj] + (obj.OutListRecursive if obj.hasExtension(GROUP_EXTENSION) else [])
    found = {}
    for one in held:
        for user in one.InList:
            if feature.is_fins(user):
                found[user.Name] = user
    return list(found.values())


class PartVisibility:
    """Document observer: when a part or a container of it is shown or hidden,
    the overhang marks of its fins follow."""

    def slotChangedObject(self, obj, prop):  # noqa: N802 - FreeCAD API
        if prop != "Visibility" or obj.Document is None:
            return
        for fins in _fins_under(obj):
            if (fins.Base and _holds(obj, fins.Base[0])
                    and isinstance(getattr(fins.ViewObject, "Proxy", None), ViewProviderFinSnap)):
                fins.ViewObject.Proxy.show_marks()


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
        if prop in (feature.OVERHANGS, feature.ISLANDS):
            self.mark(obj)

    def onChanged(self, vobj, prop):  # noqa: N802 - FreeCAD API
        if prop == "Visibility":
            self.show_marks()

    def show_marks(self):
        """Show the overhang marks while the fins and their part are shown;
        the marks lie on the part, and alone they would float in the air."""
        if not hasattr(self, "marks"):
            return
        obj = self.Object
        visible = obj.ViewObject.Visibility and (not obj.Base or _shown(obj.Base[0]))
        self.marks.whichChild.setValue(coin.SO_SWITCH_ALL if visible else coin.SO_SWITCH_NONE)

    def mark(self, obj):
        """Cover the faces that overhang without fins with red marks, and mark
        the islands, where the part would start printing in the air."""
        if not hasattr(self, "marks"):
            return
        self.marks.removeAllChildren()
        points = getattr(obj, feature.ISLANDS, [])
        if points:
            self.marks.addChild(handles.spots(points, ISLAND_COLOR, ISLAND_MARKER))
        names = getattr(obj, feature.OVERHANGS, [])
        if names and obj.Base:
            try:
                shape = global_shape(obj.Base[0])
            except ValueError:
                shape = None
            if shape is not None:
                faces = [shape.getElement(name) for name in names]
                self.marks.addChild(handles.shaded(faces, OVERHANG_COLOR, OVERHANG_TRANSPARENCY))
        self.show_marks()

    def setEdit(self, vobj, mode=0):  # noqa: N802 - FreeCAD API
        # Fins just made by a command are deleted again by Cancel.
        # Another task dialog is open: FreeCAD keeps that one.
        if Gui.Control.activeDialog():
            return False
        created, self.created = getattr(self, "created", False), False
        on_cancel, self.on_cancel = getattr(self, "on_cancel", None), None
        stands, self.stands = getattr(self, "stands", None), None
        try:
            panel = FinSnapTaskPanel(vobj.Object, created=created, on_cancel=on_cancel, stands=stands)
        except handles.NoView as error:
            _message(str(error))
            return False
        try:
            Gui.Control.showDialog(panel)
        except RuntimeError:
            panel.release_handles()
            return False
        # Kept while editing: the Delete key on a fin goes to the panel then.
        self.panel = panel
        return True

    def unsetEdit(self, vobj, mode=0):  # noqa: N802 - FreeCAD API
        # Edit mode can end without OK or Cancel; the arrows, the see-through
        # look and the listeners of the panel go with it all the same.
        panel, self.panel = getattr(self, "panel", None), None
        if panel is not None:
            panel.release_handles()
        Gui.Control.closeDialog()
        return True

    def claimChildren(self):  # noqa: N802 - FreeCAD API
        return []

    def onDelete(self, vobj, subelements):  # noqa: N802 - FreeCAD API
        """Deleting a face or edge of one fin removes that fin alone; deleting
        the object deletes all of them, and the last fins of a part stood on an
        edge lay it flat again.

        SITUATIONS this has to withstand:
          face or edge of one fin selected      ->  that fin left out, object kept
          the last main fins selected           ->  the object deleted, as from the tree
          fins selected, task panel open        ->  the panel removes them; FreeCAD
                                                    deletes nothing in edit mode
          sub-elements of merged fins           ->  message, nothing deleted
          fins and other sub-elements mixed     ->  nothing deleted
          object selected in the tree           ->  deleted; the last fins lay the part flat;
                                                    an open task panel on it closes first
        """
        obj = vobj.Object
        if subelements and obj.Connection == d.CONNECTION_MERGED:
            # Merged into the part, the fins are no solids of their own to pick.
            _message(translate("FinSnap", feature.NOTE_MERGED_SINGLE))
            return False
        fins = [feature.fin_at(obj, sub) for sub in subelements or ()]
        if fins and not all(fins):
            # Something picked that is no fin: the object as a whole is not meant.
            return False
        panel = getattr(self, "panel", None)
        if fins:
            if panel is not None:
                # The panel may delete this very object; not while its own
                # onDelete still runs.
                QtCore.QTimer.singleShot(0, functools.partial(panel.remove_fins, fins))
                return False
            obj.Document.openTransaction(translate("FinSnap", "Remove fin"))
            if not feature.remove_fins(obj, fins):
                obj.Document.commitTransaction()
                obj.Document.recompute()
                return False
            # The last main fins: nothing was changed, the object goes as a whole.
            obj.Document.abortTransaction()
        self.close_panel()
        feature.prepare_delete(obj)
        return True

    def close_panel(self):
        """Close a task panel open on these fins, as they are, before they go or change."""
        panel = getattr(self, "panel", None)
        if panel is not None:
            panel.close()

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
      one rim of a cylinder or tube         ->  stands on it, leaning to the front by the
                                                asked angle
      one rim and its curved side           ->  the same, the side leaning by the angle
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
                    "stand the part on what joins them, both equally steep. The rim of a cylinder or tube stands "
                    "it on that rim, leaning to the front.")}

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
            # A side or rim split in halves is taken whole.
            shape, elements, _ = feature.whole_elements(obj, [name for _, name in edges + faces])
            chosen = elements[len(edges):]
            face = chosen[0] if chosen else None
            edge = None
            if len(chosen) == 2:
                change = orient.rest_between(shape, *chosen)
            elif edges:
                edge = elements[0]
                if face is None and not orient.on_bed(shape, edge) and not orient.is_rim(edge):
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
        except (orient.OrientError, geometry.FinError) as error:
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
    """Turn the part of `obj` by `change`, keeping where it lay for Lay flat again.
    Fins under a round side forget how far the part was turned about it."""
    owner = outermost(obj)
    orient.remember_flat(owner)
    owner.Placement = change.multiply(owner.Placement)
    for fins in feature.fins_of(owner, owner.Document):
        feature.forget_turn(fins)


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
        # A task panel open on the fins closes first, deleted or kept, and
        # before the transaction, so its own steps stay apart from this one.
        for owner in owners:
            for fins in feature.fins_of(owner, doc):
                proxy = getattr(fins.ViewObject, "Proxy", None)
                if isinstance(proxy, ViewProviderFinSnap):
                    proxy.close_panel()
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
                    "on. A chamfer or fillet alone, or the two faces beside a fillet, carry the part as "
                    "well. The rim or the curved side of a cylinder or tube stands it on its rim, with one fin "
                    "under its lowest line. A counter fin, where wanted, is added in the panel. Where the "
                    "part can stand on another edge, or the fins can go under another face, a table at the "
                    "top of the panel lists them to choose from; ways where the part would start printing "
                    "in the air are left out while one without is found.")}

    def IsActive(self):  # noqa: N802 - FreeCAD API
        return App.ActiveDocument is not None

    def Activated(self):  # noqa: N802 - FreeCAD API
        picked, edges, faces = _picked()
        if not picked or len({id(o) for o, _ in picked}) != 1:
            _message(translate("FinSnap", "Select an edge or a face of one part."))
            return
        obj = picked[0][0]
        p = quick_params()
        # Every way is checked for islands, which takes a moment on a large part.
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            plans, refused = quick_plans(obj, [n for _, n in edges], [n for _, n in faces]), None
        except (orient.OrientError, geometry.FinError) as error:
            plans, refused = None, error
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if refused is not None:
            _message(str(refused))
            return
        plan, fin_face = plans[0].plan, plans[0].face
        doc = App.ActiveDocument
        doc.openTransaction(translate("FinSnap", "Quick fins"))
        owner = outermost(obj)
        before = orient.snapshot(owner)
        # Standing the part rebuilds its other fins laid flat; Cancel gives them back.
        laid_flat = feature.laid_flat_marks(owner, doc)
        # Standing it anew forgets how far it was turned about a round side; Cancel notes it again.
        turns = feature.round_turns(owner, doc)
        _stand(obj, plan.change)
        # The main fin only; a counter fin is added in the panel or with Add counter fin.
        fins = feature.create(obj, fin_face)
        fins.FinPlacement = p.placement
        ViewProviderFinSnap(fins.ViewObject)
        doc.commitTransaction()
        doc.recompute()
        _show_on_bed(orient.side_direction(plan.change, plan.edge, plan.beside))
        # Cancel deletes the fins and stands the part as it stood before.
        _edit_new(fins, functools.partial(_put_back_quick, owner, before, laid_flat, turns),
                  QuickStands(obj, owner, before, plans))


def quick_params():
    """The parameters Quick fins makes fins with: the standard, with one fin
    in the middle of the face; the panel can spread more along it."""
    return dataclasses.replace(presets.standard(), placement=d.PLACEMENT_CENTER)


def quick_plan(obj, edge_names, face_names):
    """How Quick fins stands `obj` for its edges and faces named ("Edge3",
    "Face12"), faces in the order selected: the first way of quick_plans(), on
    its global shape, a side or rim split in halves taken whole (feature.whole_elements()).
    Returns the plan and the name on `obj` of the face it puts the fins under.
    OrientError or FinError where it cannot."""
    way = quick_plans(obj, edge_names, face_names)[0]
    return way.plan, way.face


def quick_plans(obj, edge_names, face_names):
    """Every way Quick fins can stand `obj` for its edges and faces named that
    prints without islands, as QuickWays, in the order geometry.quick_plans()
    finds them, for the task panel to step through;
    where every way has islands, all of them, the fewest first, see
    geometry.printable_plans(). OrientError or FinError where there is none.

    A fault in the kernel while the others are looked for ends the search: the
    plans found by then are kept, as the first one is a way to stand the part."""
    shape, elements, name_of = feature.whole_elements(obj, list(edge_names) + list(face_names))
    edges, faces = elements[:len(edge_names)], elements[len(edge_names):]
    numbers = [next(i for i, candidate in enumerate(shape.Faces) if candidate.isSame(face)) for face in faces]
    found = geometry.quick_plans(shape, [(edge, None) for edge in edges], list(zip(faces, numbers)),
                                 quick_params(), d.TILT_ANGLE)
    plans = [next(found)]
    try:
        plans.extend(found)
    except Part.OCCError:
        pass
    # The area from the shape the plans number their faces in, a side split
    # in halves joined: on `obj` the number is another face.
    return [QuickWay(plan, name_of(plan.number), points, shape.Faces[plan.number].Area, _edge_name(obj, plan.edge))
            for plan, points in geometry.printable_plans(shape, plans, quick_params())]


def _edge_name(obj, edge):
    """The name of `edge` on `obj` as FreeCAD shows it, "Edge7": the edge of
    its global shape that is the same, or failing that, that has the same
    ends and length, as an edge of a shape with halves joined may be another
    one; None for no edge, or none found."""
    if edge is None:
        return None
    ends = sorted(tuple(vertex.Point) for vertex in edge.Vertexes)
    for number, candidate in enumerate(global_shape(obj).Edges, 1):
        if candidate.isSame(edge) or (
                abs(candidate.Length - edge.Length) < d.TOLERANCE
                and len(candidate.Vertexes) == len(edge.Vertexes)
                and all((App.Vector(*a) - App.Vector(*b)).Length < d.TOLERANCE
                        for a, b in zip(sorted(tuple(v.Point) for v in candidate.Vertexes), ends))):
            return "%s%d" % (EDGE_PREFIX, number)
    return None


# A way Quick fins found to stand a part: the plan, the name on the part of the
# face the fins go under, the islands, the area of that face (mm2), and the
# name on the part of the edge it stands on, None without one.
QuickWay = namedtuple("QuickWay", "plan face islands area edge")


class QuickStands:
    """The ways Quick fins found to stand a part, for its task panel to list
    and choose from: `plans` as quick_plans() returns them, the first the one
    the part stands in now. They differ by the edge the part stands on, or,
    where it stands one way only, by the face the fins go under.

    CHOICES this has to withstand (stand()):
      another edge of the face              ->  the part stands on it from where Quick fins
                                                found it, the fins planned anew under the face
      another face for the fins             ->  the part stands as it did, the fins under it
      fins changed by hand, a counter fin   ->  dropped: they belonged to the stand before
      part turned about its round side      ->  stands unturned, the turn dropped with the shifts
    """

    def __init__(self, obj, owner, before, plans):
        self.obj, self.owner, self.before, self.plans = obj, owner, before, plans
        self.current = 0
        # Under one face throughout, on edges, the plans differ by the edge.
        self.by_edge = (len({way.plan.number for way in plans}) == 1
                        and all(way.plan.edge is not None for way in plans))
        # What tells the ways apart: the edge or the face by its name on the
        # part, its length (mm) or area (mm2), and the islands standing so.
        self.rows = [(way.edge or "", way.plan.edge.Length, len(way.islands)) if self.by_edge
                     else (way.face, way.area, len(way.islands)) for way in plans]

    def __len__(self):
        return len(self.plans)

    def stand(self, fins, index):
        """Stand the part the way numbered `index` (from 0), the fins `fins`
        under its face as planned, and show it on the bed."""
        plan, face = self.plans[index].plan, self.plans[index].face
        feature.remove_counter(fins)
        feature.reset_fins(fins)
        orient.put_back(self.owner, self.before)
        _stand(self.obj, plan.change)
        fins.Base = (self.obj, [face])
        self.current = index
        _show_on_bed(orient.side_direction(plan.change, plan.edge, plan.beside))


def _put_back_quick(owner, before, laid_flat, turns):
    """Undo what Quick fins did besides making the fins: the part stands as
    before, its other fins laid flat keep their marks and shapes, and its fins
    under a round side how far it was turned about it."""
    orient.put_back(owner, before)
    feature.put_back_laid_flat(owner.Document, laid_flat)
    feature.put_back_turns(owner.Document, turns)


def _edit_new(fins, on_cancel=None, stands=None):
    """Open the task panel on fins just made, in edit mode as a double click
    does: the handles of the panel are shown only there. Cancel deletes the
    fins, then calls `on_cancel` to undo what the command did besides.
    `stands`, a QuickStands, lets the panel stand the part another way."""
    proxy = fins.ViewObject.Proxy
    proxy.created, proxy.on_cancel, proxy.stands = True, on_cancel, stands
    # Another task panel open keeps the fins' panel from opening; said below,
    # as FreeCAD says nothing then.
    busy = Gui.Control.activeDialog()
    # What was selected to make the fins is used up; left selected, the panel
    # would take a face of it for a counter fin, such as one now on the bed.
    Gui.Selection.clearSelection()
    try:
        opened = Gui.ActiveDocument.setEdit(fins)
    finally:
        # Only for this opening: a later Cancel must not delete fins long kept.
        proxy.created, proxy.on_cancel, proxy.stands = False, None, None
    # Without a panel there is no Cancel: what the command did is undone at
    # once, as Cancel would. Without a 3D view, setEdit has said why.
    if not opened:
        if busy:
            _message(translate("FinSnap", NOTE_BUSY))
        discard_created(fins, on_cancel)


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
        try:
            obj = feature.create(base, face_name, counter)
        except (ValueError, Part.OCCError) as error:
            doc.abortTransaction()
            _message(translate("FinSnap", feature.NOTE_NO_COUNTER_ON_FACE) % error)
            return
        ViewProviderFinSnap(obj.ViewObject)
        doc.commitTransaction()
        _edit_new(obj)


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
        try:
            if faces:
                found = feature.add_counter(fins[0], faces[0][0], faces[0][1])
            else:
                found = feature.add_counter(fins[0])
        except geometry.FinError as error:
            doc.abortTransaction()
            _message(translate("FinSnap", feature.NOTE_NO_COUNTER_ON_FACE) % error)
            return
        doc.commitTransaction()
        if found is None:
            _message(translate("FinSnap", feature.NOTE_NO_OPPOSITE))
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


# Registered once, when this module is first imported: with the workbench, or
# with a document holding fins.
App.addDocumentObserver(PartVisibility())


def register():
    for name, command in COMMANDS:
        Gui.addCommand(name, command)
    return [name for name, _ in COMMANDS]
