# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Handles in the 3D view to move a fin along its face and to set its height.

While the task panel is open the fins are shown see-through, green while they
can be built and red while not, the tines that find no face are marked red,
and two double arrows stand just outside the middle of the upright outer
edge of one fin, the one picked or the first: one along the face, one up.
Under the round side of a cylinder or tube, where moving the fin turns the
part about its axis, the arrow along the face is an arc round that axis
through the same place instead. An end of an arrow is left out where the fin
cannot go. While an arrow is
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
# A fin dragged to a height between two tines: it stands, but goes to the
# nearest tine when let go.
BETWEEN_COLOR = (1.0, 0.85, 0.0)
PREVIEW_TRANSPARENCY = 1.0 - 0.2
# What a material of a face carries besides its colour, kept when one face is tinted.
MATERIAL_FIELDS = ("AmbientColor", "SpecularColor", "EmissiveColor", "Shininess", "Transparency")
# Transparency of a view object is set in percent.
PERCENT = 100
# Largest deviation of drawn faces from the true faces (mm).
MESH_DEVIATION = 0.1
# Drawn faces lie this far in front of the faces they cover, so they show
# through instead of flickering with them.
FACE_OFFSET = -1.0

ALONG, UP = "along", "up"
KINDS = (ALONG, UP)
# The arc that moves the fin along a round side, by turning the part, in
# place of the straight arrow along the face.
TURNING = "turning"
UP_DIRECTION = App.Vector(0, 0, 1)
# The two ends of an arrow: towards smaller and towards larger values.
BACK, FORTH = -1, 1
# The arrows keep their size on the screen, whatever the size of the fin and
# the zoom, as FreeCAD's own draggers do, through FreeCAD's node for it. Its
# scale factor 1 makes a unit about a fiftieth of the view, less in a wide
# window; a half arrow is a unit long. FreeCAD sizes it at the origin, so in
# a perspective view an arrow far from the origin is a little off that, as
# FreeCAD's own are.
AUTO_ZOOM = "SoAutoZoomTranslation"
ARROW_SCREEN_SIZE = 4.0
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
# Coin's cone points along its y axis.
CONE_AXIS = coin.SbVec3f(0, 1, 0)
# The arc that turns a part about its round side runs round the true circle
# about the axis, but keeps the size of the straight arrows on the screen:
# each half a unit long and as thick, in this many round pieces, and never
# more than this far round the circle (radians). It is drawn anew whenever
# the zoom has changed by more than ZOOM_REDRAW_SHARE, looked for every
# ZOOM_POLL_MS. A unit is reckoned as FreeCAD's node for it does: the scale
# of the view at the origin, sampled over AUTO_ZOOM_PROBE, by AUTO_ZOOM_DIVISOR.
ARC_PIECES = 8
ARC_MAX_HALF_TURN = 0.8 * math.pi
ZOOM_REDRAW_SHARE = 0.01
ZOOM_POLL_MS = 50
AUTO_ZOOM_PROBE = 0.1
AUTO_ZOOM_DIVISOR = 5
# The parts of a Coin disc dragger, which turns about its own z axis, at rest and held.
TURN_PARTS = ("rotator", "rotatorActive")


def spots(points, color, transparency, size):
    """A Coin node marking `points` with see-through balls in one colour, of
    radius `size` in the units of FreeCAD's node that keeps them the same size
    on the screen at any zoom, as the arrows; drawn over everything else, so a
    ball under the part shows from above as well."""
    group = coin.SoAnnotation()
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.transparency.setValue(transparency)
    group.addChild(material)
    for point in points:
        spot = coin.SoSeparator()
        place = coin.SoTranslation()
        place.translation.setValue(point.x, point.y, point.z)
        zoom = coin.SoType.fromName(AUTO_ZOOM).createInstance()
        ball = coin.SoSphere()
        ball.radius.setValue(size)
        for node in (place, zoom, ball):
            spot.addChild(node)
        group.addChild(spot)
    return group


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


def double_arrow(color, offset):
    """An arrow from -1 to +1 along x, with a tip at each end, of a fixed size
    on the screen, moved by `offset` (a SoTranslation, in its units), and the
    switch of each half by its end, BACK or FORTH, to hide one."""
    group = coin.SoSeparator()
    base = coin.SoBaseColor()
    base.rgb.setValue(*color)
    zoom = coin.SoType.fromName(AUTO_ZOOM).createInstance()
    zoom.scaleFactor.setValue(ARROW_SCREEN_SIZE)
    for node in (base, zoom, offset):
        group.addChild(node)
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
    for node in (turn, to_shaft, shaft, to_tip, tip()):
        group.addChild(node)
    return group


def tip(unit=1.0):
    """The cone at the tip of an arrow, along y round the origin, `unit` long a unit of an arrow."""
    cone = coin.SoCone()
    cone.bottomRadius.setValue(TIP_RADIUS * unit)
    cone.height.setValue(TIP_LENGTH * unit)
    return cone


def arc_arrow(color):
    """An arc in `color` with an end at each side, and of each end, BACK or
    FORTH, the switch to hide it and the group fill_half_arc() draws it in."""
    group = coin.SoSeparator()
    base = coin.SoBaseColor()
    base.rgb.setValue(*color)
    group.addChild(base)
    halves, bodies = {}, {}
    for end in (BACK, FORTH):
        switch = coin.SoSwitch()
        switch.whichChild.setValue(coin.SO_SWITCH_ALL)
        body = coin.SoSeparator()
        switch.addChild(body)
        group.addChild(switch)
        halves[end], bodies[end] = switch, body
    return group, halves, bodies


def fill_half_arc(body, radius, unit, sense):
    """Draw into `body` half an arrow from (radius, 0, 0) round the circle of
    `radius` about the z axis (mm): the right way round for `sense` 1, the
    other for -1. It is as long and as thick as half a straight arrow whose
    unit is `unit` mm, but goes no further round than ARC_MAX_HALF_TURN."""
    body.removeAllChildren()
    # Along the arc, in mm, shortened alike where it would go too far round.
    share = min(1.0, ARC_MAX_HALF_TURN * radius / unit)

    def point(length):
        angle = sense * length * share / radius
        return coin.SbVec3f(radius * math.cos(angle), radius * math.sin(angle), 0)

    def placed(node, start, end):
        """`node`, standing along y round the origin, moved to stand from `start` to `end`."""
        piece = coin.SoSeparator()
        place = coin.SoTransform()
        place.translation.setValue((start + end) * 0.5)
        place.rotation.setValue(coin.SbRotation(CONE_AXIS, end - start))
        piece.addChild(place)
        piece.addChild(node)
        return piece

    shaft_length = (1.0 - TIP_LENGTH) * unit
    marks = [point(shaft_length * i / ARC_PIECES) for i in range(ARC_PIECES + 1)]
    for start, end in zip(marks, marks[1:]):
        shaft = coin.SoCylinder()
        shaft.radius.setValue(SHAFT_RADIUS * unit)
        shaft.height.setValue((end - start).length())
        body.addChild(placed(shaft, start, end))
    body.addChild(placed(tip(unit), marks[-1], point(unit)))


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
        self.places, self.draggers = {}, {}
        # Each arrow off the edge of its fin, in the units of the arrow; one
        # node shared by its two looks.
        self.offsets = {kind: coin.SoTranslation() for kind in KINDS}
        self.halves, self.ends = {}, {}
        # Each straight arrow, and the arc that stands in for the one along the
        # face under a round side, switched on while it shows.
        self.shown = {}
        for kind in KINDS:
            self.places[kind], self.draggers[kind] = self._add_dragger(kind, coin.SoTranslate1Dragger(),
                                                                       ("feedback", "feedbackActive"))
            self.halves[kind], self.ends[kind] = {}, (BACK, FORTH)
            self._look(kind, "translatorActive", HELD_COLOR)
        self._look(UP, "translator", axis_color("z"))
        self.along_axis = None
        # The arc: it turns about its own z axis, the axis of the round side,
        # and moves the fin by mm_per_degree for every degree it is turned.
        self.turn_place, self.turner = self._add_dragger(ALONG, coin.SoRotateDiscDragger(),
                                                         ("feedback", "feedbackActive"), turning=True)
        # The colour the arc was last made in; the groups its ends are drawn
        # in, by look and end; where it was last put, as the arguments of
        # _show_arc() but the last; and the unit of an arrow it was drawn for (mm).
        self.arc_made = None
        self.arc_bodies = {}
        self.arc_at = None
        self.arc_unit = 0.0
        self.mm_per_degree = 0.0
        # Draws the arc anew once the zoom has changed.
        self.zoom_timer = QtCore.QTimer()
        self.zoom_timer.setInterval(ZOOM_POLL_MS)
        self.zoom_timer.timeout.connect(self._zoomed)
        # How far the arc is turned in this drag (radians), and its turn as last read.
        self.turned, self.last_turn = 0.0, 0.0
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

    def _add_dragger(self, kind, dragger, hidden_parts, turning=False):
        """Put `dragger` into the scene under a place of its own, switched off,
        with its parts `hidden_parts` left empty and its callbacks going to
        those of the arrow of `kind`; the arc of a round side with `turning`.
        Returns the place and the dragger."""
        for part in hidden_parts:
            dragger.setPart(part, coin.SoSeparator())
        for name, method in (("addStartCallback", self._held), ("addMotionCallback", self._moved),
                             ("addFinishCallback", self._let_go)):
            callback = self.view.addDraggerCallback(dragger, name, functools.partial(method, kind))
            self.callbacks.append((dragger, name, callback))
        place = coin.SoTransform()
        group = coin.SoSeparator()
        group.addChild(place)
        group.addChild(dragger)
        switch = coin.SoSwitch()
        switch.whichChild.setValue(coin.SO_SWITCH_NONE)
        switch.addChild(group)
        self.arrows.addChild(switch)
        self.shown[TURNING if turning else kind] = switch
        return place, dragger

    def attach(self):
        if self.root is None:
            return
        # The fins are built in global coordinates: no transform of their own.
        self.viewer.setupEditingRoot(self.root, App.Matrix())
        self.attached = True

    def _material(self, color):
        """A material like the object's first, but for its colour `color`."""
        look = self.vobj.ShapeAppearance[0]
        material = App.Material()
        for name in MATERIAL_FIELDS:
            setattr(material, name, getattr(look, name))
        material.DiffuseColor = color
        return material

    def tint(self, valid):
        """Colour the object green while its fins can be built, red while not.

        One material for the whole object, also after tint_faces(): FreeCAD
        applies a list of materials only while it has one per face, and the
        number of faces changes with every fin added or removed."""
        self.tint_all(VALID_COLOR if valid else INVALID_COLOR)

    def tint_all(self, color):
        """Colour the whole object in `color`, with one material."""
        self.vobj.ShapeAppearance = [self._material(color)]

    def tint_faces(self, faces, color):
        """Colour the faces with the indices in `faces` in `color` and every
        other face green: one fin that cannot stand, or stands between two
        tines, among fins that stand. Each face gets a material of its own,
        alike but for the colour, so the object stays as see-through as it is."""
        self.vobj.ShapeAppearance = [self._material(color if index in faces else VALID_COLOR)
                                     for index in range(len(self.vobj.Object.Shape.Faces))]

    def _look(self, kind, part, color):
        """Give the arrow of `kind` a look in `color` as its `part`, at rest
        ("translator") or held ("translatorActive"), showing the ends it shows."""
        node, halves = double_arrow(color, self.offsets[kind])
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

    def show(self, edge, along, out, turn=None):
        """Put the arrows at `edge`, the middle of the upright outer edge of a
        fin, a little off it in the direction `out`, away from the part;
        `along` is the direction along the face. With `turn`, a point on the
        axis of a round side, its direction and how far the fin moves along
        the face (mm) as the part turns one degree about it, the arrow along
        the face is an arc round that axis through `edge`."""
        self._clear(self.preview)
        # The arrow along the face takes the colour of the axis it is nearest to.
        axis = "x" if abs(along.x) >= abs(along.y) else "y"
        if axis != self.along_axis:
            self._look(ALONG, "translator", axis_color(axis))
            self.along_axis = axis
        self.shown[ALONG].whichChild.setValue(coin.SO_SWITCH_NONE if turn else coin.SO_SWITCH_ALL)
        self.shown[UP].whichChild.setValue(coin.SO_SWITCH_ALL)
        self.shown[TURNING].whichChild.setValue(coin.SO_SWITCH_ALL if turn else coin.SO_SWITCH_NONE)
        if turn:
            self._show_arc(edge, out, *turn)
        else:
            self.zoom_timer.stop()
        for kind, direction in ((ALONG, along), (UP, UP_DIRECTION)):
            place = self.places[kind]
            place.translation.setValue(edge.x, edge.y, edge.z)
            turn = coin.SbRotation(DRAGGER_AXIS, coin.SbVec3f(direction.x, direction.y, direction.z))
            place.rotation.setValue(turn)
            # Off the edge in the arrow's own turned units, so the distance
            # keeps to the size of the arrow on the screen.
            off = turn.inverse().multVec(coin.SbVec3f(out.x, out.y, out.z))
            self.offsets[kind].translation.setValue(off * CLEARANCE)
            self.draggers[kind].translation.setValue(0, 0, 0)
        self.arrows.whichChild.setValue(coin.SO_SWITCH_ALL)

    def _show_arc(self, edge, out, center, axis, mm_per_degree):
        """Put the arc where the straight arrows start, at `edge` and off it
        towards `out`, bent round the axis through `center` along `axis`, about
        which it turns, in the colour of the arrow along the face; see show()."""
        if self.along_axis != self.arc_made:
            self.arc_made = self.along_axis
            for part, color in zip(TURN_PARTS, (axis_color(self.along_axis), HELD_COLOR)):
                node, halves, self.arc_bodies[part] = arc_arrow(color)
                self.turner.setPart(part, node)
                self.halves[ALONG][part] = halves
            self.show_ends(ALONG, self.ends[ALONG])
        self.mm_per_degree = mm_per_degree
        self.arc_at = (edge, out, center, axis)
        self.turner.rotation.setValue(coin.SbRotation())
        self._draw_arc()
        self.zoom_timer.start()

    def unit_mm(self):
        """How long a unit of an arrow is now (mm), as FreeCAD's node for it
        reckons it from the view, scaled by ARROW_SCREEN_SIZE."""
        aspect = self.viewer.getSoRenderManager().getViewportRegion().getViewportAspectRatio()
        volume = self.view.getCameraNode().getViewVolume(aspect)
        scale = volume.getWorldToScreenScale(coin.SbVec3f(0, 0, 0), AUTO_ZOOM_PROBE)
        return ARROW_SCREEN_SIZE * scale / (AUTO_ZOOM_DIVISOR * aspect)

    def _draw_arc(self):
        """Draw the arc where _show_arc() put it, for the zoom of now: round
        the axis of the side, through where the straight arrows start, off
        the edge by CLEARANCE units as they are."""
        edge, out, center, axis = self.arc_at
        self.arc_unit = self.unit_mm()
        start = edge + out * (CLEARANCE * self.arc_unit)
        foot = center + axis * (start - center).dot(axis)
        radial = start - foot
        # The arc turns about the axis of the side, its own z axis; its own x
        # axis points out to where it starts.
        frame = App.Rotation(radial, axis.cross(radial), axis, "ZXY")
        self.turn_place.translation.setValue(foot.x, foot.y, foot.z)
        self.turn_place.rotation.setValue(*frame.Q)
        for bodies in self.arc_bodies.values():
            for end, body in bodies.items():
                fill_half_arc(body, radial.Length, self.arc_unit, end * math.copysign(1, self.mm_per_degree))

    def _zoomed(self):
        """Draw the arc anew where the zoom has changed since it was drawn;
        not while it is held, which would move it under the mouse."""
        if self.root is None or self.held or not self.turning():
            return
        if abs(self.unit_mm() - self.arc_unit) > ZOOM_REDRAW_SHARE * self.arc_unit:
            self._draw_arc()

    def _turn(self):
        """How far the arc is turned about its z axis, from -pi to pi (radians)."""
        _, _, z, w = self.turner.rotation.getValue().getValue()
        # A disc dragger turns about its z axis alone; the quaternion holds half the angle.
        return math.remainder(2 * math.atan2(z, w), 2 * math.pi)

    # The callbacks get the dragger as a plain SoDragger, without its fields;
    # the arrow of `kind` is read instead. It moves in mm: the arrows keep
    # their size on the screen inside, not through the place. The arc is read
    # as the mm the fin moves by its turn, counted on past half a turn.
    def _mm(self, kind):
        if kind == ALONG and self.turning():
            return math.degrees(self.turned) * self.mm_per_degree
        return self.draggers[kind].translation.getValue()[0]

    def turning(self):
        """Whether the arc stands in for the arrow along the face."""
        return self.shown[TURNING].whichChild.getValue() == coin.SO_SWITCH_ALL

    def _held(self, kind, _dragger):
        self.held = True
        self.turned, self.last_turn = 0.0, self._turn()
        self.on_start(kind)

    def _moved(self, kind, _dragger):
        if kind == ALONG and self.turning():
            turn = self._turn()
            self.turned += math.remainder(turn - self.last_turn, 2 * math.pi)
            self.last_turn = turn
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

    def show_preview(self, shapes, color):
        """Show `shapes` see-through in `color`."""
        self._fill(self.preview, shaded(shapes, color, PREVIEW_TRANSPARENCY))

    def show_dropped(self, tines):
        """Mark the tines in `tines`, which find no face, red until shown again."""
        self._fill(self.dropped, *([shaded(tines, INVALID_COLOR, PREVIEW_TRANSPARENCY)] if tines else []))

    def clear_preview(self):
        self._clear(self.preview)

    def hide(self):
        self.zoom_timer.stop()
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
