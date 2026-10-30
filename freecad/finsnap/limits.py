# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The limits the checks rate a part by, in three levels: good, critical
and not printable.

They depend on the printer and the material, not on the fins, so they live
in FreeCAD's user parameters, set on the FinSnap page in Edit > Preferences
(preferences.py), and hold for every part. Angles are measured from the bed,
as PrusaSlicer measures its overhang threshold: 0 degrees is a face lying
flat over the bed, 90 a vertical wall. Cura measures its overhang angle from
the vertical: its value is 90 degrees less.

The tipping margin is the distance of the plumb line from the centre of mass
to the edge of the footprint. Below it the part is at risk of tipping; below
0 it tips, which is physics and no limit to set.

Two strictnesses set all limits at once (STRICTNESS): normal, the built-in
one, allows for what common printers manage and for the grip of the first
layer on the bed; strict counts the geometry alone, and what would need
support is not printable. Limits set by hand match neither: custom. A
strictness is saved by its name alone, so its limits follow the version
running; only custom limits are saved as values.

INPUTS this has to withstand (current()):
  nothing saved                         ->  the built-in Limits(), normal
  STRICT or NORMAL saved                ->  the limits of STRICTNESS, values
                                            saved beside it ignored
  CUSTOM saved, some values with it     ->  those, the rest built-in
  CUSTOM saved, values that do not
    validate together (unprintable
    steeper than critical, past 90, NaN)->  all built-in
  a strictness no longer known          ->  all built-in

INPUTS this has to withstand (Limits.validate()):
  built-in values                       ->  valid
  0 <= unprintable <= critical <= 90    ->  valid; equal angles leave no
                                            critical band, 0 marks nothing
                                            not printable
  an angle below 0 or past 90           ->  LimitError naming it
  unprintable steeper than critical     ->  LimitError
  tipping margin or least area below 0  ->  LimitError naming it; 0 is allowed
  NaN or infinity in any value          ->  LimitError naming it

INPUTS this has to withstand (strictness_of()):
  the built-in limits                   ->  NORMAL
  the limits of STRICTNESS[STRICT]      ->  STRICT
  any limit set otherwise               ->  CUSTOM

INPUTS this has to withstand (save()):
  the limits of a strictness            ->  its name stored, no values
  any other valid limits                ->  CUSTOM and every value stored
  either                                ->  what was saved before replaced
  invalid limits                        ->  LimitError, nothing stored

INPUTS this has to withstand (reset()):
  anything saved                        ->  all of it removed, current() is built-in
"""

import math
from dataclasses import dataclass, fields

import FreeCAD as App

from . import defaults as d
from .i18n import translate
from .presets import PREFERENCES

# Subgroup of FinSnap's preferences holding the limits. Tests point it
# elsewhere, so they never touch the user's own limits.
LIMITS_GROUP = "Limits"
# The entry there naming the strictness saved.
STRICTNESS_KEY = "Strictness"
# The three levels a check rates by.
GOOD, CRITICAL, UNPRINTABLE = "good", "critical", "unprintable"
# The strictnesses, see STRICTNESS; limits that match none are custom.
STRICT, NORMAL, CUSTOM = "strict", "normal", "custom"
# Angles are measured from the bed, from lying flat to vertical (degrees).
ANGLE_MIN, ANGLE_MAX = 0.0, 90.0


class LimitError(ValueError):
    """The limits do not fit together."""


@dataclass
class Limits:
    # Faces lying flatter than this over the bed are critical (degrees).
    overhang_critical: float = d.OVERHANG_ANGLE
    # Faces lying flatter than this are not printable (degrees).
    overhang_unprintable: float = d.OVERHANG_UNPRINTABLE_ANGLE
    # Overhanging faces smaller than this are not reported (mm2).
    overhang_min_area: float = d.OVERHANG_MIN_AREA
    # A plumb line closer than this to the edge of its footprint is at risk of tipping (mm).
    tipping_margin: float = d.STABILITY_CLOSE

    def validate(self):
        for f in fields(self):
            if not math.isfinite(getattr(self, f.name)):
                raise LimitError(translate("FinSnap", "%s is not a finite number") % f.name)
        for name in ("overhang_critical", "overhang_unprintable"):
            if not ANGLE_MIN <= getattr(self, name) <= ANGLE_MAX:
                raise LimitError(translate("FinSnap", "%s must lie between %.0f and %.0f degrees")
                                 % (name, ANGLE_MIN, ANGLE_MAX))
        if self.overhang_unprintable > self.overhang_critical:
            raise LimitError(translate("FinSnap", "overhang_unprintable must not be steeper than "
                                                  "overhang_critical"))
        for name in ("overhang_min_area", "tipping_margin"):
            if getattr(self, name) < 0:
                raise LimitError(translate("FinSnap", "%s must be 0 or greater") % name)


# The limits of each strictness.
STRICTNESS = {
    STRICT: Limits(overhang_unprintable=d.STRICT_OVERHANG_UNPRINTABLE_ANGLE, tipping_margin=d.STRICT_STABILITY_CLOSE),
    NORMAL: Limits(),
}


def strictness_of(chosen):
    """STRICT or NORMAL where `chosen`, Limits, are those of that strictness, else CUSTOM."""
    return next((name for name, preset in STRICTNESS.items() if preset == chosen), CUSTOM)


def _group():
    return App.ParamGet("%s/%s" % (PREFERENCES, LIMITS_GROUP))


def current():
    """The limits the checks rate by now."""
    group = _group()
    built_in = Limits()
    name = group.GetString(STRICTNESS_KEY, NORMAL)
    if name in STRICTNESS:
        return STRICTNESS[name]
    if name != CUSTOM:
        return built_in
    saved = group.GetFloats()
    custom = Limits(**{f.name: group.GetFloat(f.name) if f.name in saved else getattr(built_in, f.name)
                       for f in fields(Limits)})
    try:
        custom.validate()
    except LimitError:
        return built_in
    return custom


def save(chosen):
    """Make `chosen`, Limits, the ones the checks rate by: by the name of
    their strictness, or as values where they are custom."""
    chosen.validate()
    name = strictness_of(chosen)
    group = _group()
    group.Clear()
    group.SetString(STRICTNESS_KEY, name)
    if name == CUSTOM:
        for f in fields(Limits):
            group.SetFloat(f.name, getattr(chosen, f.name))


def reset():
    """Go back to the built-in limits."""
    _group().Clear()
