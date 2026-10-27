# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Handles in the 3D view to move a fin along its face and to set its height.

While the task panel is open the fins are shown see-through, green while they
can be built and red while not, the tines that find no face are marked red,
and two double arrows stand just outside the middle of the upright outer
edge of one fin, the one picked or the first: one along the face, one up. An
end of an arrow is left out where the fin cannot go. While an arrow is
dragged the task panel builds the fins along, and shows the fin red where it
cannot stand.

The two arrows are made once and kept until the panel closes; they are only
moved from fin to fin. Coin still holds an arrow let go for a moment, and an
arrow taken out of the scene then is a crash. Their callbacks go through the
3D view of FreeCAD, which takes the Python interpreter lock before calling;
pivy's own dragger callbacks do not, and crash FreeCAD on the first drag.

Shapes are drawn here as well, so the overhang marks and the previews share
one way of putting faces into the scene.
"""

import functools
import math

from pivy import coin
from PySide import QtCore

import FreeCAD as App
import FreeCADGui as Gui

from .i18n import translate

# The colours and the opacity FreeCAD shows its own feature previews in:
# green for what a feature adds, red for an error, faint enough to see through.
VALID_COLOR = (0.0, 1.0, 0.6)
INVALID_COLOR = (1.0, 0.0, 0.0)
PREVIEW_TRANSPARENCY = 1.0 - 0.2
# Transparency of a view object is set in percent.
PERCENT = 100
# Largest deviation of drawn faces from the true faces (mm).
MESH_DEVIATION = 0.1
# Drawn faces lie this far in front of the faces they cover, so they show
# through instead of flickering with them.
FACE_OFFSET = -1.0

ALONG, UP = "along", "up"
UP_DIRECTION = App.Vector(0, 0, 1)
# The two ends of an arrow: towards smaller and towards larger values.
BACK, FORTH = -1, 1
# Each half of an arrow is this share of the height of its fin long.
ARROW_SHARE = 0.25
# The shape of a half arrow one unit long, as FreeCAD draws its own arrows: a
# thin shaft and a cone at the tip.
SHAFT_RADIUS = 0.025
TIP_LENGTH = 0.25
TIP_RADIUS = 0.08
# The arrows stand this far off the outer edge of their fin, in units of a
# half arrow: clear of the fin, which would cover them otherwise.
CLEARANCE = 2 * TIP_RADIUS
# The arrows take the colours of the axes they follow, as set in FreeCAD's
# preferences, and the colour of FreeCAD's own arrows while held.
VIEW_PARAMETERS = "User parameter:BaseApp/Preferences/View"
AXIS_COLORS = {"x": ("AxisXColor", 0xCC3333FF), "y": ("AxisYColor", 0x33CC33FF),
               "z": ("AxisZColor", 0x3333CCFF)}
HELD_COLOR = (1.0, 1.0, 0.0)
BYTE = 255
# The type of FreeCAD's 3D views among the views of a document.
VIEW_3D = "Gui::View3DInventor"
# A Coin translate dragger moves along its own x axis.
DRAGGER_AXIS = coin.SbVec3f(1, 0, 0)


def shaded(shapes, color, transparency):
    """A Coin node drawing the faces of `shapes` in one colour."""
    points, index = [], []
    for shape in shapes:
        for face in shape.Faces:
            vertices, triangles = face.tessellate(MESH_DEVIATION)
            first = len(points)
            points += [(v.x, v.y, v.z) for v in vertices]
            for triangle in triangles:
                index += [first + corner for corner in triangle] + [-1]
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.transparency.setValue(transparency)
    offset = coin.SoPolygonOffset()
    offset.factor.setValue(FACE_OFFSET)
    offset.units.setValue(FACE_OFFSET)
    coordinates = coin.SoCoordinate3()
    coordinates.point.setValues(0, len(points), points)
    faces = coin.SoIndexedFaceSet()
    faces.coordIndex.setValues(0, len(index), index)
    group = coin.SoSeparator()
    for node in (material, offset, coordinates, faces):
        group.addChild(node)
    return group


def axis_color(axis):
    """The colour of `axis` ("x", "y" or "z") in FreeCAD's preferences, as RGB from 0 to 1."""
    name, standard = AXIS_COLORS[axis]
    packed = App.ParamGet(VIEW_PARAMETERS).GetUnsigned(name, standard)
    # Packed as 0xRRGGBBAA.
    return tuple((packed >> shift & BYTE) / BYTE for shift in (24, 16, 8))


def double_arrow(color):
    """An arrow from -1 to +1 along x, with a tip at each end, and the switch
    of each half by its end, BACK or FORTH, to hide one."""
    group = coin.SoSeparator()
    base = coin.SoBaseColor()
    base.rgb.setValue(*color)
    group.addChild(base)
    halves = {}
    for end in (BACK, FORTH):
        switch = coin.SoSwitch()
        switch.whichChild.setValue(coin.SO_SWITCH_ALL)
        half = coin.SoSeparator()
        if end == BACK:
            turn = coin.SoRotationXYZ()
            turn.axis.setValue(coin.SoRotationXYZ.Z)
            turn.angle.setValue(math.pi)
            half.addChild(turn)
        half.addChild(half_arrow())
        switch.addChild(half)
        group.addChild(switch)
        halves[end] = switch
    return group, halves


def half_arrow():
    """Half an arrow, one unit long from the origin along +x."""
    group = coin.SoSeparator()
    # Coin's cylinder and cone stand along y; turned, they point along x.
    turn = coin.SoRotationXYZ()
    turn.axis.setValue(coin.SoRotationXYZ.Z)
    turn.angle.setValue(-math.pi / 2)
    shaft_length = 1.0 - TIP_LENGTH
    to_shaft = coin.SoTranslation()
    to_shaft.translation.setValue(0, shaft_length / 2, 0)
    shaft = coin.SoCylinder()
    shaft.radius.setValue(SHAFT_RADIUS)
    shaft.height.setValue(shaft_length)
    to_tip = coin.SoTranslation()
    to_tip.translation.setValue(0, (shaft_length + TIP_LENGTH) / 2, 0)
    tip = coin.SoCone()
    tip.bottomRadius.setValue(TIP_RADIUS)
    tip.height.setValue(TIP_LENGTH)
    for node in (turn, to_shaft, shaft, to_tip, tip):
        group.addChild(node)
    return group


class NoView(RuntimeError):
    """The document has no 3D view to show the arrows in."""


class Handles:
    """Two arrows on one fin of the object shown by `vobj`, one along the face
    and one up, with the object see-through until remove().

    on_start(kind) is called when an arrow is grabbed, on_move(kind, mm) while
    it is dragged, on_done(kind, mm) when it is let go; kind is ALONG or UP, mm
    how far from where it was grabbed.
    """

    def __init__(self, vobj, on_start, on_move, on_done):
        # The 3D view of the document; the active view may be a drawing page
        # or a spreadsheet. Found first, so nothing is changed without one.
        gui_doc = Gui.getDocument(vobj.Object.Document)
        view = gui_doc.ActiveView
        if not hasattr(view, "getViewer"):
            views = gui_doc.mdiViewsOfType(VIEW_3D)
            if not views:
                raise NoView(translate("FinSnap", "No 3D view of %s is open to edit the fins in.")
                             % vobj.Object.Document.Label)
            view = views[0]
        self.vobj = vobj
        self.on_start, self.on_move, self.on_done = on_start, on_move, on_done
        # How the object looked before, put back by remove().
        self.look = (vobj.ShapeAppearance, vobj.Transparency)
        vobj.Transparency = round(PREVIEW_TRANSPARENCY * PERCENT)
        self.tint(True)

        self.view = view
        self.callbacks = []
        self.root = coin.SoSeparator()
        # Switches, switched off while there is nothing to show.
        self.arrows = coin.SoSwitch()
        self.preview = coin.SoSwitch()
        self.dropped = coin.SoSwitch()
        for node in (self.arrows, self.preview, self.dropped):
            node.whichChild.setValue(coin.SO_SWITCH_NONE)
            self.root.addChild(node)
        # Each arrow: where it stands and how long it is, and the dragger; the
        # halves of its two looks, at rest and held, and which ends it shows.
        self.places, self.draggers, self.lengths = {}, {}, {}
        self.halves, self.ends = {}, {}
        for kind in (ALONG, UP):
            place = coin.SoTransform()
            dragger = coin.SoTranslate1Dragger()
            for part in ("feedback", "feedbackActive"):
                dragger.setPart(part, coin.SoSeparator())
            for name, method in (("addStartCallback", self._held), ("addMotionCallback", self._moved),
                                 ("addFinishCallback", self._let_go)):
                callback = view.addDraggerCallback(dragger, name, functools.partial(method, kind))
                self.callbacks.append((dragger, name, callback))
            group = coin.SoSeparator()
            group.addChild(place)
            group.addChild(dragger)
            self.arrows.addChild(group)
            self.places[kind], self.draggers[kind] = place, dragger
            self.halves[kind], self.ends[kind] = {}, (BACK, FORTH)
            self._look(kind, "translatorActive", HELD_COLOR)
        self._look(UP, "translator", axis_color("z"))
        self.along_axis = None
        # True from grabbing an arrow until letting it go.
        self.held = False
        # In the editing root of the 3D view, where FreeCAD puts the handles of
        # its own features: outside the nodes of the object, which take mouse
        # clicks for selecting. It shows only while the object is in edit mode.
        self.viewer = view.getViewer()
        # FreeCAD opens the panel first and enters edit mode after, so the
        # editing root is there only once that is through.
        self.attached = False
        QtCore.QTimer.singleShot(0, self.attach)

    def attach(self):
        if self.root is None:
            return
        # The fins are built in global coordinates: no transform of their own.
        self.viewer.setupEditingRoot(self.root, App.Matrix())
        self.attached = True

    def tint(self, valid):
        """Colour the object green while its fins can be built, red while not."""
        self.vobj.ShapeColor = VALID_COLOR if valid else INVALID_COLOR

    def _look(self, kind, part, color):
        """Give the arrow of `kind` a look in `color` as its `part`, at rest
        ("translator") or held ("translatorActive"), showing the ends it shows."""
        node, halves = double_arrow(color)
        self.draggers[kind].setPart(part, node)
        self.halves[kind][part] = halves
        self.show_ends(kind, self.ends[kind])

    def show_ends(self, kind, ends):
        """Show the arrow of `kind` with the ends in `ends`, BACK and FORTH:
        an end where the fin cannot go is left out."""
        self.ends[kind] = tuple(ends)
        for halves in self.halves[kind].values():
            for end, switch in halves.items():
                switch.whichChild.setValue(coin.SO_SWITCH_ALL if end in ends else coin.SO_SWITCH_NONE)

    def show(self, edge, height, along, out):
        """Put the arrows off `edge`, the middle of the upright outer edge of a
        fin, by a share of their length in the direction `out`, away from the
        part, each half as long as a share of the fin's `height`; `along` is the
        direction along the face."""
        self._clear(self.preview)
        length = height * ARROW_SHARE
        # The arrow along the face takes the colour of the axis it is nearest to.
        axis = "x" if abs(along.x) >= abs(along.y) else "y"
        if axis != self.along_axis:
            self._look(ALONG, "translator", axis_color(axis))
            self.along_axis = axis
        middle = edge + out * (length * CLEARANCE)
        for kind, direction in ((ALONG, along), (UP, UP_DIRECTION)):
            place = self.places[kind]
            place.translation.setValue(middle.x, middle.y, middle.z)
            place.rotation.setValue(coin.SbRotation(DRAGGER_AXIS, coin.SbVec3f(direction.x, direction.y,
                                                                               direction.z)))
            place.scaleFactor.setValue(length, length, length)
            self.draggers[kind].translation.setValue(0, 0, 0)
            self.lengths[kind] = length
        self.arrows.whichChild.setValue(coin.SO_SWITCH_ALL)

    # The callbacks get the dragger as a plain SoDragger, without its fields;
    # the arrow of `kind` is read instead.
    def _mm(self, kind):
        return self.draggers[kind].translation.getValue()[0] * self.lengths[kind]

    def _held(self, kind, _dragger):
        self.held = True
        self.on_start(kind)

    def _moved(self, kind, _dragger):
        self.on_move(kind, self._mm(kind))

    def _let_go(self, kind, _dragger):
        self.held = False
        self.on_done(kind, self._mm(kind))

    @staticmethod
    def _clear(switch):
        switch.whichChild.setValue(coin.SO_SWITCH_NONE)
        switch.removeAllChildren()

    @staticmethod
    def _fill(switch, *nodes):
        switch.removeAllChildren()
        for node in nodes:
            switch.addChild(node)
        switch.whichChild.setValue(coin.SO_SWITCH_ALL if nodes else coin.SO_SWITCH_NONE)

    def show_preview(self, shapes, valid):
        """Show `shapes` see-through, green if `valid`, else red."""
        self._fill(self.preview, shaded(shapes, VALID_COLOR if valid else INVALID_COLOR, PREVIEW_TRANSPARENCY))

    def show_dropped(self, tines):
        """Mark the tines in `tines`, which find no face, red until shown again."""
        self._fill(self.dropped, *([shaded(tines, INVALID_COLOR, PREVIEW_TRANSPARENCY)] if tines else []))

    def clear_preview(self):
        self._clear(self.preview)

    def hide(self):
        self.arrows.whichChild.setValue(coin.SO_SWITCH_NONE)
        self._clear(self.preview)

    def remove(self):
        if self.root is None:
            return
        self.hide()
        for dragger, name, callback in self.callbacks:
            self.view.removeDraggerCallback(dragger, name, callback)
        self.callbacks = []
        self._clear(self.dropped)
        if self.attached:
            self.viewer.resetEditingRoot()
        # Not attached any more, also when the panel closes before it was.
        self.root = None
        self.vobj.ShapeAppearance, self.vobj.Transparency = self.look
