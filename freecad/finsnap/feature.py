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
from .i18n import QT_TRANSLATE_NOOP
from .params import FinParams
from .shapes import global_shape, outermost

TYPE_NAME = "FinSnap"

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
        "breaks off cleanly. Merged prints fins and part as one body."),
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
    "FootHalfWidth": "J",
}

# Labels for the values of enumerations, as the task panel shows them.
CHOICE_LABELS = {
    d.CONNECTION_SEPARATE: QT_TRANSLATE_NOOP("FinSnap", "separate, touching only"),
    d.CONNECTION_MERGED: QT_TRANSLATE_NOOP("FinSnap", "merged into the part"),
    d.PLACEMENT_AUTO: QT_TRANSLATE_NOOP("FinSnap", "automatic"),
    d.PLACEMENT_CENTER: QT_TRANSLATE_NOOP("FinSnap", "one in the centre"),
    d.PLACEMENT_ENDS: QT_TRANSLATE_NOOP("FinSnap", "two at the ends"),
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
    Prop("TineSpacing", LENGTH, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine spacing"),
         QT_TRANSLATE_NOOP("App::Property", "Vertical distance between tines"),
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
         QT_TRANSLATE_NOOP("App::Property", "Height of the fins, 0 = top of the highest tine"),
         "fin_height", None),
    Prop("FinPlateau", LENGTH, GROUP_FIN,
         QT_TRANSLATE_NOOP("FinSnap", "Fin plateau"),
         QT_TRANSLATE_NOOP("App::Property", "Width of the flat top of a fin"),
         "fin_plateau", None),
    Prop("FinPlacement", CHOICE, GROUP_PLACEMENT,
         QT_TRANSLATE_NOOP("FinSnap", "Fin placement"),
         QT_TRANSLATE_NOOP("App::Property",
                           "auto: by face length; center: one fin; ends: two fins; "
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


def value_of(obj, name):
    value = getattr(obj, name)
    return value.Value if hasattr(value, "Value") else value


def add_properties(obj):
    defaults = FinParams()
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
        obj.addProperty(prop.kind, prop.name, prop.group, prop.tip)
        if prop.choices:
            setattr(obj, prop.name, list(prop.choices))
        setattr(obj, prop.name, getattr(defaults, prop.field))

    results = (("ResultHeight", LENGTH), ("ResultThickness", LENGTH), ("ResultFinCount", INTEGER))
    for name, kind in results:
        obj.addProperty(kind, name, GROUP_RESULT, "", 1)
    obj.addProperty("App::PropertyStringList", "Warnings", GROUP_RESULT, "", 1)


def params_of(obj):
    return FinParams(**{prop.field: value_of(obj, prop.name) for prop in PROPERTIES})


def _face(link):
    part, subs = link
    if not subs:
        raise geometry.FinError("no face selected on %s" % part.Label)
    shape = global_shape(part)
    return shape, shape.getElement(subs[0])


class FinSnapFeature:
    def __init__(self, obj):
        obj.Proxy = self
        add_properties(obj)

    def execute(self, obj):
        if not obj.Base:
            return
        p = params_of(obj)
        part, face = _face(obj.Base)
        result = geometry.build(part, face, p)
        shapes = [result.fins]
        warnings = list(result.warnings)
        if obj.CounterFace:
            counter_part, counter_face = _face(obj.CounterFace)
            counter = geometry.build(counter_part, counter_face, p,
                                     tine_count=p.counter_tine_count or None)
            shapes.append(counter.fins)
            warnings += counter.warnings

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

    def dumps(self):
        return None

    def loads(self, state):
        return None


def face_name_of(shape, face):
    for number, candidate in enumerate(shape.Faces, 1):
        if candidate.isSame(face):
            return "Face%d" % number
    return None


def add_counter(obj, base=None, face_name=None):
    """Give an existing FinSnap object a counter fin.

    Without a face, the face of the same part that leans the other way is
    searched. Returns the face name, or None if there is no such face.
    """
    if face_name is None:
        base = obj.Base[0]
        shape, face = _face(obj.Base)
        found = geometry.opposite_face(shape, face)
        if found is None:
            return None
        face_name = face_name_of(shape, found)
    obj.CounterFace = (base, [face_name])
    return face_name


def create(base, face_name, counter=None):
    """A new FinSnap object under `face_name` of `base`. counter: (object, face name) or None."""
    doc = base.Document
    obj = doc.addObject("Part::FeaturePython", TYPE_NAME)
    FinSnapFeature(obj)
    obj.Base = (base, [face_name])
    if outermost(base) is not base:
        obj.Container = outermost(base)
    if counter:
        obj.CounterFace = (counter[0], [counter[1]])
    return obj
