"""Draw the two explanatory drawings of the task panel.

    python3 tools/make_drawings.py

writes freecad/finsnap/images/side_view.svg and top_view.svg. The drawings are
schematic, not to scale. Dimensions follow drawing practice: thin extension
lines from the feature, a dimension line with arrowheads, the letter beside it.
The letters match feature.MARKS.

Arrowheads are drawn as polygons: Qt renders SVG Tiny, which has no markers.
"""

import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, "freecad", "finsnap", "images")

PART_FILL = "#3d8fd6"
PART_LINE = "#1f4f7a"
FIN_FILL = "#f0a030"
FIN_LINE = "#8a5512"
DIMENSION = "#3a4148"
LETTER = "#1f4f7a"
# The drawings carry their own light background, so they read the same in a
# dark and a light FreeCAD theme.
BACKGROUND = "#ffffff"
BACKGROUND_RADIUS = 6
PART_OPACITY = 0.35
FOOT_OPACITY = 0.45

ARROW_LENGTH = 8.0
ARROW_HALF_WIDTH = 3.0
EXTENSION_WIDTH = 1.0
DIMENSION_WIDTH = 1.6
OUTSIDE_ARROW_REACH = 11.0  # length of the leader for arrows pointing in from outside
# Heights in the side view, between two tines, where the gap A and the tine
# clearance K are dimensioned, clear of the tines.
GAP_AT = 138.0
CLEARANCE_AT = 163.0
# Both drawings are shown this much larger than drawn, the same for each.
SCALE = 1.5
FONT = 'font-family="sans-serif" font-size="15" font-weight="bold"'


def arrowhead(tip, toward):
    """Triangle with its point on `tip`, pointing along the direction `toward`."""
    dx, dy = toward
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    bx, by = tip[0] - ux * ARROW_LENGTH, tip[1] - uy * ARROW_LENGTH
    nx, ny = -uy * ARROW_HALF_WIDTH, ux * ARROW_HALF_WIDTH
    points = [tip, (bx + nx, by + ny), (bx - nx, by - ny)]
    return '<polygon points="%s" fill="%s"/>' % (
        " ".join("%.1f,%.1f" % p for p in points), DIMENSION)


def line(a, b, width, extra=""):
    return '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s"%s/>' % (
        a[0], a[1], b[0], b[1], DIMENSION, width, extra)


def extension(a, b):
    return line(a, b, EXTENSION_WIDTH)


def centre_line(a, b):
    return line(a, b, EXTENSION_WIDTH, ' stroke-dasharray="8 3 2 3"')


def dimension(a, b):
    """Dimension line between a and b with arrowheads pointing outward onto both."""
    d = (b[0] - a[0], b[1] - a[1])
    return [line(a, b, DIMENSION_WIDTH), arrowhead(b, d), arrowhead(a, (-d[0], -d[1]))]


def dimension_outside(a, b):
    """For a size too small for arrows inside: arrows come from outside onto a and b."""
    d = (b[0] - a[0], b[1] - a[1])
    length = math.hypot(*d)
    u = (d[0] / length, d[1] / length)
    before = (a[0] - u[0] * OUTSIDE_ARROW_REACH, a[1] - u[1] * OUTSIDE_ARROW_REACH)
    after = (b[0] + u[0] * OUTSIDE_ARROW_REACH, b[1] + u[1] * OUTSIDE_ARROW_REACH)
    return [line(before, a, DIMENSION_WIDTH), arrowhead(a, u),
            line(after, b, DIMENSION_WIDTH), arrowhead(b, (-u[0], -u[1]))]


def letter(text, at):
    return '<text x="%.1f" y="%.1f" fill="%s">%s</text>' % (at[0], at[1], LETTER, text)


def svg(width, height, comment, body):
    head = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" %s>'
            % (round(width * SCALE), round(height * SCALE), width, height, FONT))
    note = "  <!-- %s Written by tools/make_drawings.py; change the script, not this file. -->" % comment
    background = '<rect width="%d" height="%d" rx="%d" fill="%s"/>' % (width, height, BACKGROUND_RADIUS, BACKGROUND)
    body = [background] + body
    return "\n".join([head, note] + ["  " + element for element in body] + ["</svg>", ""])


def side_view():
    """The tilted part on the right, the fin on the left, the bed below."""
    bed = 200.0
    # The face runs at 45 degrees: x = y in drawing coordinates. The tines end
    # CLEAR_X short of it, the flank of the fin runs GAP_X further out still;
    # both measured across, as horizontal offsets.
    gap_x = 17.0
    clear_x = 10.0
    fin_out, fin_top, foot_top = 83.0, 124.0, 188.0
    tines = (178.0, 148.0, 124.0)  # top edge of each tine
    tine_h = 5.0

    def flank(y):
        return y - clear_x - gap_x

    def tine_end(y):
        return y - clear_x

    body = [
        line((0, bed), (320, bed), 3),
        '<polygon points="200,200 110,110 200,20 290,110" fill="%s" fill-opacity="%s" stroke="%s" '
        'stroke-width="2"/>' % (PART_FILL, PART_OPACITY, PART_LINE),
        '<polygon points="%s" fill="%s" stroke="%s" stroke-width="2" stroke-linejoin="round"/>' % (
            " ".join("%.1f,%.1f" % p for p in [(fin_out, bed), (flank(foot_top), bed), (flank(foot_top), foot_top),
                                                (flank(fin_top), fin_top), (fin_out, fin_top)]),
            FIN_FILL, FIN_LINE),
    ]
    for top in tines:
        bottom = top + tine_h
        corners = [(flank(top), top), (tine_end(top), top), (tine_end(bottom), bottom), (flank(bottom), bottom)]
        body.append('<polygon points="%s" fill="%s"/>' % (
            " ".join("%.1f,%.1f" % p for p in corners), FIN_LINE))

    first_bottom, second_bottom = tines[0] + tine_h, tines[1] + tine_h
    plateau_end = flank(fin_top)
    body += [
        extension((fin_out, fin_top), (34, fin_top)),
        extension((flank(second_bottom), second_bottom), (56, second_bottom)),
        extension((flank(first_bottom), first_bottom), (56, first_bottom)),
        extension((fin_out, foot_top), (70, foot_top)),
        extension((fin_out, fin_top), (fin_out, 100)),
        extension((plateau_end, fin_top), (plateau_end, 100)),
        extension((tine_end(tines[2] + tine_h), tines[2]), (146, tines[2])),
        extension((tine_end(tines[2] + tine_h), tines[2] + tine_h), (146, tines[2] + tine_h)),
    ]
    body += dimension((40, fin_top), (40, bed))                                  # E
    body += dimension((62, second_bottom), (62, first_bottom))                   # B
    body += dimension((62, first_bottom), (62, bed))                             # C
    body += dimension((fin_out, 106), (plateau_end, 106))                        # F
    body += dimension_outside((76, foot_top), (76, bed))                         # G
    body += dimension_outside((141, tines[2]), (141, tines[2] + tine_h))         # D
    # Across the face, each in a free space between two tines: the gap A from
    # the plane of the tine ends to the flank, and below it the tine clearance
    # K from the face to that plane.
    a_from = (tine_end(GAP_AT), GAP_AT)
    a_to = (a_from[0] - gap_x / 2, a_from[1] + gap_x / 2)
    k_from = (CLEARANCE_AT, CLEARANCE_AT)
    k_to = (k_from[0] - clear_x / 2, k_from[1] + clear_x / 2)
    body += [centre_line((tine_end(tines[0]), tines[0]), (tine_end(132.0), 132.0))]
    body += dimension_outside(a_from, a_to)                                     # A
    body += dimension_outside(k_from, k_to)                                     # K
    body += [letter("E", (26, 166)), letter("B", (48, 172)), letter("C", (48, 196)),
             letter("F", (90, 98)), letter("G", (82, 222)), letter("D", (147, 122)),
             letter("A", (103, 162)), letter("K", (174, 152))]
    return svg(320, 230, "Side view: part, fin with tines and foot, bed.", body)


def top_view():
    """The supported face along the top, fins and feet reaching out below it."""
    left_fin, right_fin, fin_w = 50.0, 262.0, 8.0
    fin_top, fin_bottom = 68.0, 155.0
    foot_half_w, foot_half_l, foot_cy = 18.0, 40.0, 115.0
    face_end = 30.0
    right_centre = right_fin + fin_w / 2
    body = ['<rect x="30" y="20" width="260" height="40" fill="%s" fill-opacity="%s" stroke="%s" '
            'stroke-width="2"/>' % (PART_FILL, PART_OPACITY, PART_LINE)]
    for x in (left_fin, right_fin):
        body.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" fill-opacity="%s" '
                    'stroke="%s" stroke-width="1.5"/>' % (x + fin_w / 2, foot_cy, foot_half_w, foot_half_l,
                                                         FIN_FILL, FOOT_OPACITY, FIN_LINE))
    for x in (left_fin, right_fin):
        body.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" stroke="%s" '
                    'stroke-width="2"/>' % (x, fin_top, fin_w, fin_bottom - fin_top, FIN_FILL, FIN_LINE))
    body += [
        extension((face_end, 60), (face_end, 196)),
        extension((left_fin, fin_bottom), (left_fin, 196)),
        extension((left_fin + fin_w, fin_bottom), (left_fin + fin_w, 174)),
        extension((right_centre + foot_half_w, foot_cy), (right_centre + foot_half_w, 174)),
        centre_line((right_centre, 64), (right_centre, 174)),
    ]
    body += dimension_outside((left_fin, 168), (left_fin + fin_w, 168))          # H
    body += dimension((face_end, 190), (left_fin, 190))                          # I
    body += dimension((right_centre, 168), (right_centre + foot_half_w, 168))    # J
    body += [letter("H", (76, 173)), letter("I", (36, 206)), letter("J", (290, 173))]
    return svg(320, 210, "Top view: face, fins and feet.", body)


def main():
    for name, content in (("side_view.svg", side_view()), ("top_view.svg", top_view())):
        with open(os.path.join(IMAGES, name), "w", encoding="utf-8") as handle:
            handle.write(content)
        print("written", name)


if __name__ == "__main__":
    main()
