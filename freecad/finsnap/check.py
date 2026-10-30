# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""A check of a part in the tree: what Check stability or Check part found.

One object for each part and kind of check; checking again fills the same
object. It keeps what was found, the note said and what the 3D view shows,
so it shows again once the document is opened. It links the part and its
fins, so FreeCAD touches it when they change: its recompute then only marks
it out of date, as checking again takes seconds on a large part. A double
click checks again (taskpanel.ViewProviderCheck).

INPUTS this has to withstand (record()):
  a part checked for the first time     ->  a new object, its result kept, up to date
  the same part checked again, the same
    kind                                ->  the same object, its result replaced
  the same part, the other kind         ->  an object of its own
  nothing of the part on the bed        ->  the note kept, nothing to show
  the part, its place or its fins
    changed after                       ->  marked out of date on the next recompute
  an object saved by an older version,
    without the properties added since  ->  they are added, then filled
"""

import FreeCAD as App
import Part

from . import limits
from .i18n import QT_TRANSLATE_NOOP, translate
from .shapes import outermost

TYPE_NAME = "FinSnapCheck"
STABILITY, PART = "stability", "part"
LABELS = {STABILITY: QT_TRANSLATE_NOOP("FinSnap", "Stability check of %s"),
          PART: QT_TRANSLATE_NOOP("FinSnap", "Part check of %s")}
GROUP = QT_TRANSLATE_NOOP("App::Property", "Check")
GROUP_SHOWN = QT_TRANSLATE_NOOP("App::Property", "Shown")
# Shown read-only in the property view, or not at all.
EDITOR_READ_ONLY = 1
EDITOR_HIDDEN = 2
# The properties of a check, as (name, type, group, tooltip, editor mode).
PROPERTIES = (
    # Global links, as the part may lie in a body or a part container.
    ("Part", "App::PropertyLinkGlobal", GROUP, QT_TRANSLATE_NOOP("App::Property", "The part checked"),
     EDITOR_READ_ONLY),
    ("Fins", "App::PropertyLinkListGlobal", GROUP,
     QT_TRANSLATE_NOOP("App::Property", "The fins of the part checked"), EDITOR_READ_ONLY),
    # The outermost container of the part, so moving it marks the check out
    # of date, as it rebuilds the fins.
    ("Container", "App::PropertyLinkGlobal", GROUP, "", EDITOR_HIDDEN),
    ("Kind", "App::PropertyString", GROUP, QT_TRANSLATE_NOOP("App::Property", "What was checked"),
     EDITOR_HIDDEN),
    ("Result", "App::PropertyString", GROUP, QT_TRANSLATE_NOOP("App::Property", "What the check found"),
     EDITOR_READ_ONLY),
    ("OutOfDate", "App::PropertyBool", GROUP,
     QT_TRANSLATE_NOOP("App::Property", "The part, its place or its fins changed since: double-click to check "
                                        "again"), EDITOR_READ_ONLY),
    # The level of the stability found, STANDS, CLOSE or TIPS, whose colour
    # the plumb line and the layer cut out show.
    ("Level", "App::PropertyString", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Tips", "App::PropertyBool", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Layer", "App::PropertyInteger", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Height", "App::PropertyFloat", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Margin", "App::PropertyFloat", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Centre", "App::PropertyVector", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Foot", "App::PropertyVector", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Footprint", "App::PropertyVectorList", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("ProfileHeights", "App::PropertyFloatList", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("ProfileMargins", "App::PropertyFloatList", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("Cut", "Part::PropertyPartShape", GROUP_SHOWN, "", EDITOR_HIDDEN),
    # The faces that overhang without fins, critical ones and those too flat
    # to print, see limits.py.
    ("Overhangs", "Part::PropertyPartShape", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("UnprintableOverhangs", "Part::PropertyPartShape", GROUP_SHOWN, "", EDITOR_HIDDEN),
    # The tipping margin the check rated by, which the colours by height show.
    ("TippingMargin", "App::PropertyFloat", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("IslandLayers", "Part::PropertyPartShape", GROUP_SHOWN, "", EDITOR_HIDDEN),
    ("IslandsUncut", "App::PropertyVectorList", GROUP_SHOWN, "", EDITOR_HIDDEN),
)
# What the view provider draws from: a change of one shows the check anew.
OUT_OF_DATE = "OutOfDate"
SHOWN = tuple(name for name, _, group, _, _ in PROPERTIES if group == GROUP_SHOWN) + (OUT_OF_DATE,)


class CheckFeature:
    """The proxy of a check. Its recompute, which FreeCAD runs once the part
    or its fins changed, marks it out of date and checks nothing."""

    def __init__(self, obj):
        obj.Proxy = self
        add_properties(obj)

    def execute(self, obj):
        obj.OutOfDate = True

    def dumps(self):
        return None

    def loads(self, state):
        return None


def add_properties(obj):
    """Add those of PROPERTIES `obj` does not have yet."""
    for name, kind, group, tip, mode in PROPERTIES:
        if name not in obj.PropertiesList:
            obj.addProperty(kind, name, group, tip)
            obj.setEditorMode(name, mode)


def outdate(part_obj):
    """Mark the checks of `part_obj` out of date: its fins were built anew,
    perhaps new ones, which the checks do not link."""
    for kind in (STABILITY, PART):
        found = find(part_obj, kind)
        if found is not None and not found.OutOfDate:
            found.OutOfDate = True
            # Set by hand, not by a recompute of the check, which then needs none.
            found.purgeTouched()


def is_check(obj):
    return getattr(obj, "TypeId", None) == "App::FeaturePython" and isinstance(getattr(obj, "Proxy", None),
                                                                               CheckFeature)


def find(part_obj, kind):
    """The check of `kind` of `part_obj`, None if there is none yet."""
    return next((obj for obj in part_obj.Document.Objects
                 if is_check(obj) and obj.Part is part_obj and obj.Kind == kind), None)


def record(part_obj, fins, kind, level, note, shown, cut=None, overhangs=(), islands=()):
    """Keep what a check of `kind` of `part_obj`, with its fins `fins`, found
    in its object, made if there is none yet: `level`, that of its
    stability, and the `note` said; `shown`, the stability.Stability whose
    plumb line shows, or None; `cut`, the layer cut out of the part at it;
    and for a check of the part, `overhangs`, the faces that overhang without
    fins, as (face, level) pairs, and `islands`. The limits of the
    preferences are those it was checked by, just before. Returns the
    object, up to date."""
    obj = find(part_obj, kind)
    if obj is not None:
        add_properties(obj)
        # Shows nothing while it is filled, so it is drawn once, at the end.
        obj.OutOfDate = True
    if obj is None:
        obj = part_obj.Document.addObject("App::FeaturePython", TYPE_NAME)
        CheckFeature(obj)
        obj.Part = part_obj
        obj.Kind = kind
    # Set each time: the part may have moved into a container, or out of one.
    owner = outermost(part_obj)
    obj.Container = owner if owner is not part_obj else None
    obj.Label = translate("FinSnap", LABELS[kind]) % part_obj.Label
    obj.Fins = list(fins)
    obj.Result = note
    obj.Level = level
    obj.Tips = bool(shown and shown.tips)
    obj.Layer = shown.layer if shown else 0
    obj.Height = shown.height if shown else 0.0
    obj.Margin = shown.margin if shown else 0.0
    obj.Centre = shown.centre if shown else App.Vector()
    obj.Foot = shown.foot if shown else App.Vector()
    obj.Footprint = list(shown.footprint) if shown else []
    obj.ProfileHeights = [height for height, _ in shown.profile] if shown else []
    obj.ProfileMargins = [margin for _, margin in shown.profile] if shown else []
    obj.Cut = cut if cut is not None else Part.Shape()
    for name, chosen in (("Overhangs", limits.CRITICAL), ("UnprintableOverhangs", limits.UNPRINTABLE)):
        faces = [face for face, level in overhangs if level == chosen]
        setattr(obj, name, Part.makeCompound(faces) if faces else Part.Shape())
    obj.TippingMargin = limits.current().tipping_margin
    layers = [island.first for island in islands if island.first is not None]
    obj.IslandLayers = Part.makeCompound(layers) if layers else Part.Shape()
    obj.IslandsUncut = [island.point for island in islands if island.first is None]
    obj.OutOfDate = False
    # Filled by hand, not by a recompute: FreeCAD would take that for the part
    # having changed.
    obj.purgeTouched()
    return obj
