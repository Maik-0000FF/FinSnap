# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

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
from . import orient
from . import overhang
from . import presets
from .i18n import QT_TRANSLATE_NOOP, translate
from .params import FinParams
from .shapes import face_name, global_shape, moved, outermost

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
# Fins removed by hand, by their number from the left seen from outside, for
# the main fin and the counter fin; and which fin each solid of the shape is,
# "main:2" or "counter:1", so a face picked in the 3D view finds its fin.
REMOVED = {"main": "RemovedFins", "counter": "RemovedCounterFins"}
FIN_TAGS = "FinTags"
TAG_SEPARATOR = ":"
# How many fins the face was planned for at the last build.
PLANNED = {"main": "PlannedFins", "counter": "PlannedCounterFins"}
# Fins moved along the face and fins with a height of their own, by number: mm.
SHIFTS = {"main": "FinShifts", "counter": "CounterFinShifts"}
HEIGHTS = {"main": "FinHeights", "counter": "CounterFinHeights"}
# How many fins the face was planned for when a fin of it was changed by hand,
# and the name earlier versions kept it under, when fins could only be removed.
EDITED_OF = {"main": "EditedFinsOf", "counter": "EditedCounterFinsOf"}
REMOVED_OF = {"main": "RemovedFinsOf", "counter": "RemovedCounterFinsOf"}
NOTE_EDITS_DROPPED = QT_TRANSLATE_NOOP(
    "FinSnap", "The number of fins changed, so the fins changed by hand are as planned again: removed fins "
    "are back, moved fins and fin heights of their own are undone.")
MAIN, COUNTER = "main", "counter"
# Said when a single fin is to be removed from fins merged into the part.
NOTE_MERGED_SINGLE = QT_TRANSLATE_NOOP(
    "FinSnap", "Single fins can be removed with the separate connection only; merged into the part they "
    "have no body of their own. To delete all of them, select the fins in the tree.")
# Said when a face chosen for the counter fin cannot take fins; %s says why.
NOTE_NO_COUNTER_ON_FACE = QT_TRANSLATE_NOOP("FinSnap", "No counter fin on this face: %s")
# A counter fin under the side of a cylinder or tube would stay under its
# lowest line and move only by turning the part, the main fin with it.
COUNTER_ROUND_SIDE = QT_TRANSLATE_NOOP(
    "FinSnap", "the counter fin goes under a flat face, not under the side of a cylinder or tube")
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

# step: how far one turn of the mouse wheel or an arrow press changes the field;
# None keeps the default of the field, one unit.
Prop = namedtuple("Prop", "name kind group label tip field choices step", defaults=(None,))

# Steps of the fields, each sized to what the value is: hundredths for the
# print profile and the gap, whole millimetres only for the fin height.
# STEP_LAYER: heights on the layer grid step by the layer height entered; a
# value already on the grid steps to the next layer, and params rounds any
# other value onto it.
STEP_PROFILE = 0.05
STEP_CLEARANCE = 0.01
STEP_LAYER = "layer height"
STEP_HALF = 0.5
STEP_THICKNESS = 0.1
STEP_HEIGHT = 1.0
STEP_FACE_LENGTH = 5.0
STEP_RATIO = 0.05

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
         "nozzle_diameter", None, STEP_PROFILE),
    Prop("BeadWidth", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "Bead width"),
         QT_TRANSLATE_NOOP("App::Property", "Extrusion width of the outer perimeter"),
         "bead_width", None, STEP_PROFILE),
    Prop("LayerHeight", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "Layer height"),
         QT_TRANSLATE_NOOP("App::Property", "Layer height of the print profile"),
         "layer_height", None, STEP_PROFILE),
    Prop("FirstLayerHeight", LENGTH, GROUP_SLICER,
         QT_TRANSLATE_NOOP("FinSnap", "First layer height"),
         QT_TRANSLATE_NOOP("App::Property", "Height of the first layer"),
         "first_layer_height", None, STEP_PROFILE),
    Prop("Connection", CHOICE, GROUP_CONNECTION,
         QT_TRANSLATE_NOOP("FinSnap", "Connection"),
         QT_TRANSLATE_NOOP("App::Property",
                           "separate: fins are their own object and only touch the part; "
                           "merged: fins and part become one body"),
         "connection", d.CONNECTIONS),
    Prop("Gap", LENGTH, GROUP_CONNECTION,
         QT_TRANSLATE_NOOP("FinSnap", "Gap"),
         QT_TRANSLATE_NOOP("App::Property", "Clearance between fin and face, along the face normal"),
         "gap", None, STEP_PROFILE),
    Prop("TineClearance", LENGTH, GROUP_CONNECTION,
         QT_TRANSLATE_NOOP("FinSnap", "Tine clearance"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Distance between the end of a tine and the face, along the face normal; 0 = the "
                           "tine touches the face. More leaves fainter marks, too much and the tine does not "
                           "hold: find the value by a test print."),
         "tine_clearance", None, STEP_CLEARANCE),
    Prop("TineSpacing", LENGTH, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine spacing"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Vertical distance between tines, at least the tine height plus one layer"),
         "tine_spacing", None, STEP_LAYER),
    Prop("TineFirst", LENGTH, GROUP_TINES,
         QT_TRANSLATE_NOOP("FinSnap", "Tine first"),
         QT_TRANSLATE_NOOP("App::Property", "Height of the lowest tine above the bed, 0 = on the top of the foot"),
         "tine_first", None, STEP_LAYER),
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
         "fin_thickness", None, STEP_THICKNESS),
    Prop("FinHeight", LENGTH, GROUP_FIN,
         QT_TRANSLATE_NOOP("FinSnap", "Fin height"),
         QT_TRANSLATE_NOOP("App::Property",
                           "Height of the fins, 0 = top of the highest tine. A lower value leaves out the "
                           "tines above it; the fins reach at most to just below the top of the face."),
         "fin_height", None, STEP_HEIGHT),
    Prop("FinPlateau", LENGTH, GROUP_FIN,
         QT_TRANSLATE_NOOP("FinSnap", "Top width"),
         QT_TRANSLATE_NOOP("App::Property", "Width of the flat top of a fin"),
         "fin_plateau", None, STEP_HALF),
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
         "end_inset", None, STEP_HALF),
    Prop("FaceLengthPerFin", LENGTH, GROUP_PLACEMENT,
         QT_TRANSLATE_NOOP("FinSnap", "Face length per fin"),
         QT_TRANSLATE_NOOP("App::Property", "Automatic placement: one fin per this much face length"),
         "face_length_per_fin", None, STEP_FACE_LENGTH),
    Prop("FootShape", CHOICE, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot shape"),
         QT_TRANSLATE_NOOP("App::Property", "Shape of the foot on the bed"),
         "foot_shape", d.FOOT_SHAPES),
    Prop("FootThickness", LENGTH, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot thickness"),
         QT_TRANSLATE_NOOP("App::Property", "Height of the foot, rounded to whole layers"),
         "foot_thickness", None, STEP_LAYER),
    Prop("FootOverhang", LENGTH, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot overhang"),
         QT_TRANSLATE_NOOP("App::Property", "How far the foot reaches past the outer end of the fin"),
         "foot_overhang", None, STEP_HALF),
    Prop("FootWidthRatio", FLOAT, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot width ratio"),
         QT_TRANSLATE_NOOP("App::Property", "Foot width as a share of its length"),
         "foot_width_ratio", None, STEP_RATIO),
    Prop("FootHalfWidth", LENGTH, GROUP_FOOT,
         QT_TRANSLATE_NOOP("FinSnap", "Foot half width"),
         QT_TRANSLATE_NOOP("App::Property", "Half width of the foot, 0 = from FootWidthRatio"),
         "foot_half_width", None, STEP_HALF),
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
    Depends("TineClearance", "Connection", (d.CONNECTION_SEPARATE,),
            QT_TRANSLATE_NOOP("FinSnap", "Not used with fins merged into the part: they need their tines on the "
                              "face, or they would be loose bodies.")),
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


# Builds of one side kept during a drag; beyond these the oldest goes.
REUSE_KEPT = 8


class FinSnapFeature:
    def __init__(self, obj):
        obj.Proxy = self
        add_properties(obj)

    def during_drag(self, name, make):
        """make(), once while a drag in the task panel lasts, kept as `name`;
        every time otherwise. What does not change while one fin is dragged."""
        kept = getattr(self, "reuse", None)
        if kept is None:
            return make()
        if name not in kept:
            kept[name] = make()
        return kept[name]

    def side_builder(self, obj, which):
        """builder(obj, which); while a drag in the task panel lasts, with the
        same part throughout, and taking a result built before with the same
        changes by hand, keeping each new one. The panel sets `reuse` to {}
        then and back to None after. During a drag only the changes by hand
        of the dragged fin differ from step to step, so the trial build of a
        step serves its real build, and the other side is built once. The
        part is kept as well: the faces of a result belong to it."""
        if getattr(self, "reuse", None) is None:
            return builder(obj, which)
        found, side = self.during_drag(which, lambda: (builder(obj, which), {}))
        if found is None:
            return None
        part, build_fn = found

        def build(left, shifts, heights):
            key = edits_key(left, shifts, heights)
            if key not in side:
                # The latest few are enough; a long drag would hold every step.
                while len(side) >= REUSE_KEPT:
                    side.pop(next(iter(side)))
                side[key] = build_fn(left, shifts, heights)
            return side[key]
        return part, build

    def execute(self, obj):
        # The last build, for the arrows of an open task panel only: a failed
        # build leaves none, and without a panel none is kept.
        self.results = {}
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
            notes = []
            part, build_main = self.side_builder(obj, MAIN)
            result = build_keeping_edits(obj, MAIN, build_main, notes)
            counter = None
            if obj.CounterFace:
                counter_side = self.side_builder(obj, COUNTER)
                if counter_side is None:
                    # Under the side of a cylinder or tube: left out, the main fin stays.
                    notes.append(translate("FinSnap", "Counter fin: %s") % translate("FinSnap", COUNTER_ROUND_SIDE))
                else:
                    counter_part, build_counter = counter_side
                    counter = build_keeping_edits(obj, COUNTER, build_counter, notes)
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
        if getattr(self, "editing", False):
            self.results = {MAIN: result, COUNTER: counter}
        for which, built in ((MAIN, result), (COUNTER, counter)):
            if built is not None:
                hidden_property(obj, PLANNED[which], "App::PropertyInteger")
                setattr(obj, PLANNED[which], built.planned)
        # The faces the fins carry stay the same while one fin is dragged.
        overhanging = self.during_drag(OVERHANGS, lambda: overhangs_of(obj.Base[0], obj.Document))
        setattr(obj, OVERHANGS, overhanging)
        shapes = [result.fins]
        # Each warning says which fin it is about, the main or the counter fin.
        warnings = [translate("FinSnap", "Main fin: %s") % w for w in result.warnings]
        if counter is not None:
            shapes.append(counter.fins)
            warnings += [translate("FinSnap", "Counter fin: %s") % w for w in counter.warnings]
        warnings += notes
        if overhanging:
            warnings.append(translate("FinSnap", "%d faces of %s overhang flatter than %.0f degrees without fins: %s")
                            % (len(overhanging), obj.Base[0].Label, d.OVERHANG_ANGLE, ", ".join(overhanging)))

        tags = [fin_tag(MAIN, n) for n in result.numbers]
        if counter is not None:
            tags += [fin_tag(COUNTER, n) for n in counter.numbers]
        if p.connection == d.CONNECTION_MERGED:
            obj.Shape = geometry.merged(part, *shapes)
            tags = []
        else:
            obj.Shape = Part.makeCompound(shapes)
        # One solid per fin, in the order built; otherwise picking cannot tell them apart.
        hidden_property(obj, FIN_TAGS, "App::PropertyStringList")
        setattr(obj, FIN_TAGS, tags if len(tags) == len(obj.Shape.Solids) else [])
        obj.ResultHeight = result.height
        obj.ResultThickness = result.thickness
        obj.ResultFinCount = len(result.positions)
        # Into the report view only when they changed: every rebuild, as at
        # each step of a drag, would repeat them there otherwise. Warnings
        # keeps them all the time.
        if list(obj.Warnings) != warnings:
            for warning in warnings:
                App.Console.PrintWarning("FinSnap: %s\n" % warning)
        obj.Warnings = warnings

    def onDocumentRestored(self, obj):  # noqa: N802 - FreeCAD API
        obj.Proxy = self
        if OVERHANGS not in obj.PropertiesList:
            add_overhangs(obj)
        # Saved when fins could only be removed: the count is taken over.
        for which, old in REMOVED_OF.items():
            if old in obj.PropertiesList:
                if EDITED_OF[which] not in obj.PropertiesList:
                    hidden_property(obj, EDITED_OF[which], "App::PropertyInteger")
                    setattr(obj, EDITED_OF[which], getattr(obj, old))
                obj.removeProperty(old)
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


def check_counter_face(face):
    """Refuse `face` for a counter fin where it is the side of a cylinder or
    tube: its fin would stay under the lowest line and move only by turning
    the part, the main fin with it. FinError then."""
    if orient.is_round_side(face):
        raise geometry.FinError(translate("FinSnap", COUNTER_ROUND_SIDE))


def add_counter(obj, base=None, face_ref=None):
    """Give an existing FinSnap object a counter fin.

    face_ref is the name of the face ("Face3"). Without it, the face of the
    same part that leans the other way is searched. Returns the face name, or
    None if there is no such face.

    INPUTS this has to withstand:
      no face, one leans the other way         ->  that face, counter fin set
      no face, none leans the other way        ->  None, nothing changed
      a face that leans over the bed           ->  that face, counter fin set
      a face lying flat, facing up or sideways,
        or not planar, such as one still
        selected from standing the part        ->  FinError saying why, nothing changed
    """
    if face_ref is None:
        base = obj.Base[0]
        shape, face = _face(obj.Base)
        found = geometry.opposite_face(shape, face)
        if found is None:
            return None
        face_ref = face_name_of(shape, found)
    else:
        # A face chosen by hand has to take fins, or the next build fails.
        face = _face((base, [face_ref]))
        # Said before the face is asked to take fins, which a bore or a cut
        # side would refuse for a reason of its own.
        check_counter_face(face[1])
        geometry.frame_of(*face)
    # Changes by hand to a counter fin on another face would name other fins.
    if obj.CounterFace != (base, [face_ref]):
        reset_fins(obj, COUNTER)
    obj.CounterFace = (base, [face_ref])
    return face_ref


def create(base, face_ref, counter=None):
    """A new FinSnap object under the face named `face_ref` of `base`. counter: (object, face name) or None.
    A counter face on the side of a cylinder or tube: FinError, nothing made."""
    if counter:
        check_counter_face(_face((counter[0], [counter[1]]))[1])
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
      fins under a round side, part turned
        about it by hand                    ->  the turn goes with the placement laid
                                                back, so the fin keeps no shift
    """
    forget_turn(obj)
    hidden_property(obj, LAID_FLAT, "App::PropertyBool")
    hidden_property(obj, LAID_FLAT_AT, "App::PropertyPlacement")
    owner = outermost(obj.Base[0])
    setattr(obj, LAID_FLAT_AT, change.multiply(owner.Placement))
    setattr(obj, LAID_FLAT, True)
    obj.Shape = moved(obj.Shape, change)


def laid_flat_marks(owner, document):
    """The fins of `owner` laid flat, by name, with the place their part lay
    at and the shape they kept, for put_back_laid_flat()."""
    return [(obj.Name, App.Placement(getattr(obj, LAID_FLAT_AT)), obj.Shape.copy())
            for obj in fins_of(owner, document) if is_laid_flat(obj)]


def put_back_laid_flat(document, marks):
    """Mark the fins in `marks`, from laid_flat_marks(), laid flat again with
    the shapes they kept, once their part lies where it did: a command that
    stood the part and was cancelled leaves them as they were, rather than
    rebuilt for a part they no longer stand under. Fins deleted since are
    passed over."""
    for name, laid_at, shape in marks:
        obj = document.getObject(name)
        if obj is None:
            continue
        setattr(obj, LAID_FLAT_AT, laid_at)
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


def builder(obj, which):
    """How the fins of `which` are built: (the global shape of the part they
    stand under, a function of (left_out, shifts, heights) returning the
    FinResult), or None for a counter fin not added. The faces in the result
    belong to that shape. execute() builds with the changes by hand stored;
    the task panel tries changes with it before they are made."""
    p = params_of(obj)
    if which == MAIN:
        part, face = _face(obj.Base)
        return part, lambda left, shifts, heights: geometry.build(part, face, p, left_out=left, shifts=shifts,
                                                                  heights=heights)
    if not obj.CounterFace:
        return None
    part, face = _face(obj.CounterFace)
    if orient.is_round_side(face):
        # Its fin would stay under the lowest line and could move only by
        # turning the part, which turns the main fin away as well: left out,
        # as a counter fin not added, with a note (execute()).
        return None
    return part, lambda left, shifts, heights: geometry.build(
        part, face, p, tine_count=p.counter_tine_count or None, left_out=left, shifts=shifts, heights=heights)


def build_keeping_edits(obj, which, build_fn, notes):
    """Build the fins of `which` with the changes made by hand, as long as the
    face is planned for as many fins as when they were made.

    build_fn(left_out, shifts, heights) builds the fins. The numbers of the fins
    changed by hand count along the face; with another count, from another
    placement or a longer face, they would name other fins, so every change by
    hand is dropped and a note says so.

    INPUTS this has to withstand:
      nothing changed by hand               ->  built as usual
      fins removed, moved or set to a
        height, same count                  ->  built with those changes
      changes made, count changed           ->  built as planned, changes dropped, note
      every fin removed, same count         ->  FinError: every fin is removed
      every fin removed, count changed      ->  built as planned, changes dropped, note
      changes made, count they were made
        for unknown                         ->  built with them; a FinError passed on
      FinError for any other reason         ->  passed on
    """
    left, shifts, heights = edits(obj, which)
    changed = bool(left or shifts or heights)
    made_for = getattr(obj, EDITED_OF[which], None)
    result, failure = None, None
    try:
        result = build_fn(left, shifts, heights)
        planned = result.planned
    except geometry.FinError as error:
        failure, planned = error, getattr(error, "planned", None)
    stale = changed and made_for is not None and planned is not None and planned != made_for
    if not stale:
        if failure is not None:
            raise failure
        return result
    reset_fins(obj, which)
    notes.append(translate("FinSnap", NOTE_EDITS_DROPPED))
    return build_fn((), {}, {})


def fin_at(obj, sub):
    """(MAIN or COUNTER, number) of the fin a picked sub-element `sub` ("Face12")
    of `obj` belongs to, or None.

    INPUTS this has to withstand:
      face or edge of one fin               ->  that fin
      fins merged into the part             ->  None: the fins are no solids of their own
      name the shape does not have          ->  None
    """
    tags = list(getattr(obj, FIN_TAGS, []))
    try:
        element = obj.Shape.getElement(sub)
    except (ValueError, IndexError, Part.OCCError):
        return None
    for tag, solid in zip(tags, obj.Shape.Solids):
        if any(element.isSame(candidate) for candidate in solid.Faces + solid.Edges):
            return tag_fin(tag)
    return None


def fin_tag(which, number):
    """The tag of fin `number` of `which` among FIN_TAGS: "main:2"."""
    return "%s%s%d" % (which, TAG_SEPARATOR, number)


def tag_fin(tag):
    """(MAIN or COUNTER, number) of a tag among FIN_TAGS."""
    which, number = tag.split(TAG_SEPARATOR)
    return which, int(number)


def fin_faces(obj, which, number):
    """The indices among the faces of `obj`, from 0, of fin `number` of
    `which`; empty for a fin not built, or for fins merged into the part,
    which have no solids of their own."""
    tags = list(getattr(obj, FIN_TAGS, []))
    tag = fin_tag(which, number)
    if tag not in tags:
        return []
    own = obj.Shape.Solids[tags.index(tag)].Faces
    return [index for index, candidate in enumerate(obj.Shape.Faces)
            if any(candidate.isSame(face) for face in own)]


def fin_face(obj, which, number):
    """The name of a face of fin `number` of `which` ("Face12"), to select the
    fin by; None where fin_faces() finds none."""
    faces = fin_faces(obj, which, number)
    # Face names count from 1.
    return face_name(faces[0] + 1) if faces else None


def edits(obj, which):
    """The changes by hand to the fins of `which` (MAIN or COUNTER): the numbers
    removed, and by number the shift along the face and the own height, in mm."""
    def numbers_to_mm(name):
        return {int(number): float(mm) for number, mm in dict(getattr(obj, name, {})).items()}
    return (list(getattr(obj, REMOVED[which], [])), numbers_to_mm(SHIFTS[which]),
            numbers_to_mm(HEIGHTS[which]))


def removed(obj, which):
    """Numbers of the fins of `which` removed by hand."""
    return edits(obj, which)[0]


def _edited(obj, which):
    """Note how many fins the face was planned for when a change by hand was made."""
    hidden_property(obj, EDITED_OF[which], "App::PropertyInteger")
    setattr(obj, EDITED_OF[which], getattr(obj, PLANNED[which], 0))


def remove_fin(obj, which, number):
    """Leave fin `number` of `which` out from now on."""
    hidden_property(obj, REMOVED[which], "App::PropertyIntegerList")
    setattr(obj, REMOVED[which], sorted(set(removed(obj, which)) | {number}))
    _edited(obj, which)


def stored_mm(mm):
    """`mm` as a change by hand is stored: a value tried before and the same
    value stored compare equal."""
    return round(mm, d.LENGTH_DECIMALS)


def edits_key(left, shifts, heights):
    """The changes by hand of one side, as edits() gives them, as a key:
    equal changes, equal key."""
    return tuple(sorted(left)), tuple(sorted(shifts.items())), tuple(sorted(heights.items()))


def _set_mm(obj, name, number, mm):
    hidden_property(obj, name, "App::PropertyMap")
    values = dict(getattr(obj, name))
    if mm is None:
        values.pop(str(number), None)
    else:
        values[str(number)] = repr(stored_mm(mm))
    setattr(obj, name, values)


def shift_fin(obj, which, number, by):
    """Move fin `number` of `which` along the face by `by` mm more (to the right, seen from outside)."""
    set_fin_shift(obj, which, number, edits(obj, which)[1].get(number, 0.0) + by)


def set_fin_shift(obj, which, number, mm):
    """Move fin `number` of `which` `mm` along the face from where it was planned."""
    _set_mm(obj, SHIFTS[which], number, None if abs(mm) < d.TOLERANCE else mm)
    _edited(obj, which)


def set_fin_height(obj, which, number, mm):
    """Give fin `number` of `which` a height of its own, or with None the height of the others again."""
    _set_mm(obj, HEIGHTS[which], number, mm)
    _edited(obj, which)


def turn_part(obj, mm):
    """Turn the part of `obj` about the axis of the round side its main fin
    stands under, so the fin comes to stand `mm` further along the side; see
    geometry.turn_of(). Inside a Body, the whole Body is turned. No turn
    leaves the placement as it is, so nothing is recomputed for it."""
    if abs(mm) < d.TOLERANCE:
        return
    change = geometry.turn_of(round_side(obj), mm)
    owner = outermost(obj.Base[0])
    owner.Placement = change.multiply(owner.Placement)


def on_round_side(obj):
    """Whether the main fin of `obj` stands under the round side of a cylinder or tube."""
    try:
        return orient.is_round_side(round_side(obj))
    except (geometry.FinError, ValueError, Part.OCCError):
        return False


def round_side(obj):
    """The round side of a cylinder or tube the main fin of `obj` stands
    under, as its part stands now."""
    return _face(obj.Base)[1]


def round_shift(obj):
    """How far the part of `obj` was turned about its round side by hand, as
    the shift of its main fin (mm round the side); 0 if not."""
    return edits(obj, MAIN)[1].get(1, 0.0)


def round_turns(owner, document):
    """The fins of `owner` under a round side whose part was turned by hand,
    by name, with how far (mm round the side), for put_back_turns()."""
    turns = {}
    for obj in fins_of(owner, document):
        mm = round_shift(obj)
        if mm and on_round_side(obj):
            turns[obj.Name] = mm
    return turns


def put_back_turns(document, turns):
    """Note again how far the part of the fins in `turns`, from round_turns(),
    was turned, once it stands as it did then: the placement put back holds
    the turn itself, so the part is not turned again. Fins deleted since are
    passed over. Only the shift is written back: the count of fins it was
    made for stays as it was noted then."""
    for name, mm in turns.items():
        obj = document.getObject(name)
        if obj is not None:
            _set_mm(obj, SHIFTS[MAIN], 1, mm)


def forget_turn(obj):
    """Drop how far the part of `obj` was turned about its round side, once
    the part is laid flat or stood anew: the turn went with its placement,
    and the fin starts from where it stands then. Only the shift goes: the
    count of fins it was made for stays, as it does in put_back_turns()."""
    if round_shift(obj) and on_round_side(obj):
        _set_mm(obj, SHIFTS[MAIN], 1, None)


def set_round_shift(obj, mm):
    """Turn the part so its main fin stands `mm` round its round side from
    where it was stood, and keep that as the shift of the fin."""
    turn_part(obj, mm - round_shift(obj))
    set_fin_shift(obj, MAIN, 1, mm)


def reset_fins(obj, which=None):
    """Undo every change by hand: removed fins come back, moved fins and fins
    with a height of their own return to where and how high they were planned.
    Both fins without `which`."""
    for one in (which,) if which else (MAIN, COUNTER):
        if REMOVED[one] in obj.PropertiesList:
            setattr(obj, REMOVED[one], [])
        for name in (SHIFTS[one], HEIGHTS[one]):
            if name in obj.PropertiesList:
                setattr(obj, name, {})


def remove_fins(obj, fins):
    """Leave out the fins in `fins`, as (MAIN or COUNTER, number). True when
    that would leave no main fin: then nothing is changed, and the caller
    deletes the fins object instead.

    INPUTS this has to withstand (fins built: main 1, 2, 3 and counter 1):
      main 2                                ->  main 2 left out, False
      main 1, 2, 3                          ->  nothing changed, True
      main 1, 2, 3 and counter 1            ->  nothing changed, True
      counter 1, the only counter fin       ->  counter fin dropped, False
      main 2 and counter 1                  ->  main 2 left out, counter fin dropped, False
      a fin twice                           ->  as once
      empty                                 ->  nothing changed, False
    """
    picked = set(fins)
    built = {MAIN: set(), COUNTER: set()}
    for tag in getattr(obj, FIN_TAGS, []):
        which, number = tag_fin(tag)
        built[which].add(number)
    gone = {which: {n for w, n in picked if w == which} for which in built}
    if built[MAIN] and built[MAIN] <= gone[MAIN]:
        return True
    if built[COUNTER] and built[COUNTER] <= gone[COUNTER]:
        remove_counter(obj)
        gone[COUNTER] = set()
    for which, numbers in gone.items():
        for number in sorted(numbers):
            remove_fin(obj, which, number)
    return False


def prepare_delete(obj):
    """Before the fins object `obj` is deleted: the last fins of a part stood
    on an edge lay it flat again; other fins of it are built anew."""
    if not obj.Base:
        return
    owner = outermost(obj.Base[0])
    others = [o for o in fins_of(owner, obj.Document) if o is not obj]
    if not others:
        orient.lay_back(owner)
    for other in others:
        other.touch()


def remove_counter(obj):
    """Drop the counter fin, and its changes by hand with it."""
    obj.CounterFace = None
    reset_fins(obj, COUNTER)
