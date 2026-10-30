# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The analysis of a part as it stands: what keeps it from printing.

Faces overhanging without fins, bridges, islands, and whether the part stays
standing while it is printed, with the notes the checks say and the levels
they rate by. What the fins carry and where they hold the part is given by
the caller, feature.py, as this module knows no fin objects and no task
panel. What is worked out is kept for each part as it stands (stand_key()),
as fins are built far more often than their part changes; the ways Quick
fins rates (rate_plans()) are worked out each time, as they stand the part
in turns.

INPUTS this has to withstand (the kept analysis, _analysis()):
  a part asked again as it stands       ->  the same entry: islands, bridges and
                                            centres of mass taken, not worked out
  the part recomputed, shape the same   ->  the same key: taken
  the part moved or changed after       ->  another key: worked out anew
  a hole or pocket moved, the measures
    of the shape the same               ->  its corners moved: another key
  other layers asked                    ->  another key: worked out anew
  many parts in turn                    ->  the oldest goes past KEPT
"""

import math
from collections import namedtuple

import FreeCAD as App

from . import bridge
from . import defaults as d
from . import limits
from . import overhang
from . import stability as standing
from .i18n import QT_TRANSLATE_NOOP, translate
from .presets import PREFERENCES
from .shapes import FACE_PREFIX, face_name, global_shape, moved

# Parts as they stand, by stand_key(), kept at most this many, the oldest
# going first; their shapes and corners compared to this many decimal places.
KEPT = 8
KEY_DIGITS = 6
# What an entry keeps: the islands, None until worked out; the bridges, by
# the bead, the limits and the faces carried; the centres of mass of the
# part printed up to each layer, as standing.check() works them out.
ISLANDS, BRIDGES, CENTRES = "islands", "bridges", "centres"
_kept = {}
# Whether islands and bridges are checked while fins are made and edited, in
# FinSnap's preferences: on a slow computer they can be left to Check part.
# Named for islands alone, as it was before bridges: the setting saved holds.
ISLANDS_WHILE_EDITING = "IslandsWhileEditing"

# Said for the bridges spanning too far, by level: how many, of which part,
# the limit and the longest span (mm), the faces they lie under.
NOTE_BRIDGES = {
    limits.CRITICAL: QT_TRANSLATE_NOOP(
        "FinSnap", "%d bridges of %s span further than %.1f mm, the longest %.1f mm: %s"),
    limits.UNPRINTABLE: QT_TRANSLATE_NOOP(
        "FinSnap", "%d bridges of %s span further than %.1f mm, too far to print, the longest %.1f mm: %s"),
}
STANDS, CLOSE, TIPS = "stands", "close", "tips"
SIDE_SHARE = math.sqrt(0.5)
NOTE_NOTHING_ON_BED = QT_TRANSLATE_NOOP("FinSnap", "Nothing of the part stands on the bed.")
NOTE_STANDS = QT_TRANSLATE_NOOP(
    "FinSnap", "Stands on its own while it is printed: tipping margin at least %.1f mm, smallest at layer %d "
    "(%.1f mm).")
NOTE_STANDS_CLOSE = QT_TRANSLATE_NOOP(
    "FinSnap", "At risk of tipping on its own: tipping margin only %.1f mm at layer %d (%.1f mm).")
NOTE_NEEDS_FINS = QT_TRANSLATE_NOOP(
    "FinSnap", "Tips over at layer %d (%.1f mm) while it is printed: fins under its leaning face hold it.")
NOTE_HELD = QT_TRANSLATE_NOOP(
    "FinSnap", "On its own it would tip over at layer %d (%.1f mm); its fins hold it: tipping margin at least "
    "%.1f mm, smallest at layer %d (%.1f mm).")
NOTE_HELD_CLOSE = QT_TRANSLATE_NOOP(
    "FinSnap", "On its own it would tip over at layer %d (%.1f mm); its fins hold it, but it is at risk of "
    "tipping: tipping margin only %.1f mm at layer %d (%.1f mm).")
NOTE_BEFORE_TINES = QT_TRANSLATE_NOOP(
    "FinSnap", "Tips over at layer %d (%.1f mm), before its fins hold it from their lowest tine at %.1f mm: "
    "set the first tine lower.")
NOTE_AWAY_FROM_FINS = QT_TRANSLATE_NOOP(
    "FinSnap", "Tips over at layer %d (%.1f mm), away from its fins: a counter fin on that side holds it.")
NOTE_TOWARDS_FINS = QT_TRANSLATE_NOOP(
    "FinSnap", "Tips over at layer %d (%.1f mm) towards its fins, past their feet: a longer foot or more "
    "fins hold it.")
NOTE_PAST_EDGE_END = QT_TRANSLATE_NOOP(
    "FinSnap", "Tips over at layer %d (%.1f mm), past an end of the edge it stands on.")

# The lines of Check part, one for each check.
NOTE_OVERHANGS = QT_TRANSLATE_NOOP("FinSnap", "%d faces overhang flatter than %.0f degrees from the bed without "
                                             "fins.")
NOTE_UNPRINTABLE = QT_TRANSLATE_NOOP("FinSnap", "%d faces overhang flatter than %.0f degrees from the bed without "
                                               "fins, too flat to print.")
NOTE_NO_OVERHANGS = QT_TRANSLATE_NOOP("FinSnap", "No face overhangs without fins.")
NOTE_ISLANDS_FOUND = QT_TRANSLATE_NOOP("FinSnap", "%d island(s): it would start printing in the air there.")
NOTE_NO_ISLANDS = QT_TRANSLATE_NOOP("FinSnap", "No islands.")
NOTE_NO_BRIDGES = QT_TRANSLATE_NOOP("FinSnap", "No bridge spans further than %.1f mm.")
# What the colours of a stability check mean, said with its result.
NOTE_COLOURS = QT_TRANSLATE_NOOP(
    "FinSnap", "Colours by height: green stands, yellow is at risk of tipping (tipping margin under %.0f mm), red "
    "tips over from there.")


def stand_key(part_obj, p):
    """What the analysis of `part_obj` depends on: the part, its shape, where
    it stands and the layers of `p`. The shape by its measures and where its
    corners lie, not its hash: FreeCAD gives a part a new hash each time it is
    recomputed, the same shape or not. The corners tell a shape whose measures
    stay apart, as with a hole moved."""
    shape = part_obj.Shape
    corners = tuple(sorted(tuple(round(c, KEY_DIGITS) for c in vertex.Point) for vertex in shape.Vertexes))
    measures = (round(shape.Volume, KEY_DIGITS), round(shape.Area, KEY_DIGITS),
                len(shape.Faces), len(shape.Edges), corners)
    return (part_obj.Document.Name, part_obj.Name, measures, tuple(part_obj.getGlobalPlacement().toMatrix().A),
            p.first_layer_height, p.layer_height)


def _keep(store, key, make):
    """What `store` keeps under `key`, made by make() where it keeps nothing
    yet; past KEPT entries the oldest goes first."""
    if key not in store:
        while len(store) >= KEPT:
            store.pop(next(iter(store)))
        store[key] = make()
    return store[key]


def _analysis(part_obj, p):
    """The entry kept for `part_obj` as it stands on the layers of `p`, made
    empty where there is none yet."""
    return _keep(_kept, stand_key(part_obj, p), lambda: {ISLANDS: None, BRIDGES: {}, CENTRES: {}})


def checks_while_editing():
    """Whether islands and bridges are checked while fins are made and
    edited, as the user set it with Islands and bridges while editing; on,
    if never set."""
    return App.ParamGet(PREFERENCES).GetBool(ISLANDS_WHILE_EDITING, True)


def set_checks_while_editing(on):
    App.ParamGet(PREFERENCES).SetBool(ISLANDS_WHILE_EDITING, bool(on))


def islands(part_obj, p):
    """The islands (overhang.islands()) of `part_obj` as it stands, on the
    layers of `p`; fins do not count. Worked out once for the part as it
    stands, unless keep_islands() was told them before."""
    kept = _analysis(part_obj, p)
    if kept[ISLANDS] is None:
        kept[ISLANDS] = overhang.islands(global_shape(part_obj), p.first_layer_height, p.layer_height)
    return list(kept[ISLANDS])


def keep_islands(part_obj, p, found):
    """Keep `found`, the islands of `part_obj` as it stands now on the layers
    of `p`, for islands(), as Quick fins has worked them out already."""
    _analysis(part_obj, p)[ISLANDS] = list(found)


def bridges(part_obj, shape, supported, p):
    """The bridges (bridge.bridges()) of `part_obj` as it stands, its shape
    `shape`, on the layers and beads of `p`, rated by the limits of the
    preferences; faces in `supported`, carried by fins, span nothing. Worked
    out once for the part as it stands, the bead, the limits and the faces
    carried, at most KEPT combinations of them."""
    rating = limits.current()
    carried = tuple(number for number, face in enumerate(shape.Faces, 1)
                    if any(face.isSame(other) for other in supported))
    found = _keep(_analysis(part_obj, p)[BRIDGES], (p.bead_width, rating, carried),
                  lambda: bridge.bridges(shape, p.first_layer_height, p.layer_height, p.bead_width, rating, supported))
    return list(found)


def overhangs(part_obj, shape, supported, p, with_bridges=True):
    """(name, level) of the faces of `part_obj`, its shape `shape`, that
    overhang, faces in `supported` carried by fins left out, rated by the
    limits of the preferences: limits.CRITICAL or limits.UNPRINTABLE. Faces a
    bridge covers whole (bridges(), on the layers and beads of `p`) are no
    overhangs: their risk is their span. A face the bridge covers in part
    still overhangs where it does not. Without `with_bridges` no bridge is
    looked for, and every face is rated."""
    spanned = ({number for found in bridges(part_obj, shape, supported, p) for number in found.covered}
               if with_bridges else set())
    return [(face_name(number), level) for number, level in overhang.rated(shape, supported, limits.current())
            if number not in spanned]


def bridge_notes(part_obj, found):
    """The warnings for the Bridges `found` of `part_obj`, by level, each with
    the faces they lie under, as (note, names)."""
    rating = limits.current()
    limit = {limits.CRITICAL: rating.bridge_critical, limits.UNPRINTABLE: rating.bridge_unprintable}
    notes = []
    for level in (limits.CRITICAL, limits.UNPRINTABLE):
        spans = [spanned for spanned in found if spanned.level == level]
        if spans:
            names = sorted({face_name(number) for spanned in spans for number in spanned.faces},
                           key=lambda name: int(name[len(FACE_PREFIX):]))
            notes.append((translate("FinSnap", NOTE_BRIDGES[level])
                          % (len(spans), part_obj.Label, limit[level], max(s.span for s in spans), ", ".join(names)),
                          names))
    return notes


def bridge_lines(part_obj, spans):
    """The lines saying what the bridges `spans` of `part_obj` are, by level;
    one saying none spans too far where none does."""
    lines = [note for note, _ in bridge_notes(part_obj, spans)]
    return lines or [translate("FinSnap", NOTE_NO_BRIDGES) % limits.current().bridge_critical]


def bridges_level(spans):
    """The level of the bridges `spans` as a check rates it, those of a
    stability check: TIPS where one is too long to print, CLOSE where one is
    critical, else STANDS."""
    levels = {spanned.level for spanned in spans}
    return TIPS if limits.UNPRINTABLE in levels else CLOSE if limits.CRITICAL in levels else STANDS


def part_report(part_obj, rated, spans, found, level, note, shown):
    """What Check part says of `part_obj`: the level of the worst found and a
    line for each check, from its overhangs `rated` (overhangs()), bridges
    `spans`, islands `found` and its stability, `level`, `note` and `shown`
    (stability()). Faces too flat to print, bridges too long and islands keep
    the part from printing; critical ones are a risk, as coming close to
    tipping is."""
    rating = limits.current()
    unprintable = [name for name, rated_level in rated if rated_level == limits.UNPRINTABLE]
    critical = len(rated) - len(unprintable)
    lines = []
    if critical:
        lines.append(translate("FinSnap", NOTE_OVERHANGS) % (critical, rating.overhang_critical))
    if unprintable:
        lines.append(translate("FinSnap", NOTE_UNPRINTABLE) % (len(unprintable), rating.overhang_unprintable))
    if not rated:
        lines.append(translate("FinSnap", NOTE_NO_OVERHANGS))
    lines += bridge_lines(part_obj, spans)
    lines.append(translate("FinSnap", NOTE_ISLANDS_FOUND) % len(found) if found
                 else translate("FinSnap", NOTE_NO_ISLANDS))
    lines.append(with_colours(note, shown))
    levels = {rated_level for _, rated_level in rated} | {spanned.level for spanned in spans}
    worst = (TIPS if limits.UNPRINTABLE in levels or found
             else CLOSE if limits.CRITICAL in levels and level == STANDS else level)
    return worst, lines


def with_colours(note, shown):
    """`note`, followed by what the colours of the part mean, where they show."""
    if shown is None:
        return note
    return note + "\n" + translate("FinSnap", NOTE_COLOURS) % limits.current().tipping_margin


def stability(part_obj, p, holders):
    """Whether `part_obj`, as it stands, stays standing while it is printed in
    the layers of `p`, as (level, note, shown): first the part alone; where it
    tips, whether its fins hold it, and if not, why: `holders()`, asked only
    then, says what holds it up beside it on the bed, as
    feature.supports_of() does.
    `level` is STANDS, CLOSE or TIPS, `note` says it in a sentence, and
    `shown` is the standing.Stability to show the plumb line of: of the part
    alone where it stands so, else held by its fins; None where nothing of
    the part stands on the bed. The centres of mass are kept for the part as
    it stands, so a check after the fins changed only measures their feet.

    CASES this has to withstand:
      stands alone, far from tipping       ->  STANDS, the closest layer
      stands alone, within the tipping
        margin of the preferences          ->  CLOSE
      tips alone, no fins                  ->  TIPS, add fins
      tips alone, the fins hold it         ->  STANDS or CLOSE, the layer it would tip at
      tips before the lowest tine          ->  TIPS, the height of that tine
      tips away from its fins, none on that
        side                               ->  TIPS, add a counter fin
      tips towards a fin, main or counter  ->  TIPS, past their feet
      a part off the bed at z 0            ->  the tines measured from its bottom
      tips past an end of its edge         ->  TIPS, past an end of the edge
      nothing on the bed                   ->  TIPS, None to show
    """
    centres = _analysis(part_obj, p)[CENTRES]
    margin = limits.current().tipping_margin
    part = global_shape(part_obj)
    alone = standing.check(part, [], p.first_layer_height, p.layer_height, centres, p.brim_width)
    if alone is None:
        return TIPS, translate("FinSnap", NOTE_NOTHING_ON_BED), None
    if not alone.tips:
        close = alone.margin < margin
        note = NOTE_STANDS_CLOSE if close else NOTE_STANDS
        return ((CLOSE if close else STANDS), translate("FinSnap", note)
                % (alone.margin, alone.layer + 1, alone.height), alone)
    tipping = (alone.layer + 1, alone.height)
    supports, sides = holders()
    if not supports:
        return TIPS, translate("FinSnap", NOTE_NEEDS_FINS) % tipping, alone
    held = standing.check(part, supports, p.first_layer_height, p.layer_height, centres, p.brim_width)
    if held is None:
        return TIPS, translate("FinSnap", NOTE_NOTHING_ON_BED), None
    if not held.tips:
        close = held.margin < margin
        note = NOTE_HELD_CLOSE if close else NOTE_HELD
        return ((CLOSE if close else STANDS), translate("FinSnap", note)
                % (tipping + (held.margin, held.layer + 1, held.height)), held)
    at = (held.layer + 1, held.height)
    # Over the bed, as the heights of the layers are.
    lowest = min(height for _, height in supports) - held.foot.z
    if held.height < lowest:
        return TIPS, translate("FinSnap", NOTE_BEFORE_TINES) % (at + (lowest,)), held
    towards = max((held.outward.dot(side.normalize()) for side in sides if side.Length > d.TOLERANCE),
                  default=0.0)
    away = min((held.outward.dot(side.normalize()) for side in sides if side.Length > d.TOLERANCE),
               default=0.0)
    # Towards a fin first: with a counter fin, the side it tips to has one.
    if towards > SIDE_SHARE:
        return TIPS, translate("FinSnap", NOTE_TOWARDS_FINS) % at, held
    if away < -SIDE_SHARE:
        return TIPS, translate("FinSnap", NOTE_AWAY_FROM_FINS) % at, held
    return TIPS, translate("FinSnap", NOTE_PAST_EDGE_END) % at, held


# A QuickPlan rated for Quick fins (printable_plans()): its Islands, the
# levels of the faces overhanging without fins, limits.CRITICAL or
# UNPRINTABLE, and its bridge.Bridges; None each where it was not checked.
RatedPlan = namedtuple("RatedPlan", "plan islands overhangs bridges")


def printable_plans(shape, plans, p):
    """The QuickPlans `plans` for `shape` as RatedPlans, rated by the limits of
    the preferences: those that print, with no island, no face too flat and
    no bridge too long to print, in the order given; where none does, all of
    them, the fewest islands first, then the fewest faces and bridges that do
    not print. The islands are those of the part stood by the plan, see
    overhang.islands(); the fins do not count, they carry no layer. The
    overhangs and bridges leave out the face the fins go under, and a face a
    bridge covers whole is no overhang. Plans standing the part alike, differing
    only by the face for the fins, are checked for islands and bridges once.

    INPUTS this has to withstand:
      plans that print and plans that do not
                                            ->  those that print, in the order given
      every plan with islands               ->  all of them, the fewest first, the
                                                order given among as many
      as many islands, faces or bridges
        that do not print                   ->  the fewest of those first
      critical faces and bridges only       ->  the plan prints: kept, rated
      plans standing the part alike         ->  checked for islands and bridges once,
                                                the bridges of the face under the fins
                                                left out
      one plan                              ->  it, with None for each: unchecked,
                                                as there is no choice, and the fins
                                                warn of them
    """
    if len(plans) == 1:
        return [RatedPlan(plans[0], None, None, None)]
    rated = rate_plans(shape, plans, p)

    def unprintable(entry):
        return (entry.overhangs.count(limits.UNPRINTABLE)
                + sum(1 for found in entry.bridges if found.level == limits.UNPRINTABLE))

    clean = [entry for entry in rated if not entry.islands and not unprintable(entry)]
    return clean or sorted(rated, key=lambda entry: (len(entry.islands), unprintable(entry)))


def rate_plans(shape, plans, p):
    """The QuickPlans `plans` for `shape` as RatedPlans, in the order given,
    each rated as printable_plans() rates them, with none left out."""
    rating = limits.current()
    checked = {}
    rated = []
    for plan in plans:
        stood = moved(shape, plan.change)
        key = tuple(plan.change.toMatrix().A)
        if key not in checked:
            checked[key] = (overhang.islands(stood, p.first_layer_height, p.layer_height),
                            bridge.bridges(stood, p.first_layer_height, p.layer_height, p.bead_width, rating))
        found_islands, every = checked[key]
        # The face under the fins spans nothing: it leaves the bridges it
        # alone lies under, the others lie under it no longer.
        carried = plan.number + 1
        spans = [found._replace(faces=[n for n in found.faces if n != carried],
                                covered=[n for n in found.covered if n != carried])
                 for found in every if any(n != carried for n in found.faces)]
        spanned = {number for found in spans for number in found.covered}
        levels = [level for number, level in overhang.rated(stood, (stood.Faces[plan.number],), rating)
                  if number not in spanned]
        rated.append(RatedPlan(plan, found_islands, levels, spans))
    return rated
