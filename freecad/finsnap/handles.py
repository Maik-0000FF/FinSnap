"""Handles in the 3D view to move a fin along its face and to set its height.

The task panel puts them on the fin last picked. While one is dragged, a
see-through preview of the fin follows: green where the fin can stand, red
where it cannot, with the tines that would find no face in red. Letting go
hands the change to the task panel, which builds the fins with it.

Shapes are drawn here as well, so the overhang marks and the previews share
one way of putting faces into the scene.
"""

from pivy import coin

import FreeCAD as App

# The colours and the opacity FreeCAD shows its own feature previews in:
# green for what a feature adds, red for an error, faint enough to see through.
VALID_COLOR = (0.0, 1.0, 0.6)
INVALID_COLOR = (1.0, 0.0, 0.0)
PREVIEW_TRANSPARENCY = 1.0 - 0.2
# Largest deviation of drawn faces from the true faces (mm).
MESH_DEVIATION = 0.1
# Drawn faces lie this far in front of the faces they cover, so they show
# through instead of flickering with them.
FACE_OFFSET = -1.0

ALONG, UP = "along", "up"
HANDLE_LENGTH = 12.0  # from tip to tip (mm)
HANDLE_GAP = 3.0      # between the top of the fin and a handle (mm)
UP_DIRECTION = App.Vector(0, 0, 1)
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


def _length(dragger):
    """The length of `dragger` along its axis, in its own units."""
    action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion())
    action.apply(dragger)
    low, high = action.getBoundingBox().getMin(), action.getBoundingBox().getMax()
    return high[0] - low[0]


class Handles:
    """Two handles on one fin, one along the face and one up.

    on_move(kind, mm) is called while a handle is dragged, on_done(kind, mm)
    when it is let go; kind is ALONG or UP, mm how far from where it started.
    """

    def __init__(self, parent, on_move, on_done):
        self.parent = parent
        self.on_move, self.on_done = on_move, on_done
        self.root = coin.SoSeparator()
        self.arrows = coin.SoSeparator()
        self.preview = coin.SoSeparator()
        self.root.addChild(self.arrows)
        self.root.addChild(self.preview)
        parent.addChild(self.root)
        self.scale = None

    def show(self, top, along):
        """Put the handles over `top`, the middle of the top of a fin; `along`
        is the direction along the face."""
        self.arrows.removeAllChildren()
        self.preview.removeAllChildren()
        lift = UP_DIRECTION * HANDLE_GAP
        # The handle up stands above the one along, so neither hides the other.
        for kind, direction, middle in ((ALONG, along, top + lift),
                                        (UP, UP_DIRECTION, top + lift * 2 + UP_DIRECTION * (HANDLE_LENGTH / 2))):
            dragger = coin.SoTranslate1Dragger()
            if self.scale is None:
                self.scale = HANDLE_LENGTH / _length(dragger)
            place = coin.SoTransform()
            place.translation.setValue(middle.x, middle.y, middle.z)
            place.rotation.setValue(coin.SbRotation(DRAGGER_AXIS, coin.SbVec3f(direction.x, direction.y,
                                                                               direction.z)))
            place.scaleFactor.setValue(self.scale, self.scale, self.scale)
            dragger.addMotionCallback(self._moved, kind)
            dragger.addFinishCallback(self._let_go, kind)
            group = coin.SoSeparator()
            group.addChild(place)
            group.addChild(dragger)
            self.arrows.addChild(group)

    def _mm(self, dragger):
        return dragger.translation.getValue()[0] * self.scale

    def _moved(self, kind, dragger):
        self.on_move(kind, self._mm(dragger))

    def _let_go(self, kind, dragger):
        self.on_done(kind, self._mm(dragger))

    def show_preview(self, shapes, valid, dropped=()):
        """Show `shapes` see-through, green if `valid`, else red, and the tines
        in `dropped` red."""
        self.preview.removeAllChildren()
        self.preview.addChild(shaded(shapes, VALID_COLOR if valid else INVALID_COLOR, PREVIEW_TRANSPARENCY))
        if dropped:
            self.preview.addChild(shaded(dropped, INVALID_COLOR, PREVIEW_TRANSPARENCY))

    def hide(self):
        self.arrows.removeAllChildren()
        self.preview.removeAllChildren()

    def remove(self):
        self.hide()
        self.parent.removeChild(self.root)
