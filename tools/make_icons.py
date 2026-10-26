"""Draw the icons of the workbench and the logo.

    python3 tools/make_icons.py

writes freecad/finsnap/icons/*.svg and docs/assets/logo.svg. All icons share one picture of the part
and its fin, the same one the drawings of the task panel use: the part standing
on an edge, the fin parallel to its face at a gap, with a flat top, horizontal
tines and a foot. Changing that picture here changes every icon.
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "freecad", "finsnap", "icons")
LOGO = os.path.join(ROOT, "docs", "assets", "logo.svg")
# The mark of the logo is the workbench icon, scaled up; the name sits beside it.
LOGO_SCALE = 2.6
LOGO_FONT_SIZE = 72
LOGO_PADDING = 16
LOGO_GAP = 24
# Width of the name in font sizes. Fonts differ (about 3.9 for Arial, 4.6 for
# DejaVu Sans Bold); textLength pins the name to this width in every font, so the
# banner stays centred whatever the viewer has installed.
LOGO_NAME_EM = 4.2

PART_FILL = "#3d8fd6"
PART_LINE = "#1f4f7a"
FIN_FILL = "#f0a030"
FIN_LINE = "#8a5512"
BED = "#5c6670"
ADD_FILL = "#3fa34d"
ADD_LINE = "#1d5e26"
# The badge of Quick fins: a lightning bolt on yellow, one step instead of several.
QUICK_FILL = "#f2c230"
QUICK_LINE = "#8a6d12"
WHITE = "#ffffff"
PAPER = "#f4f6f8"
LINE_WIDTH = 1.5

SIZE = 64
BED_Y = 58.0
BED_LEFT = 2.0
BED_WIDTH = 60.0
BED_HEIGHT = 3.0
# The part is a square standing on its corner; its lower left face runs at 45
# degrees, x = y - FACE_OFFSET in icon coordinates.
PART_CENTRE = (38.0, 40.0)
PART_HALF = 18.0
FACE_OFFSET = BED_Y - PART_CENTRE[0]   # the face passes through the bottom corner
GAP_X = 4.0          # horizontal gap between face and flank
FIN_TOP = 43.0
PLATEAU = 5.0
FOOT_TOP = 55.0
FOOT_REACH = 2.0     # how far the foot reaches past the outer end of the fin
TINES = (52.0, 46.0)  # lower edge of each tine
TINE_HEIGHT = 2.0


def points(pts):
    return " ".join("%.1f,%.1f" % p for p in pts)


def face_x(y):
    return y - FACE_OFFSET


def flank_x(y):
    return face_x(y) - GAP_X


def mirror(pts, axis):
    return [(2 * axis - x, y) for x, y in pts]


def fin_shapes(mirrored=False):
    """Fin with foot and tines, on the left of the part, or mirrored to the right."""
    outer = flank_x(FIN_TOP) - PLATEAU
    blade = [(outer, BED_Y), (flank_x(FOOT_TOP), BED_Y), (flank_x(FOOT_TOP), FOOT_TOP),
             (flank_x(FIN_TOP), FIN_TOP), (outer, FIN_TOP)]
    foot = [(outer - FOOT_REACH, FOOT_TOP), (flank_x(FOOT_TOP), FOOT_TOP),
            (flank_x(FOOT_TOP), BED_Y), (outer - FOOT_REACH, BED_Y)]
    tines = []
    for low in TINES:
        high = low - TINE_HEIGHT
        tines.append([(flank_x(high), high), (face_x(high), high), (face_x(low), low), (flank_x(low), low)])
    shapes = [blade, foot] + tines
    if mirrored:
        shapes = [mirror(s, PART_CENTRE[0]) for s in shapes]
    out = ['<polygon points="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>'
           % (points(shapes[0]), FIN_FILL, FIN_LINE, LINE_WIDTH),
           '<polygon points="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>'
           % (points(shapes[1]), FIN_FILL, FIN_LINE, LINE_WIDTH)]
    out += ['<polygon points="%s" fill="%s"/>' % (points(t), FIN_LINE) for t in shapes[2:]]
    return out


def part_shape():
    cx, cy = PART_CENTRE
    h = PART_HALF
    return ['<polygon points="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>'
            % (points([(cx, cy + h), (cx - h, cy), (cx, cy - h), (cx + h, cy)]), PART_FILL, PART_LINE,
               LINE_WIDTH)]


def bed():
    return ['<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1" fill="%s"/>'
            % (BED_LEFT, BED_Y, BED_WIDTH, BED_HEIGHT, BED)]


def plus_badge():
    return ['<circle cx="52" cy="12" r="10" fill="%s" stroke="%s" stroke-width="2"/>' % (ADD_FILL, ADD_LINE),
            '<g stroke="%s" stroke-width="3.5" stroke-linecap="round">' % WHITE,
            '<line x1="52" y1="7" x2="52" y2="17"/><line x1="47" y1="12" x2="57" y2="12"/></g>']


def bolt_badge():
    bolt = "53,4 45,13 50,13 48,20 57,10 52,10 54,4"
    return ['<circle cx="52" cy="12" r="10" fill="%s" stroke="%s" stroke-width="2"/>' % (QUICK_FILL, QUICK_LINE),
            '<polygon points="%s" fill="%s" stroke="%s" stroke-width="1" stroke-linejoin="round"/>'
            % (bolt, WHITE, QUICK_LINE)]


def svg(body, width=SIZE, height=SIZE):
    return "\n".join(['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
                      % (width, height, width, height),
                      "  <!-- Written by tools/make_icons.py; change the script, not this file. -->"]
                     + ["  " + element for element in body] + ["</svg>", ""])


def workbench():
    return bed() + part_shape() + fin_shapes()


def icons():
    tilted_from = ('<rect x="2" y="36" width="20" height="20" fill="none" stroke="%s" stroke-width="1.5" '
                   'stroke-dasharray="3 2"/>' % BED)
    tilt_arrow = ['<path d="M14 30 A20 20 0 0 1 30 14" fill="none" stroke="%s" stroke-width="3" '
                  'stroke-linecap="round"/>' % FIN_FILL,
                  '<polygon points="30,8 37,14 29,19" fill="%s"/>' % FIN_FILL]
    # Lay flat again: the same picture backwards, the tilted part dashed and the
    # flat one solid, the arrow mirrored about the diagonal so it points down.
    laid_flat = ('<rect x="2" y="36" width="20" height="20" fill="%s" stroke="%s" stroke-width="1.5"/>'
                 % (PART_FILL, PART_LINE))
    tilted_outline = [element.replace('fill="%s"' % PART_FILL, 'fill="none"')
                      .replace('stroke="%s"' % PART_LINE, 'stroke="%s" stroke-dasharray="3 2"' % BED)
                      for element in part_shape()]
    lay_arrow = ['<path d="M30 14 A20 20 0 0 0 14 30" fill="none" stroke="%s" stroke-width="3" '
                 'stroke-linecap="round"/>' % FIN_FILL,
                 '<polygon points="8,30 14,37 19,29" fill="%s"/>' % FIN_FILL]
    paper = ['<polygon points="8,2 40,2 54,16 54,62 8,62" fill="%s" stroke="%s" stroke-width="2" '
             'stroke-linejoin="round"/>' % (PAPER, BED),
             '<polyline points="40,2 40,16 54,16" fill="none" stroke="%s" stroke-width="2" '
             'stroke-linejoin="round"/>' % BED]
    small = '<g transform="translate(6,8) scale(0.72)">%s</g>' % "".join(part_shape() + fin_shapes())

    def label(text):
        return ('<text x="31" y="57" font-family="sans-serif" font-size="11" font-weight="bold" '
                'text-anchor="middle" fill="%s">%s</text>' % (PART_LINE, text))

    return {
        "finsnap.svg": workbench(),
        "add_fins.svg": workbench() + plus_badge(),
        "quick_fins.svg": workbench() + bolt_badge(),
        "counter_fin.svg": bed() + part_shape() + fin_shapes() + fin_shapes(mirrored=True) + plus_badge(),
        "tilt.svg": bed() + [tilted_from] + part_shape() + tilt_arrow,
        "lay_flat.svg": bed() + tilted_outline + [laid_flat] + lay_arrow,
        "export_3mf.svg": paper + [small, label("3MF")],
        "export_step.svg": paper + [small, label("STEP")],
    }


def logo():
    """The workbench icon, scaled up, with the name beside it, centred on the banner.

    The mark is cropped to what it shows (bed and part), so no empty margin of
    the icon pushes it off centre.
    """
    left, right = BED_LEFT, BED_LEFT + BED_WIDTH
    top, bottom = PART_CENTRE[1] - PART_HALF, BED_Y + BED_HEIGHT
    mark_w, mark_h = (right - left) * LOGO_SCALE, (bottom - top) * LOGO_SCALE
    name_w = LOGO_NAME_EM * LOGO_FONT_SIZE
    width = 2 * LOGO_PADDING + mark_w + LOGO_GAP + name_w
    height = 2 * LOGO_PADDING + mark_h
    mark = '<g transform="translate(%.1f,%.1f) scale(%s)">%s</g>' % (
        LOGO_PADDING - left * LOGO_SCALE, LOGO_PADDING - top * LOGO_SCALE, LOGO_SCALE, "".join(workbench()))
    name = ('<text x="%.1f" y="%.1f" dominant-baseline="central" textLength="%.1f" '
            'lengthAdjust="spacingAndGlyphs" font-family="sans-serif" font-size="%d" font-weight="bold">'
            '<tspan fill="%s">Fin</tspan><tspan fill="%s">Snap</tspan></text>'
            % (LOGO_PADDING + mark_w + LOGO_GAP, height / 2, name_w, LOGO_FONT_SIZE, FIN_FILL, PART_FILL))
    return svg([mark, name], width=round(width), height=round(height))


def main():
    for name, body in icons().items():
        with open(os.path.join(ICONS, name), "w", encoding="utf-8") as handle:
            handle.write(svg(body))
        print("written", name)
    os.makedirs(os.path.dirname(LOGO), exist_ok=True)
    with open(LOGO, "w", encoding="utf-8") as handle:
        handle.write(logo())
    print("written", os.path.relpath(LOGO, ROOT))


if __name__ == "__main__":
    main()
