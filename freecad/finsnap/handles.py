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
from PySide import QtCore, QtWidgets

import FreeCAD as App
import FreeCADGui as Gui

from . import limits
from .i18n import translate

# The colours and the opacity FreeCAD shows its own feature previews in:
# green for what a feature adds, red for an error, faint enough to see through.
VALID_COLOR = (0.0, 1.0, 0.6)
INVALID_COLOR = (1.0, 0.0, 0.0)
# A fin dragged to a height between two tines: it stands, but goes to the
# nearest tine when let go.
BETWEEN_COLOR = (1.0, 0.85, 0.0)
PREVIEW_TRANSPARENCY = 1.0 - 0.2
# How much room View fit selection leaves round what it frames: none.
FIT_SLACK = 1.0
# The least size of what the view is fitted to (mm): a point or a thin face
# shows with the part round it.
FIT_MIN_SIZE = 10.0
# Viewport mappings of a camera that crop the view, framed as a square.
CROPPING_MAPPINGS = (coin.SoCamera.CROP_VIEWPORT_FILL_FRAME, coin.SoCamera.CROP_VIEWPORT_LINE_FRAME,
                     coin.SoCamera.CROP_VIEWPORT_NO_FRAME)
# What a clicked note is about but cannot be selected, marked less
# see-through, so it stands out of the see-through fins it lies in.
NOTED_TRANSPARENCY = 1.0 - 0.7
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
# While an arrow is dragged, its value as the task panel shows it stands past
# its tip: this many pixels high, this many units of the arrow past the tip,
# drawn over everything else; in the colour of the held arrow over a dark
# background of the 3D view, nearly black over a light one.
VALUE_FONT_SIZE = 16
VALUE_GAP = 0.3
VALUE_ON_LIGHT = (0.1, 0.1, 0.1)
# The plumb line of a stability check: this many pixels wide, dashed, a ball
# of this size, in the units of the arrows, at either end, and the footprint
# under it this see-through.
PLUMB_WIDTH = 2
PLUMB_PATTERN = 0xF0F0
PLUMB_BALL = 0.15
FOOTPRINT_TRANSPARENCY = 0.6
# Marks on faces that overhang without fins, by level: yellow where critical,
# red where too flat to print; half see-through, drawn slightly in front of
# the part's own faces, which lie in the same place.
OVERHANG_COLORS = {limits.CRITICAL: BETWEEN_COLOR, limits.UNPRINTABLE: (0.9, 0.1, 0.1)}
OVERHANG_TRANSPARENCY = 0.4
# The first layers of islands in the air: see-through, yet red over a part of
# any colour. As see-through as a fin while editing, the colour of the part
# would show through and the red be lost.
ISLAND_TRANSPARENCY = 0.4
# An island whose first layer the kernel could not cut out is marked at its
# lowest point instead, by a ball of this radius, in the units of the node
# that keeps it the same size on the screen at any zoom.
ISLAND_SPOT_SIZE = 0.3
# The layer a stability check shows cut out of the part, this see-through.
LAYER_CUT_TRANSPARENCY = 0.3
# How closely the colours of a stability check follow the faces of the part
# (mm): coarser than the overhang marks, as the faces are cut by height.
GRADIENT_DEVIATION = 0.2
# The background of the 3D view as FreeCAD keeps it, with FreeCAD's own
# defaults: one colour, or a gradient from the second to the third colour,
# through the fourth where the middle colour is on, packed as 0xRRGGBBAA.
BACKGROUND_SINGLE = ("BackgroundColor", 0xEAE5DCFF)
# FreeCAD's selection colour, which the user sets in the preferences: what a
# clicked note is about but cannot be selected is marked in it.
# Unset, FreeCAD draws the selection in 0.1, 0.8, 0.1, not the colour its
# preferences dialog offers.
SELECTION_COLOR = ("SelectionColor", 0x1ACC1AFF)
BACKGROUND_GRADIENT = (("BackgroundColor2", 0x333365FF), ("BackgroundColor3", 0xABABC1FF))
BACKGROUND_MIDDLE = ("BackgroundColor4", 0x6F6F93FF)
BACKGROUND_FLAGS = (("Gradient", True), ("RadialGradient", False))
BACKGROUND_USE_MIDDLE = ("UseBackgroundColorMid", False)
# A background lighter than this (0 black, 1 white) counts as light; the
# lightness of a colour is weighed as the eye sees it (ITU-R BT.709).
LIGHT_BACKGROUND = 0.5
LIGHTNESS_WEIGHTS = (0.2126, 0.7152, 0.0722)
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
# The parts of a straight arrow's dragger it is drawn as, at rest and held.
TRANSLATE_PARTS = ("translator", "translatorActive")


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


def plumb(found, color, text, text_at):
    """A Coin node showing `found`, a stability.Stability, in `color`, drawn
    over everything else: the footprint see-through on the bed, the plumb
    line dashed from the centre of mass of the part printed up to its layer
    down to the bed, a ball at either end, and `text` at `text_at`, the layer."""
    group = coin.SoAnnotation()
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.transparency.setValue(FOOTPRINT_TRANSPARENCY)
    corners = coin.SoCoordinate3()
    corners.point.setValues(0, len(found.footprint), [(p.x, p.y, p.z) for p in found.footprint])
    outline = coin.SoFaceSet()
    outline.numVertices.setValue(len(found.footprint))
    footprint = coin.SoSeparator()
    for node in (material, corners, outline):
        footprint.addChild(node)
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(PLUMB_WIDTH)
    style.linePattern.setValue(PLUMB_PATTERN)
    line_color = coin.SoBaseColor()
    line_color.rgb.setValue(*color)
    ends = coin.SoCoordinate3()
    ends.point.setValues(0, 2, [tuple(found.centre), tuple(found.foot)])
    line = coin.SoSeparator()
    for node in (style, line_color, ends, coin.SoLineSet()):
        line.addChild(node)
    at = coin.SoTranslation()
    at.translation.setValue(*text_at)
    font = coin.SoFont()
    font.size.setValue(VALUE_FONT_SIZE)
    label = coin.SoText2()
    label.string.setValue(text)
    caption = coin.SoSeparator()
    for node in (at, line_color, font, label):
        caption.addChild(node)
    for node in (footprint, line, spots([found.centre, found.foot], color, 0.0, PLUMB_BALL), caption):
        group.addChild(node)
    return group


def overhang_faces(faces, level):
    """A Coin node marking `faces`, which overhang without fins, in the
    colour of their `level`, limits.CRITICAL or limits.UNPRINTABLE."""
    return shaded(faces, OVERHANG_COLORS[level], OVERHANG_TRANSPARENCY)


def bridge_regions(regions, level):
    """A Coin node showing `regions`, the free regions of bridges on the
    underside of the part, in the colour of their `level`, as overhangs are."""
    return shaded([regions], OVERHANG_COLORS[level], OVERHANG_TRANSPARENCY)


def island_layers(layers):
    """A Coin node showing `layers`, the first layers of islands in the air."""
    return shaded([layers], INVALID_COLOR, ISLAND_TRANSPARENCY)


def layer_cut(cut, color):
    """A Coin node showing `cut`, a layer cut out of the part, in `color`,
    drawn over everything else, so it shows inside the part."""
    group = coin.SoAnnotation()
    group.addChild(shaded([cut], color, LAYER_CUT_TRANSPARENCY))
    return group


def island_spots(points):
    """A Coin node marking `points`, the lowest points of islands whose first
    layer the kernel could not cut out."""
    return spots(points, INVALID_COLOR, ISLAND_TRANSPARENCY, ISLAND_SPOT_SIZE)


def gradient(shape, color_at, heights, transparency):
    """A Coin node colouring the faces of `shape` see-through by height:
    `color_at(z)` gives the colour at a height. Its triangles are cut at
    `heights`, the heights the colours are known at, so the colours follow
    them over a tall face as well, blended between."""
    points, triangles = shape.tessellate(GRADIENT_DEVIATION)
    corners, colors, counts = [], [], []
    cuts = sorted(heights)
    for triangle in triangles:
        polygon = [points[corner] for corner in triangle]
        low = min(point.z for point in polygon)
        high = max(point.z for point in polygon)
        levels = [low] + [z for z in cuts if low < z < high] + [high]
        for bottom, top in zip(levels, levels[1:]):
            piece = _clipped(_clipped(polygon, bottom, 1), top, -1)
            if len(piece) < 3:
                continue
            corners += [(p.x, p.y, p.z) for p in piece]
            colors += [color_at(p.z) for p in piece]
            counts.append(len(piece))
    material = coin.SoMaterial()
    material.diffuseColor.setValues(0, len(colors), colors)
    material.transparency.setValues(0, len(colors), [transparency] * len(colors))
    binding = coin.SoMaterialBinding()
    binding.value.setValue(coin.SoMaterialBinding.PER_VERTEX)
    offset = coin.SoPolygonOffset()
    offset.factor.setValue(FACE_OFFSET)
    offset.units.setValue(FACE_OFFSET)
    coordinates = coin.SoCoordinate3()
    coordinates.point.setValues(0, len(corners), corners)
    faces = coin.SoFaceSet()
    faces.numVertices.setValues(0, len(counts), counts)
    group = coin.SoSeparator()
    for node in (material, binding, offset, coordinates, faces):
        group.addChild(node)
    return group


def _clipped(polygon, z, keep):
    """The part of `polygon`, a list of App.Vectors, above the height `z` for
    `keep` 1, below it for -1: the polygon cut by that plane."""
    kept = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        start_in = (start.z - z) * keep >= 0
        end_in = (end.z - z) * keep >= 0
        if start_in:
            kept.append(start)
        if start_in != end_in:
            share = (z - start.z) / (end.z - start.z)
            kept.append(start + (end - start) * share)
    return kept


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


def _view_color(name, standard):
    """The colour `name` of FreeCAD's view preferences, `standard` if unset, as RGB from 0 to 1."""
    packed = App.ParamGet(VIEW_PARAMETERS).GetUnsigned(name, standard)
    # Packed as 0xRRGGBBAA.
    return tuple((packed >> shift & BYTE) / BYTE for shift in (24, 16, 8))


def axis_color(axis):
    """The colour of `axis` ("x", "y" or "z") in FreeCAD's preferences, as RGB from 0 to 1."""
    return _view_color(*AXIS_COLORS[axis])


def value_color():
    """The colour the value of a dragged arrow is written in: that of the
    held arrow over a dark background of the 3D view, nearly black over a
    light one, the background taken as the mean of its colours.

    INPUTS this has to withstand:
      one dark colour                       ->  HELD_COLOR
      one light colour, as white            ->  VALUE_ON_LIGHT
      a gradient, FreeCAD's own             ->  by the mean of its two colours
      a gradient through a middle colour    ->  by the mean of its three colours
      nothing set                           ->  FreeCAD's defaults, a gradient
    """
    view = App.ParamGet(VIEW_PARAMETERS)
    if any(view.GetBool(*flag) for flag in BACKGROUND_FLAGS):
        colors = [_view_color(*entry) for entry in BACKGROUND_GRADIENT]
        if view.GetBool(*BACKGROUND_USE_MIDDLE):
            colors.append(_view_color(*BACKGROUND_MIDDLE))
    else:
        colors = [_view_color(*BACKGROUND_SINGLE)]
    lightness = sum(sum(w * c for w, c in zip(LIGHTNESS_WEIGHTS, color)) for color in colors) / len(colors)
    return VALUE_ON_LIGHT if lightness > LIGHT_BACKGROUND else HELD_COLOR


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


def arc_point(radius, unit, sense, length):
    """The point `length` mm along half an arc arrow from (radius, 0, 0), as
    fill_half_arc() draws it: round the z axis, the right way round for
    `sense` 1, the other for -1, shortened alike where the arrow, whose unit
    is `unit` mm, would go further round than ARC_MAX_HALF_TURN."""
    share = min(1.0, ARC_MAX_HALF_TURN * radius / unit)
    angle = sense * length * share / radius
    return coin.SbVec3f(radius * math.cos(angle), radius * math.sin(angle), 0)


def fill_half_arc(body, radius, unit, sense):
    """Draw into `body` half an arrow from (radius, 0, 0) round the circle of
    `radius` about the z axis (mm): the right way round for `sense` 1, the
    other for -1. It is as long and as thick as half a straight arrow whose
    unit is `unit` mm, but goes no further round than ARC_MAX_HALF_TURN."""
    body.removeAllChildren()

    def point(length):
        return arc_point(radius, unit, sense, length)

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


# The arrows of every task panel open, so their objects can look as before
# editing while their documents are saved (saving_document()).
EDITING = []


def saving_document(document, started):
    """Before `document` is saved, `started` True, its objects being edited
    take the look they had before editing, so it is that look the file keeps
    and not the see-through green of editing; after, the look of editing again."""
    for arrows in list(EDITING):
        try:
            mine = arrows.vobj.Object.Document is document
        except ReferenceError:
            # The object went with its panel still open; nothing to show.
            continue
        if mine:
            arrows.saving(started)


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
        # How the object looked before, put back by remove() and while its
        # document is saved (saving()); the look while editing, kept then.
        self.look = (vobj.ShapeAppearance, vobj.Transparency)
        self.editing_look = None
        vobj.Transparency = round(PREVIEW_TRANSPARENCY * PERCENT)
        self.tint(True)
        EDITING.append(self)

        self.view = view
        self.callbacks = []
        self.root = coin.SoSeparator()
        # Switches, switched off while there is nothing to show.
        self.arrows = coin.SoSwitch()
        self.preview = coin.SoSwitch()
        self.dropped = coin.SoSwitch()
        self.noted = coin.SoSwitch()
        self.value = coin.SoSwitch()
        for node in (self.arrows, self.preview, self.dropped, self.noted, self.value):
            node.whichChild.setValue(coin.SO_SWITCH_NONE)
            self.root.addChild(node)
        self.value.addChild(self._value_group())
        # Each arrow: where it stands and how long it is, and the dragger; the
        # halves of its two looks, at rest and held, and which ends it shows.
        self.places, self.draggers = {}, {}
        # Each arrow off the edge of its fin, in the units of the arrow; one
        # node shared by its two looks.
        self.offsets = {kind: coin.SoTranslation() for kind in KINDS}
        self.halves, self.ends = {}, {}
        # The looks of each arrow, by the arrow (ALONG, UP or TURNING) and the
        # part of its dragger they are, at rest or held.
        self.looks = {}
        # Each straight arrow, and the arc that stands in for the one along the
        # face under a round side, switched on while it shows.
        self.shown = {}
        for kind in KINDS:
            self.places[kind], self.draggers[kind] = self._add_dragger(kind, coin.SoTranslate1Dragger(),
                                                                       ("feedback", "feedbackActive"))
            self.halves[kind], self.ends[kind] = {}, (BACK, FORTH)
            self._look(kind, TRANSLATE_PARTS[1], HELD_COLOR)
        self._look(UP, TRANSLATE_PARTS[0], axis_color("z"))
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
        self.arc_radius = 0.0
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
        for name, method in (("addStartCallback", self._held), ("addMotionCallback", self._dragged),
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
        self.looks[kind, part] = node
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
            self._look(ALONG, TRANSLATE_PARTS[0], axis_color(axis))
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
                self.looks[TURNING, part] = node
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
        self.arc_radius = radial.Length
        for bodies in self.arc_bodies.values():
            for end, body in bodies.items():
                fill_half_arc(body, self.arc_radius, self.arc_unit, self._arc_sense(end))

    def _arc_sense(self, end):
        """Which way round the end BACK or FORTH of the arc goes, as
        fill_half_arc() takes it: the way the fin moves along the face."""
        return end * math.copysign(1, self.mm_per_degree)

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
        # Held: the look of a held arrow in its own colour again, should a
        # drag before have been let go by _dragged().
        self._tint_held(kind, HELD_COLOR)
        self.turned, self.last_turn = 0.0, self._turn()
        self.on_start(kind)

    def _dragged(self, kind, dragger):
        """A move of the arrow of `kind` from Coin. A drag goes on only while
        the button that grabbed the arrow is down: should its release not reach
        the dragger, the arrow would stay grabbed and follow the mouse with no
        button pressed. Then it is let go here, as the release would, and Coin
        is told to let it go too."""
        if QtWidgets.QApplication.mouseButtons() & QtCore.Qt.LeftButton:
            self._moved(kind, dragger)
            return
        # The dragger itself, not the plain one Coin passes: Coin left it
        # active, and an active dragger follows every move of the mouse.
        arrow = self.turner if kind == ALONG and self.turning() else self.draggers[kind]
        arrow.isActive.setValue(False)
        action = arrow.getHandleEventAction()
        if action is not None and action.getGrabber() is not None:
            action.releaseGrabber()
        # Coin also leaves it showing its held look, which only it can switch
        # back; that look takes the colour of the arrow at rest instead.
        self._tint_held(kind, self._rest_color(kind))
        if self.held:
            self._let_go(kind, dragger)

    def _held_look(self, kind):
        """The look of the arrow of `kind` while it is held: of the arc where it
        stands in for the arrow along the face."""
        if kind == ALONG and self.turning():
            return self.looks.get((TURNING, TURN_PARTS[1]))
        return self.looks.get((kind, TRANSLATE_PARTS[1]))

    def _tint_held(self, kind, color):
        """Give the look of the arrow of `kind` while held the colour `color`,
        its first node; no node changes, so a held arrow keeps its scene."""
        look = self._held_look(kind)
        if look is not None:
            look.getChild(0).rgb.setValue(*color)

    def _rest_color(self, kind):
        """The colour of the arrow of `kind` at rest: that of the axis it is
        nearest to, z for the arrow up."""
        return axis_color("z") if kind == UP else axis_color(self.along_axis)

    def _moved(self, kind, _dragger):
        if kind == ALONG and self.turning():
            turn = self._turn()
            self.turned += math.remainder(turn - self.last_turn, 2 * math.pi)
            self.last_turn = turn
        self.on_move(kind, self._mm(kind))

    def _let_go(self, kind, _dragger):
        self.held = False
        self.on_done(kind, self._mm(kind))

    def _value_group(self):
        """The nodes of the value shown past the tip of a dragged arrow, made
        once: while an arrow is held only their fields change, as a scene
        changed under a held dragger can lose the release of the mouse."""
        self.value_at = coin.SoTransform()
        zoom = coin.SoType.fromName(AUTO_ZOOM).createInstance()
        zoom.scaleFactor.setValue(ARROW_SCREEN_SIZE)
        self.value_past_tip = coin.SoTranslation()
        color = coin.SoBaseColor()
        color.rgb.setValue(*value_color())
        font = coin.SoFont()
        font.size.setValue(VALUE_FONT_SIZE)
        self.value_label = coin.SoText2()
        group = coin.SoAnnotation()
        for node in (self.value_at, zoom, self.value_past_tip, color, font, self.value_label):
            group.addChild(node)
        return group

    def show_value(self, kind, text):
        """Show `text`, the value of the arrow of `kind` as the task panel
        shows it, past the tip of that arrow where it is dragged to: of the
        arc, where it stands in for the arrow along the face, past the tip of
        its end FORTH, turning with it."""
        if kind == ALONG and self.turning():
            past = arc_point(self.arc_radius, self.arc_unit, self._arc_sense(FORTH),
                             (1 + VALUE_GAP) * self.arc_unit)
            turned = self.turner.rotation.getValue().multVec(past)
            self.value_at.translation.setValue(self.turn_place.translation.getValue()
                                               + self.turn_place.rotation.getValue().multVec(turned))
            self.value_at.rotation.setValue(coin.SbRotation())
            self.value_past_tip.translation.setValue(0, 0, 0)
        else:
            place = self.places[kind]
            moved = place.rotation.getValue().multVec(self.draggers[kind].translation.getValue())
            self.value_at.translation.setValue(place.translation.getValue() + moved)
            self.value_at.rotation.setValue(place.rotation.getValue())
            self.value_past_tip.translation.setValue(self.offsets[kind].translation.getValue()
                                                     + coin.SbVec3f(1 + VALUE_GAP, 0, 0))
        self.value_label.string.setValue(text)
        self.value.whichChild.setValue(coin.SO_SWITCH_ALL)

    def hide_value(self):
        self.value.whichChild.setValue(coin.SO_SWITCH_NONE)

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

    def show_noted(self, shapes, points=()):
        """Mark `shapes` and `points`, what a clicked note is about but cannot
        be selected, in the selection colour, the points as balls; none, nothing."""
        color = _view_color(*SELECTION_COLOR)
        nodes = [shaded(shapes, color, NOTED_TRANSPARENCY)] if shapes else []
        if points:
            nodes.append(spots(points, color, NOTED_TRANSPARENCY, ISLAND_SPOT_SIZE))
        self._fill(self.noted, *nodes)

    def fit(self, shapes, points=()):
        """Fit the view to `shapes` and `points`, as View fit selection does to
        what is selected: the camera framing their bounding box, at least
        FIT_MIN_SIZE wide, so a single point is not zoomed into. Done here
        rather than by that command, whose message not every FreeCAD acts on
        at once."""
        box = App.BoundBox()
        for shape in shapes:
            box.add(shape.BoundBox)
        for point in points:
            box.add(point)
        if not box.isValid():
            return
        box.enlarge(max(0.0, (FIT_MIN_SIZE - min(box.XLength, box.YLength, box.ZLength)) / 2))
        camera = self.view.getCameraNode()
        aspect = self.viewer.getSoRenderManager().getViewportRegion().getViewportAspectRatio()
        # A camera that crops the viewport fits a square, as FreeCAD does.
        if camera.viewportMapping.getValue() in CROPPING_MAPPINGS:
            aspect = 1.0
        camera.viewBoundingBox(coin.SbBox3f(box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax), aspect,
                               FIT_SLACK)

    def clear_preview(self):
        self._clear(self.preview)

    def hide(self):
        self.zoom_timer.stop()
        self.arrows.whichChild.setValue(coin.SO_SWITCH_NONE)
        self._clear(self.preview)
        self.hide_value()

    def remove(self):
        if self.root is None:
            return
        self.hide()
        for dragger, name, callback in self.callbacks:
            self.view.removeDraggerCallback(dragger, name, callback)
        self.callbacks = []
        self._clear(self.dropped)
        self._clear(self.noted)
        if self.attached:
            self.viewer.resetEditingRoot()
        # Not attached any more, also when the panel closes before it was.
        self.root = None
        self.vobj.ShapeAppearance, self.vobj.Transparency = self.look
        if self in EDITING:
            EDITING.remove(self)

    def saving(self, started):
        """While the document of the object is saved, `started` True, it looks
        as it did before editing, so the file keeps that look; once saved, as
        while editing again."""
        if started:
            self.editing_look = (self.vobj.ShapeAppearance, self.vobj.Transparency)
            self.vobj.ShapeAppearance, self.vobj.Transparency = self.look
        elif self.editing_look is not None:
            self.vobj.ShapeAppearance, self.vobj.Transparency = self.editing_look
            self.editing_look = None
