"""Check a sliced G-code file for FinSnap fins.

For every part exported together with its fins (objects "<name>" and
"<name>_fins"), layer by layer:
  - no extrusion path of the fins may run into the part,
  - the tines have to reach the part in at least one layer.

Usage (Python with shapely 2.0 or newer):
    python3 tools/check_gcode.py <file.gcode>

The G-code must be plain text (PrusaSlicer: binary_gcode = 0) and carry object
labels (gcode_label_objects = firmware, i.e. M486).

WHAT IS MEASURED, per layer and part:
  distance  ->  smallest distance between the centre lines of fin and part paths.
                >= bead width + CONTACT_SLACK  no contact in this layer
                <  bead width + CONTACT_SLACK  contact: the beads lie against each other
                <  bead width / 2              overlap: a fin path runs into the part's bead
  crossing  ->  a point of a fin path lies inside the convex hull of the part's paths
                in that layer, i.e. a path leading into the part. Only the part's hull
                is used: its cross-section is assumed convex near the fins, the fins'
                is not (blades, foot, tines).
  unlabelled -> extrusion outside any object (purge line, skirt). It must stay at least
                UNLABELLED_DISTANCE away from every object in the same layer.

INPUTS this has to withstand:
  G-code as written by PrusaSlicer          ->  report per part, exit 0
  binary G-code ("GCDE" at the start)       ->  message, exit 2
  no M486 labels                            ->  message, exit 2
  no "<name>_fins" object                   ->  message, exit 2
  fins without their part                   ->  message, exit 2
  G91 (relative positioning)                ->  message, exit 2, not supported
  G2/G3 (arcs)                              ->  counted as the chord; arcs here are short,
                                                and a chord only measures closer, never further
  extrusion without XY move (unretract)     ->  ignored
  negative E (retraction)                   ->  ignored
  M83 / M82 (relative or absolute E)        ->  both understood
  bead width missing in the header          ->  message, exit 2
  crossing or overlap found                 ->  exit 1
  part whose tines touch in no layer        ->  exit 1
  unlabelled extrusion too close            ->  exit 1
  skirt round the foot of a tilted part that
    leans out over it further up            ->  passed: compared within each layer
  file missing                              ->  message, exit 2
  large print, hundreds of thousands of
    segments                                ->  memory grows with the segments, not
                                                with the crossings between layers
"""

import math
import re
import sys
from collections import defaultdict

from shapely import STRtree
from shapely.geometry import LineString, MultiLineString, Point

# How far apart two beads may be on paper and still count as touching, in mm.
# ASSUMPTION: a bead swells a few hundredths beyond its nominal width while
# printing, which closes a gap up to this size. Confirmed only by a test print.
CONTACT_SLACK = 0.05
# How close an unlabelled extrusion may come to an object, in mm.
UNLABELLED_DISTANCE = 2.0
# Header line that holds the width of the outer perimeter.
WIDTH_KEY = "external_perimeter_extrusion_width"
FINS_SUFFIX = "_fins"
WORD = re.compile(r"([A-Z])(-?[0-9.]+)")

EXIT_OK, EXIT_FINDINGS, EXIT_UNUSABLE = 0, 1, 2


class Unusable(Exception):
    """The G-code cannot be checked as it is."""


def read(path):
    """Paths per (layer z, object name) as segments, unlabelled (layer z, segment), bead width."""
    with open(path, "rb") as handle:
        if handle.read(4) == b"GCDE":
            raise Unusable("binary G-code; slice again with binary_gcode = 0")

    paths = defaultdict(list)
    unlabelled = []
    names = {}
    width = None
    current = -1
    last_id = None
    z = 0.0
    x = y = 0.0
    relative_e = True
    last_e = 0.0

    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("; " + WIDTH_KEY + " ="):
                width = float(line.split("=")[1])
                continue
            if line.startswith(";Z:"):
                z = round(float(line[3:]), 3)
                continue
            command = line.split(";")[0].strip()
            if not command:
                continue
            if command.startswith("M486 S"):
                current = int(command[6:])
                last_id = current
                continue
            if command.startswith("M486 A"):
                names[last_id] = command[6:].strip().strip('"')
                continue
            if command == "G91":
                raise Unusable("G91 (relative positioning) is not supported")
            if command == "M83":
                relative_e = True
                continue
            if command == "M82":
                relative_e = False
                continue
            if command.startswith("G92"):
                words = dict(WORD.findall(command[3:]))
                if "E" in words:
                    last_e = float(words["E"])
                continue
            if not re.match(r"^G[0123]\b", command):
                continue

            words = dict(WORD.findall(command[2:]))
            nx = float(words.get("X", x))
            ny = float(words.get("Y", y))
            e = 0.0
            if "E" in words:
                e = float(words["E"]) if relative_e else float(words["E"]) - last_e
                if not relative_e:
                    last_e = float(words["E"])
            if e > 0 and (nx, ny) != (x, y):
                segment = ((x, y), (nx, ny))
                if current >= 0:
                    paths[(z, current)].append(segment)
                else:
                    unlabelled.append((z, segment))
            x, y = nx, ny

    if not names:
        raise Unusable("no M486 labels; slice again with gcode_label_objects = firmware")
    if width is None:
        raise Unusable("%s missing in the G-code header" % WIDTH_KEY)

    named = defaultdict(list)
    for (layer, number), segments in paths.items():
        named[(layer, names.get(number, "object_%d" % number))].extend(segments)
    return named, unlabelled, width


def pairs(paths):
    """Part name -> fins name."""
    objects = {name for _, name in paths}
    found = {}
    for name in objects:
        if name.endswith(FINS_SUFFIX):
            part = name[:-len(FINS_SUFFIX)]
            if part not in objects:
                raise Unusable("%s has no part named %s" % (name, part))
            found[part] = name
    if not found:
        raise Unusable("no object named <part>%s" % FINS_SUFFIX)
    return found


def lines(segments):
    return MultiLineString([list(s) for s in segments])


def measure(paths, part, fins):
    """(layer z, distance, crossing) for every layer both objects share."""
    layers = sorted({z for z, n in paths if n == fins} & {z for z, n in paths if n == part})
    result = []
    for z in layers:
        f = lines(paths[(z, fins)])
        p = lines(paths[(z, part)])
        hull = p.convex_hull
        crossing = any(hull.contains(Point(pt)) for s in paths[(z, fins)] for pt in s)
        result.append((z, f.distance(p), crossing))
    return result


def nearest_in_layer(paths, unlabelled):
    """Smallest distance from an unlabelled segment to an object segment of the
    same layer; infinity if no layer holds both.

    Layer by layer: the skirt of the first layer runs round the foot of a tilted
    part, which leans out over it further up, so all layers in one plane would
    report the skirt as touching. A spatial index per layer keeps the memory to
    the segments; merging them into one shape nodes every crossing and ran a
    large print out of memory.
    """
    by_layer = defaultdict(list)
    for z, segment in unlabelled:
        by_layer[z].append(LineString(segment))
    nearest = math.inf
    for z, extruded in by_layer.items():
        objects = [LineString(s) for (layer, _), segments in paths.items() if layer == z for s in segments]
        if not objects:
            continue
        _, distances = STRtree(objects).query_nearest(extruded, return_distance=True)
        nearest = min(nearest, float(distances.min()))
    return nearest


def main(argv):
    if len(argv) != 2:
        print("Usage: python3 tools/check_gcode.py <file.gcode>")
        return EXIT_UNUSABLE
    try:
        paths, unlabelled, width = read(argv[1])
        found = pairs(paths)
    except (OSError, Unusable) as error:
        print("Cannot check:", error)
        return EXIT_UNUSABLE

    contact_limit = width + CONTACT_SLACK
    overlap_limit = width / 2
    findings = 0
    print("bead width %.2f mm, contact below %.2f mm, overlap below %.2f mm"
          % (width, contact_limit, overlap_limit))

    for part in sorted(found):
        values = measure(paths, part, found[part])
        contacts = [(z, d) for z, d, _ in values if d < contact_limit]
        overlaps = [z for z, d, _ in values if d < overlap_limit]
        crossings = [z for z, _, c in values if c]
        print("\n%s: %d shared layers" % (part, len(values)))
        print("  contact at z = %s" % (", ".join("%.2f" % z for z, _ in contacts) or "none"))
        if contacts:
            print("  beads apart at contact: up to %.3f mm" % (max(d for _, d in contacts) - width))
        if overlaps:
            print("  OVERLAP at z = %s" % ", ".join("%.2f" % z for z in overlaps))
        if crossings:
            print("  CROSSING at z = %s" % ", ".join("%.2f" % z for z in crossings))
        if not contacts:
            print("  ERROR: the tines reach the part in no layer")
        if overlaps or crossings or not contacts:
            findings += 1

    if unlabelled:
        nearest = nearest_in_layer(paths, unlabelled)
        where = "%.1f mm away" % nearest if math.isfinite(nearest) else "in no layer with an object"
        print("\nunlabelled extrusion: %d segments, nearest object in the same layer %s"
              % (len(unlabelled), where))
        if nearest < UNLABELLED_DISTANCE:
            print("  ERROR: closer than %.1f mm" % UNLABELLED_DISTANCE)
            findings += 1

    print("\nresult:", "passed" if not findings else "%d finding(s)" % findings)
    return EXIT_FINDINGS if findings else EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
