"""The parametric FinSnap object.

One table, PROPERTIES, describes every parameter once: its property name, type,
group, label, tooltip and the FinParams field behind it. Creating the properties,
reading them back into FinParams and building the task panel all walk this
table, so a new parameter is added in exactly one place (plus its default).
"""

from collections import namedtuple

import FreeCAD as App
import Part

from . import defaults as d
from . import geometry
from . import overhang
from . import presets
from .i18n import QT_TRANSLATE_NOOP, translate
from .params import FinParams
from .shapes import face_name, global_shape, outermost

TYPE_NAME = "FinSnap"
# Result property listing the faces that overhang without fins; the view
# provider marks them.
OVERHANGS = "Overhangs"
# Hidden marker on fins whose part was laid flat again with the fins kept:
# they keep their last shape, moved along with the part, until it is moved again.
LAID_FLAT = "LaidFlat"
# Where the part was laid flat; moved from there, the fins are rebuilt.
LAID_FLAT_AT = "LaidFlatAt"
# The faces of the part the fins were last built under, so overhang marks leave
# out exactly those.
CARRIED = "CarriedFaces"
NOTE_LAID_FLAT = QT_TRANSLATE_NOOP(
    "FinSnap", "The part lies flat again: the fins keep their last shape until the part is moved, for example "
    "stood on its edge again; then they are rebuilt.")

GROUP_SLICER = QT_TRANSLATE_NOOP("App::Property", "Slicer")
GROUP_CONNECTION = QT_TRANSLATE_NOOP("App::Property", "Connection")
GROUP_TINES = QT_TRANSLATE_NOOP("App::Property", "Tines")
GROUP_FIN = QT_TRANSLATE_NOOP("App::Property", "Fin")
GROUP_PLACEMENT = QT_TRANSLATE_NOOP("App::Property", "Placement of fins")
GROUP_FOOT = QT_TRANSLATE_NOOP("App::Property", "Foot")
GROUP_COUNTER = QT_TRANSLATE_NOOP("App::Property", "Counter fin")
GROUP_SOURCE = QT_TRANSLATE_NOOP("App::Property", "Source")
GROUP_RESULT = QT_TRANSLATE_NOOP("App::Property", "Result")

LENGTH = "App::PropertyLength"
INTEGER = "App::PropertyInteger"
FLOAT = "App::PropertyFloat"
CHOICE = "App::PropertyEnumeration"
# Editor mode that hides a property in the property view.
EDITOR_HIDDEN = 2

Prop = namedtuple("Prop", "name kind group label tip field choices")

# Short explanations shown at the top of each group in the task panel.
GROUP_INFO = {
    GROUP_SLICER: QT_TRANSLATE_NOOP(
        "FinSnap", "Enter the values of the print profile you will slice with. Tines and fin "
        "are sized in beads and layers of this profile."),
    GROUP_CONNECTION: QT_TRANSLATE_NOOP(
        "FinSnap", "Separate keeps the fins a separate object that only touches the part and "
        "breaks off cleanly. Merged prints fins and part as one body. A tine clearance keeps the "
        "ends of the tines that far from the face."),
    GROUP_TINES: QT_TRANSLATE_NOOP(
        "FinSnap", "Tines are the small horizontal contacts between fin and part. The highest "
        "tine sets the height of the fin."),
    GROUP_FIN: QT_TRANSLATE_NOOP(
        "FinSnap", "0 means automatic: the thickness grows with the height, the height ends at "
        "the highest tine."),
    GROUP_PLACEMENT: QT_TRANSLATE_NOOP(
        "FinSnap", "Automatic places one fin per face length set below, a single fin in the "
        "centre."),
    GROUP_FOOT: QT_TRANSLATE_NOOP(
        "FinSnap", "The foot holds the fin on the bed. It is narrowed automatically so that the "
        "feet of neighbouring fins never touch."),
    GROUP_COUNTER: QT_TRANSLATE_NOOP(
        "FinSnap", "A fin on the opposite face, against tipping away, as large as the main fin. It "
        "only has to stop the part from tipping over, so fewer tines are enough to make it smaller. "
        "Add it with Add counter fin, or select a second face when adding the fins."),
}

# Letters of the parameters in the drawings of the task panel (images/).
MARKS = {
    "Gap": "A", "TineSpacing": "B", "TineFirst": "C", "TineLayers": "D", "FinHeight": "E",
    "FinPlateau": "F", "FootThickness": "G", "FinThickness": "H", "EndInset": "I",
    "FootHalfWidth": "J", "TineClearance": "K",
}

# Labels for the values of enumerations, as the task panel shows them.
CHOICE_LABELS = {
    d.CONNECTION_SEPARATE: QT_TRANSLATE_NOOP("FinSnap", "separate, touching only"),
    d.CONNECTION_MERGED: QT_TRANSLATE_NOOP("FinSnap", "merged into the part"),
    d.PLACEMENT_AUTO: QT_TRANSLATE_NOOP("FinSnap", "automatic"),
    d.PLACEMENT_CENTER: QT_TRANSLATE_NOOP("FinSnap", "one in the centre"),
    d.PLACEMENT_ENDS: QT_TRANSLATE_NOOP("FinSnap", "two at the ends"),
    d.PLACEMENT_CORNERS: QT_TRANSLATE_NOOP("FinSnap", "two on the corners"),
    d.PLACEMENT_CORNER_LEFT: QT_TRANSLATE_NOOP("FinSnap", "one on the left corner"),
    d.PLACEMENT_CORNER_RIGHT: QT_TRANSLATE_NOOP("FinSnap", "one on the right corner"),
    d.PLACEMENT_DISTRIBUTED: QT_TRANSLATE_NOOP("FinSnap", "distributed"),
    d.FOOT_ELLIPSE: QT_TRANSLATE_NOOP("FinSnap", "oval"),
    d.FOOT_RECTANGLE: QT_TRANSLATE_NOOP("FinSnap", "rectangle"),
    d.FOOT_NONE: QT_TRANSLATE_NOOP("FinSnap", "none"),
}

# choices: allowed values of an enumeration, None for plain values.
PROPERTIES = (
    Prop("NozzleDiameter", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "Nozzle diameter"),
         QT_TRANSLATE_NOOP("App::Property", "Nozzle diameter of the print profile"),
         "nozzle_diameter", None),
    Prop("BeadWidth", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "Bead width"),
         QT_TRANSLATE_NOOP("App::Property", "Extrusion width of the outer perimeter"),
         "bead_width", None),
    Prop("LayerHeight", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "Layer height"),
         QT_TRANSLATE_NOOP("App::Property", "Layer height of the print profile"),
         "layer_height", None),
    Prop("FirstLayerHeight", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "First layer height"),
         QT_TRANSLATE_NOOP("App::Property", "Height of the first layer"),
         "first_layer_height", None),
    Prop("Connection", CHOICE, GROUP_CONNECTION,
         QT_TRANSLATE_NOOP("FinSnap", "Connection"),
         QT_TRANSLATE_NOOP("App::Property",
                           "separate: fins are their own object and only touch the part; "
                           "merged: fins and part become one body"),
         "connection", d.CONNECTIONS),
    Prop("Gap", LENGTH, GROUP_CONNECTION,
         QT_TRANSLATE_NOOP("FinSnap", "Gap"),
         QT_TRANSLATE_NOOP("App::Property", "Clearance between fin and face, along the face normal"),
         "gap", None),
    Prop("TineClearance", LENGTH, GROUP_CONNECTION,
         QT_TRANSLATE_NOOP("FinSnap", "Tine clearance"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Distance between the end of a tine and the face, along the face normal; 0 = the "
                           "tine touches the face. More leaves fainter marks, too much and the tine does not "
                           "hold: find the value by a test print."),
         "tine_clearance", None),
    Prop("TineSpacing", LENGTH, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine spacing"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Vertical distance between tines, at least the tine height plus one layer"),
         "tine_spacing", None),
    Prop("TineFirst", LENGTH, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine first"),
         QT_TRANSLATE_NOOP("App::Property", "Height of the lowest tine above the bed, 0 = on the top of the foot"),
         "tine_first", None),
    Prop("TineLayers", INTEGER, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine layers"),
         QT_TRANSLATE_NOOP("App::Property", "Tine height in layers"),
         "tine_layers", None),
    Prop("TineWidthBeads", INTEGER, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine width beads"),
         QT_TRANSLATE_NOOP("App::Property", "Tine width in beads"),
         "tine_width_beads", None),
    Prop("TineCount", INTEGER, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine count"),
         QT_TRANSLATE_NOOP("App::Property", "Number of tines per fin, 0 = as many as fit"),
         "tine_count", None),
    Prop("FinThickness", LENGTH, GROUP_FIN,
         QT_TRANSLATE_NOOP("FinSnap", "Fin thickness"),
         QT_TRANSLATE_NOOP("App::Property", "Wall thickness of a fin, 0 = from its height"),
         "fin_thickness", None),
    Prop("FinHeight", LENGTH, GROUP_FIN,
         QT_TRANSLATE_NOOP("FinSnap", "Fin height"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Height of the fins, 0 = top of the highest tine. A lower value leaves out the "
                           "tines above it; the fins reach at most to just below the top of the face."),
         "fin_height", None),
    Prop("FinPlateau", LENGTH, GROUP_FIN,
         QT_TRANSLATE_NOOP("FinSnap", "Top width"),
         QT_TRANSLATE_NOOP("App::Property", "Width of the flat top of a fin"),
         "fin_plateau", None),
    Prop("FinPlacement", CHOICE, GROUP_PLACEMENT,
         QT_TRANSLATE_NOOP("FinSnap", "Fin placement"),
         QT_TRANSLATE_NOOP("App::Property",
                           "auto: by face length; center: one fin; ends: two fins; corners: two fins "
                           "on the face ends, each tine whole on the face and flush with its end, so the "
                           "tine marks merge with the edges; the fin reaches a little past the end; "
                           "left corner, right corner: one such fin on that end, left and right as seen "
                           "from outside, looking at the face; "
                           "distributed: FinCount fins"),
         "placement", d.PLACEMENTS),
    Prop("FinCount", INTEGER, GROUP_PLACEMENT,
         QT_TRANSLATE_NOOP("FinSnap", "Fin count"),
         QT_TRANSLATE_NOOP("App::Property", "Number of fins for distributed placement"),
         "fin_count", None),
    Prop("EndInset", LENGTH, GROUP_PLACEMENT,
         QT_TRANSLATE_NOOP("FinSnap", "End inset"),
         QT_TRANSLATE_NOOP("App::Property", "Distance of the outer fins from the face ends"),
         "end_inset", None),
    Prop("FaceLengthPerFin", LENGTH, GROUP_PLACEMENT,
         QT_TRANSLATE_NOOP("FinSnap", "Face length per fin"),
         QT_TRANSLATE_NOOP("App::Property", "Automatic placement: one fin per this much face length"),
         "face_length_per_fin", None),
    Prop("FootShape", CHOICE, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot shape"),
         QT_TRANSLATE_NOOP("App::Property", "Shape of the foot on the bed"),
         "foot_shape", d.FOOT_SHAPES),
    Prop("FootThickness", LENGTH, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot thickness"),
         QT_TRANSLATE_NOOP("App::Property", "Height of the foot, rounded to whole layers"),
         "foot_thickness", None),
    Prop("FootOverhang", LENGTH, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot overhang"),
         QT_TRANSLATE_NOOP("App::Property", "How far the foot reaches past the outer end of the fin"),
         "foot_overhang", None),
    Prop("FootWidthRatio", FLOAT, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot width ratio"),
         QT_TRANSLATE_NOOP("App::Property", "Foot width as a share of its length"),
         "foot_width_ratio", None),
    Prop("FootHalfWidth", LENGTH, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot half width"),
         QT_TRANSLATE_NOOP("App::Property", "Half width of the foot, 0 = from FootWidthRatio"),
         "foot_half_width", None),
    Prop("CounterTineCount", INTEGER, GROUP_COUNTER,
         QT_TRANSLATE_NOOP("FinSnap", "Counter tine count"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Tines of the counter fin, 0 = as many as the main fin. The counter fin only has "
                           "to stop the part from tipping over, so it may be smaller."),
         "counter_tine_count", None),
)

# Fields that only take effect while another field holds one of `values`. The
# task panel greys them out otherwise and says why in the tooltip. `control`
# may also name a link that is no panel field; then it counts as set or not.
Depends = namedtuple("Depends", "name control values note")
FOOT_SHAPES_WITH_FOOT = tuple(s for s in d.FOOT_SHAPES if s != d.FOOT_NONE)
NOTE_NO_FOOT = QT_TRANSLATE_NOOP("FinSnap", "Not used without a foot.")
DEPENDS = (
    Depends("FinCount", "FinPlacement", (d.PLACEMENT_DISTRIBUTED,),
            QT_TRANSLATE_NOOP("FinSnap", "Only used with distributed placement.")),
    Depends("FaceLengthPerFin", "FinPlacement", (d.PLACEMENT_AUTO,),
            QT_TRANSLATE_NOOP("FinSnap", "Only used with automatic placement.")),
    Depends("EndInset", "FinPlacement", (d.PLACEMENT_AUTO, d.PLACEMENT_ENDS, d.PLACEMENT_DISTRIBUTED),
            QT_TRANSLATE_NOOP("FinSnap", "Not used with one fin in the centre or fins on the corners.")),
    Depends("FootThickness", "FootShape", FOOT_SHAPES_WITH_FOOT, NOTE_NO_FOOT),
    Depends("FootOverhang", "FootShape", FOOT_SHAPES_WITH_FOOT, NOTE_NO_FOOT),
    Depends("FootWidthRatio", "FootShape", FOOT_SHAPES_WITH_FOOT, NOTE_NO_FOOT),
    Depends("FootHalfWidth", "FootShape", FOOT_SHAPES_WITH_FOOT, NOTE_NO_FOOT),
    Depends("FootWidthRatio", "FootHalfWidth", (0,),
            QT_TRANSLATE_NOOP("FinSnap", "Only used while Foot half width is 0.")),
    Depends("CounterTineCount", "CounterFace", (True,),
            QT_TRANSLATE_NOOP("FinSnap", "Only used with a counter fin.")),
)


def unused_notes(name, current):
    """Why field `name` has no effect, empty if it has one. current(name) gives a field's value."""
    return [dep.note for dep in DEPENDS if dep.name == name and current(dep.control) not in dep.values]


def value_of(obj, name):
    value = getattr(obj, name)
    return value.Value if hasattr(value, "Value") else value


def add_property(obj, prop, value):
    obj.addProperty(prop.kind, prop.name, prop.group, prop.tip)
    if prop.choices:
        setattr(obj, prop.name, list(prop.choices))
    setattr(obj, prop.name, value)


def add_properties(obj):
    defaults = presets.standard()
    obj.addProperty("App::PropertyLinkSubGlobal", "Base", GROUP_SOURCE,
                    QT_TRANSLATE_NOOP("App::Property", "Part and the face the fins support"))
    obj.addProperty("App::PropertyLinkGlobal", "Container", GROUP_SOURCE,
                    QT_TRANSLATE_NOOP("App::Property",
                                      "Outermost container of the part, so moving it rebuilds the fins"))
    # A hidden link would not pass the container's move on; a global one does.
    obj.setEditorMode("Container", EDITOR_HIDDEN)
    obj.addProperty("App::PropertyLinkSubGlobal", "CounterFace", GROUP_COUNTER,
                    QT_TRANSLATE_NOOP("App::Property",
                                      "Optional face on the opposite side for a small counter fin"))
    for prop in PROPERTIES:
        add_property(obj, prop, getattr(defaults, prop.field))

    results = (("ResultHeight", LENGTH), ("ResultThickness", LENGTH), ("ResultFinCount", INTEGER))
    for name, kind in results:
        obj.addProperty(kind, name, GROUP_RESULT, "", 1)
    obj.addProperty("App::PropertyStringList", "Warnings", GROUP_RESULT, "", 1)
    add_overhangs(obj)


def add_overhangs(obj):
    obj.addProperty("App::PropertyStringList", OVERHANGS, GROUP_RESULT,
                    QT_TRANSLATE_NOOP("App::Property",
                                      "Faces of the part that overhang too flatly and carry no fins"), 1)


def params_of(obj):
    return FinParams(**{prop.field: value_of(obj, prop.name) for prop in PROPERTIES})


def _face(link):
    part, subs = link
    if not subs:
        raise geometry.FinError(translate("FinSnap", "no face selected on %s") % part.Label)
    shape = global_shape(part)
    return shape, shape.getElement(subs[0])


def _supported(part_obj, document):
    """Faces of `part_obj` that carry fins of any FinSnap object in `document`:
    the faces the fins were last built under, or else the faces they link to.

    INPUTS this has to withstand:
      fins built, faces recorded            ->  the recorded faces
      fins never built, or built nothing    ->  the faces they link to
      a face the part no longer has         ->  left out
      part edited, faces numbered anew      ->  recorded names of other fins may
                                                point to other faces until those are
                                                rebuilt; FreeCAD renames links, not
                                                these names. Accepted: it lasts one
                                                recompute and only with several fin
                                                objects on one part
    """
    shape = global_shape(part_obj)
    names = []
    for other in document.Objects:
        if not is_fins(other):
            continue
        carried = getattr(other, CARRIED, [])
        if carried and other.Base and other.Base[0] is part_obj:
            names.extend(carried)
            continue
        for link in (other.Base, other.CounterFace):
            if link and link[0] is part_obj and link[1]:
                names.append(link[1][0])
    faces = []
    for name in names:
        try:
            faces.append(shape.getElement(name))
        except (ValueError, IndexError, Part.OCCError):
            # The part changed and lost this face; those fins report it
            # themselves, the others are still built.
            continue
    return shape, faces


def overhangs_of(part_obj, document):
    """Names of the faces of `part_obj` that overhang without fins."""
    shape, supported = _supported(part_obj, document)
    return [face_name(number) for number in overhang.overhangs(shape, supported)]


class FinSnapFeature:
    def __init__(self, obj):
        obj.Proxy = self
        add_properties(obj)

    def execute(self, obj):
        if not obj.Base:
            return
        if still_laid_flat(obj):
            # The fins keep the shape they were moved to; the face they belong
            # to no longer leans over the bed until the part stands again.
            setattr(obj, OVERHANGS, [])
            obj.Warnings = [translate("FinSnap", NOTE_LAID_FLAT)]
            return
        p = params_of(obj)
        try:
            part, face = _face(obj.Base)
            result = geometry.build(part, face, p)
            counter = None
            if obj.CounterFace:
                counter_part, counter_face = _face(obj.CounterFace)
                counter = geometry.build(counter_part, counter_face, p,
                                         tine_count=p.counter_tine_count or None)
        except Exception:
            # Built nothing, the fins carry no face; the overhang marks still
            # follow the part.
            hidden_property(obj, CARRIED, "App::PropertyStringList")
            setattr(obj, CARRIED, [])
            setattr(obj, OVERHANGS, overhangs_of(obj.Base[0], obj.Document))
            raise
        # Named on the shape each face was found on: the counter face comes from
        # a shape of its own, even of the same part.
        carried = [face_name_of(part, f) for f in result.carried]
        if counter is not None and obj.CounterFace[0] is obj.Base[0]:
            carried += [face_name_of(counter_part, f) for f in counter.carried]
        hidden_property(obj, CARRIED, "App::PropertyStringList")
        setattr(obj, CARRIED, carried)
        overhanging = overhangs_of(obj.Base[0], obj.Document)
        setattr(obj, OVERHANGS, overhanging)
        shapes = [result.fins]
        # Each warning says which fin it is about, the main or the counter fin.
        warnings = [translate("FinSnap", "Main fin: %s") % w for w in result.warnings]
        if counter is not None:
            shapes.append(counter.fins)
            warnings += [translate("FinSnap", "Counter fin: %s") % w for w in counter.warnings]
        if overhanging:
            warnings.append(translate("FinSnap", "%d faces of %s overhang flatter than %.0f degrees without fins: %s")
                            % (len(overhanging), obj.Base[0].Label, d.OVERHANG_ANGLE, ", ".join(overhanging)))

        if p.connection == d.CONNECTION_MERGED:
            obj.Shape = geometry.merged(part, *shapes)
        else:
            obj.Shape = Part.makeCompound(shapes)
        obj.ResultHeight = result.height
        obj.ResultThickness = result.thickness
        obj.ResultFinCount = len(result.positions)
        obj.Warnings = warnings
        for warning in warnings:
            App.Console.PrintWarning("FinSnap: %s\n" % warning)

    def onDocumentRestored(self, obj):  # noqa: N802 - FreeCAD API
        obj.Proxy = self
        if OVERHANGS not in obj.PropertiesList:
            add_overhangs(obj)
        # A parameter added in a later version starts with its built-in value,
        # so fins saved before it keep their shape.
        built_in = FinParams()
        for prop in PROPERTIES:
            if prop.name not in obj.PropertiesList:
                add_property(obj, prop, getattr(built_in, prop.field))
        # A file saved by an older version knows fewer choices; offer the
        # current ones and keep the value.
        for prop in PROPERTIES:
            if prop.choices and list(prop.choices) != obj.getEnumerationsOfProperty(prop.name):
                value = getattr(obj, prop.name)
                setattr(obj, prop.name, list(prop.choices))
                setattr(obj, prop.name, value)

    def dumps(self):
        return None

    def loads(self, state):
        return None


def is_fins(obj):
    """Whether `obj` is a FinSnap object."""
    return isinstance(getattr(obj, "Proxy", None), FinSnapFeature)


def face_name_of(shape, face):
    for number, candidate in enumerate(shape.Faces, 1):
        if candidate.isSame(face):
            return face_name(number)
    return None


def add_counter(obj, base=None, face_ref=None):
    """Give an existing FinSnap object a counter fin.

    face_ref is the name of the face ("Face3"). Without it, the face of the
    same part that leans the other way is searched. Returns the face name, or
    None if there is no such face.
    """
    if face_ref is None:
        base = obj.Base[0]
        shape, face = _face(obj.Base)
        found = geometry.opposite_face(shape, face)
        if found is None:
            return None
        face_ref = face_name_of(shape, found)
    obj.CounterFace = (base, [face_ref])
    return face_ref


def create(base, face_ref, counter=None):
    """A new FinSnap object under the face named `face_ref` of `base`. counter: (object, face name) or None."""
    doc = base.Document
    obj = doc.addObject("Part::FeaturePython", TYPE_NAME)
    FinSnapFeature(obj)
    obj.Base = (base, [face_ref])
    if outermost(base) is not base:
        obj.Container = outermost(base)
    if counter:
        obj.CounterFace = (counter[0], [counter[1]])
    # Fins already on this part now see one more carried face.
    for other in doc.Objects:
        if other is not obj and is_fins(other) and other.Base and other.Base[0] is base:
            other.touch()
    return obj


def fins_of(owner, document):
    """The FinSnap objects of the part whose outermost container is `owner`."""
    return [obj for obj in document.Objects
            if is_fins(obj) and obj.Base and outermost(obj.Base[0]) is owner]


def hidden_property(obj, name, kind):
    """Add the hidden result property `name` to `obj` if it has none yet."""
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name, GROUP_RESULT, "", 1)
        obj.setEditorMode(name, EDITOR_HIDDEN)


def is_laid_flat(obj):
    return bool(getattr(obj, LAID_FLAT, False))


def keep_laid_flat(obj, change):
    """Move the fins `obj` by the placement change their part makes when it is
    laid flat, and keep that shape until the part is moved again.

    INPUTS this has to withstand:
      fins of a standing part               ->  moved with it, marked, not rebuilt
      fins already laid flat                ->  moved once more, still marked
    """
    hidden_property(obj, LAID_FLAT, "App::PropertyBool")
    hidden_property(obj, LAID_FLAT_AT, "App::PropertyPlacement")
    owner = outermost(obj.Base[0])
    shape = obj.Shape.copy()
    shape.Placement = change.multiply(shape.Placement)
    setattr(obj, LAID_FLAT_AT, change.multiply(owner.Placement))
    setattr(obj, LAID_FLAT, True)
    obj.Shape = shape


def still_laid_flat(obj):
    """Whether the part of the fins `obj` still lies where it was laid flat. Moved
    since, by Stand on edge or by hand, the fins are rebuilt: the marker is cleared.

    INPUTS this has to withstand:
      fins never laid flat                  ->  False
      part where it was laid flat           ->  True, marker kept
      part moved since (stood again, or its
        placement edited)                   ->  False, marker cleared
    """
    if not is_laid_flat(obj):
        return False
    if outermost(obj.Base[0]).Placement.isSame(getattr(obj, LAID_FLAT_AT), d.TOLERANCE):
        return True
    setattr(obj, LAID_FLAT, False)
    return False
