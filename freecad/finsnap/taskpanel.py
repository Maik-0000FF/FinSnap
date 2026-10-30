# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Task panel to tune the parameters of a FinSnap object.

The form is generated from feature.PROPERTIES, one section per property
group, so it never falls out of step with the object. Each section folds
away and opens again as it was left.
"""

import functools
import html
import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from pivy import coin
from PySide import QtCore, QtGui, QtWidgets

from . import check
from . import defaults as d
from . import feature
from . import geometry
from . import handles
from . import limits
from . import overhang
from . import presets
from . import stability
from .i18n import QT_TRANSLATE_NOOP, translate
from .params import FinParams
from .paths import (ICON_CHECK_OUTDATED, ICON_CHECK_PART, ICON_COUNTER, ICON_REMOVE_COUNTER, ICON_REMOVE_FIN,
                    ICON_RESET_FINS, ICON_STABILITY, SIDE_VIEW, TOP_VIEW)
from .shapes import FACE_PREFIX, global_shape, outermost
from .version import NAME, application

# Upper limits of the input fields; generous, the geometry rejects nonsense.
MAX_LENGTH = 10000.0
MAX_INTEGER = 1000
MAX_RATIO = 10.0
LENGTH_DECIMALS = 3
# Half the last place a length field shows: a value closer than this is the one shown.
FIELD_TOLERANCE = 0.5 * 10 ** -LENGTH_DECIMALS
RATIO_DECIMALS = 2
LENGTH_SUFFIX = " mm"
# A checkbox shown in a tooltip, as for the standard it goes back to.
SHOWN_ON = QT_TRANSLATE_NOOP("FinSnap", "on")
SHOWN_OFF = QT_TRANSLATE_NOOP("FinSnap", "off")
DEGREE_SUFFIX = " \N{DEGREE SIGN}"
# Pause after the last change before the preview is rebuilt, so typing a
# number does not rebuild the fins at every keystroke.
PREVIEW_DELAY_MS = 400
# The keys that end typing in a field.
ENTER_KEYS = (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter)
# Pause after the last move of a handle before the preview for it is built.
DRAG_PREVIEW_MS = 150
# Places of fins whose arrow ends are kept while the panel is open; beyond
# these the oldest goes.
ENDS_KEPT = 32
# How near a tine a fin dragged up or down goes to it (mm); farther from
# every tine, it is shown yellow where it is dragged and goes to the nearest
# when let go.
HEIGHT_REACH = 1.0
# Rows the list of fins shows at most; more fins scroll.
FIN_LIST_ROWS = 6
# Pause after the arrows are put on a fin before trying where it can go, so a
# run of rebuilds tries only once, after the last.
ENDS_DELAY_MS = 300
# How close a fin let go beyond where it can stand comes to that limit, and
# how far an arrow end looks ahead before it is left out (mm).
SNAP_RESOLUTION = 0.1
# The lowest a fin dragged down is previewed, so the preview never flattens
# to nothing or turns over (mm).
MIN_PREVIEW_HEIGHT = 0.1
NOTE_CLICK_FIN = QT_TRANSLATE_NOOP("FinSnap", "Click a fin of these fins in the 3D view first.")
# The fields of the fin with the arrows, as (label, tooltip, suffix, decimals,
# lowest, highest, whether it wraps round): where it stands along the face, or
# round the side of a cylinder or tube, and how high it is.
FIN_FIELD_PLACE = (QT_TRANSLATE_NOOP("FinSnap", "Place on the face"),
                   QT_TRANSLATE_NOOP("FinSnap", "Distance of the middle of the fin from the left end of the face, "
                                     "seen from outside. Type a value to move the fin there."),
                   LENGTH_SUFFIX, LENGTH_DECIMALS, -MAX_LENGTH, MAX_LENGTH, False)
ANGLE_DECIMALS = 2
FIN_FIELD_ANGLE = (QT_TRANSLATE_NOOP("FinSnap", "Angle on the part"),
                   QT_TRANSLATE_NOOP("FinSnap", "Position of the fin around the cylinder or tube, measured at the "
                                     "middle of its tines, in degrees from 0°, where it is first placed. Type a "
                                     "value to turn the part to it; the fin keeps its place."),
                   DEGREE_SUFFIX, ANGLE_DECIMALS, 0.0, geometry.FULL_CIRCLE, True)
FIN_FIELD_HEIGHT = (QT_TRANSLATE_NOOP("FinSnap", "Height"),
                    QT_TRANSLATE_NOOP("FinSnap", "Height of this fin alone. Type a value to set it; Reset fins "
                                      "gives it the height of the others again."),
                    LENGTH_SUFFIX, LENGTH_DECIMALS, -MAX_LENGTH, MAX_LENGTH, False)
# Half the last place the angle field shows: an angle closer than this is the one shown.
ANGLE_TOLERANCE = 0.5 * 10 ** -ANGLE_DECIMALS
SIDES = {feature.MAIN: QT_TRANSLATE_NOOP("FinSnap", "Main fin"),
         feature.COUNTER: QT_TRANSLATE_NOOP("FinSnap", "Counter fin")}
# FinParams field of the layer height, the step of the fields on the layer grid.
LAYER_FIELD = "layer_height"
# Notes below the result: warnings in amber, a refusal in red, each in a framed
# box with a sign, so they stand out from the result line above.
WARNING_COLOR = "#e0a000"
ERROR_COLOR = "#d03030"
# A stability check that finds the part standing, and one out of date.
STANDS_COLOR = "#30a050"
OUTDATED_COLOR = "#808080"
NOTE_STYLE = "QLabel { border: 2px solid %s; border-radius: 4px; padding: 6px; }"
WARNING_SIGN = "⚠"
# A field whose value differs from the standard for new fins: its label in
# this colour, and a button beside it that puts the standard value back.
MODIFIED_COLOR = "#e07000"
MODIFIED_STYLE = "QLabel { color: %s; font-weight: bold; }" % MODIFIED_COLOR
MODIFIED_HEADER_STYLE = "QToolButton { color: %s; }" % MODIFIED_COLOR
# The sections of the panel fold away under a flat header in bold; whether
# each is open is kept in this group of the preferences.
SECTION_HEADER_STYLE = "QToolButton { border: none; font-weight: bold; }"
SECTION_PREFERENCES = presets.PREFERENCES + "/PanelSections"
# The section to edit the fins in, open the first time, as it holds what is
# most often changed; the others start folded away.
EDIT_SECTION = QT_TRANSLATE_NOOP("FinSnap", "Edit fins")
RESET_SIGN = "↺"
# Icon buttons: icon size, the gap to the text and the margin inside, in pixels.
BUTTON_ICON_SIZE = 20
ICON_GAP = 8
BUTTON_PADDING = 6
# The ways Quick fins found to stand the part, one row each at the top of the
# panel, chosen with a click: the edge it stands on or the face the fins go
# under, by its name on the part as FreeCAD shows it, its length or area, and
# how many islands the part has standing so.
STAND_CAPTION = QT_TRANSLATE_NOOP("FinSnap", "Stand")
# A way whose edge is not found on the part by name is shown by its row.
STAND_ROW = "#%d"
STAND_RATED = (QT_TRANSLATE_NOOP("FinSnap", "Islands"), QT_TRANSLATE_NOOP("FinSnap", "Overhangs"),
               QT_TRANSLATE_NOOP("FinSnap", "Bridges"))
STAND_HEADERS = {True: (QT_TRANSLATE_NOOP("FinSnap", "Stands on"), QT_TRANSLATE_NOOP("FinSnap", "Length"))
                 + STAND_RATED,
                 False: (QT_TRANSLATE_NOOP("FinSnap", "Fins under"), QT_TRANSLATE_NOOP("FinSnap", "Area"))
                 + STAND_RATED}
# A cell of the table rated critical or not printable is shaded so; its
# tooltip says how many of each, the bridges by their longest span.
STAND_LEVEL_COLORS = {limits.CRITICAL: WARNING_COLOR, limits.UNPRINTABLE: ERROR_COLOR}
STAND_OVERHANGS_TIP = QT_TRANSLATE_NOOP("FinSnap", "%d faces overhang critically, %d too flat to print.")
STAND_BRIDGES = "%d (%.1f%s)"
STAND_BRIDGES_TIP = QT_TRANSLATE_NOOP("FinSnap", "%d bridges span critically, %d too far to print.")
AREA_SUFFIX = " mm\N{SUPERSCRIPT TWO}"
STAND_TIP = QT_TRANSLATE_NOOP("FinSnap", "Quick fins found more than one way to stand the part. Click a row to "
                                         "stand it so; the part and its fins follow in the 3D view. Ways where "
                                         "the part would start printing in the air, an island, or where a face "
                                         "lies too flat or a bridge spans too far to print, are left out while "
                                         "one without is found. Overhangs counts the faces overhanging without "
                                         "fins, Bridges those spanning too far, with the longest span in "
                                         "brackets; yellow is critical, red not printable.")
STAND_ASK = QT_TRANSLATE_NOOP("FinSnap", "Stand the part another way? The fins are planned anew: fins removed, "
                                         "moved or set to a height of their own, a turn of the part and the "
                                         "counter fin are undone.")
# Rows the table of ways shows at most; more scroll.
STAND_ROWS = 6
# What a stability check found, in the colours of the fins while editing: green
# where the part stands, yellow where only just, red where it tips; and the
# label of the layer its plumb line is shown for, counted from 1, beside it.
LEVEL_COLORS = {feature.STANDS: handles.VALID_COLOR, feature.CLOSE: handles.BETWEEN_COLOR,
                feature.TIPS: handles.INVALID_COLOR}
LAYER_TIPS = QT_TRANSLATE_NOOP("FinSnap", "Tips at layer %d, %.1f mm high")
LAYER_CLOSEST = QT_TRANSLATE_NOOP("FinSnap", "Closest to tipping at layer %d, %.1f mm high")
# What the colours of a stability check mean, said with its result.
NOTE_COLOURS = QT_TRANSLATE_NOOP(
    "FinSnap", "Colours by height: green stands, yellow comes within %.0f mm of tipping, red tips from there.")
# The one way a check in the tree is shown in the 3D view.
CHECK_DISPLAY_MODE = "Check"
# The part coloured by height in a stability check, this see-through.
GRADIENT_TRANSPARENCY = 0.5
# The lines of Check part, one for each check.
NOTE_OVERHANGS = QT_TRANSLATE_NOOP("FinSnap", "%d faces overhang flatter than %.0f degrees from the bed without "
                                             "fins.")
NOTE_UNPRINTABLE = QT_TRANSLATE_NOOP("FinSnap", "%d faces overhang flatter than %.0f degrees from the bed without "
                                               "fins, too flat to print.")
NOTE_NO_OVERHANGS = QT_TRANSLATE_NOOP("FinSnap", "No face overhangs without fins.")
NOTE_ISLANDS_FOUND = QT_TRANSLATE_NOOP("FinSnap", "%d island(s): it would start printing in the air there.")
NOTE_NO_ISLANDS = QT_TRANSLATE_NOOP("FinSnap", "No islands.")
NOTE_NO_BRIDGES = QT_TRANSLATE_NOOP("FinSnap", "No bridge spans further than %.1f mm.")
# The frame of the note of a stability check in the task panel, by what was
# found; OUTDATED_COLOR once a change has made it out of date.
STABILITY_FRAMES = {feature.STANDS: STANDS_COLOR, feature.CLOSE: WARNING_COLOR, feature.TIPS: ERROR_COLOR}
STABILITY_TIP = QT_TRANSLATE_NOOP(
    "FinSnap", "Checks whether the part stays standing while it is printed, layer by layer, on its own and "
    "held by these fins, which hold it only from their lowest tine up, and shows the plumb line from its "
    "centre of mass to the bed. Takes a moment on a large part.")
NOTE_STABILITY_OUTDATED = QT_TRANSLATE_NOOP("FinSnap", "Changed since the stability check: check again.")
# Said on a double click on a check whose part is gone.
NOTE_PART_GONE = QT_TRANSLATE_NOOP("FinSnap", "The part of this check is gone; delete the check.")
DRAWINGS = (
    (SIDE_VIEW, QT_TRANSLATE_NOOP("FinSnap", "Side view")),
    (TOP_VIEW, QT_TRANSLATE_NOOP("FinSnap", "Top view")),
)


def check_stability(part_obj, p):
    """Check whether `part_obj` stays standing while it is printed in the
    layers of `p` (feature.stability_of()), and keep what was found in its
    stability check in the tree (check.record()), which shows it. Returns the
    level and the note found."""
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    try:
        level, note, shown = feature.stability_of(part_obj, p)
        note = _with_colours(note, shown)
        _in_tree(check.record(part_obj, fins_on(part_obj), check.STABILITY, level, note, shown,
                              _layer_cut(part_obj, p, shown)))
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()
    return level, note


def check_part(part_obj, p):
    """Check `part_obj` as it stands for everything that keeps it from
    printing: faces overhanging without fins, bridges, islands and whether it
    stays standing, in the layers and beads of `p`, and keep it in its part
    check in the tree, which shows it. Returns the level of the worst found,
    and a note with a line for each check."""
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    try:
        part = global_shape(part_obj)
        rated = feature.overhangs_of(part_obj, part_obj.Document, p)
        unprintable = [name for name, level in rated if level == limits.UNPRINTABLE]
        spans = feature.bridges_of(part_obj, part_obj.Document, p)
        found = overhang.islands(part, p.first_layer_height, p.layer_height)
        level, note, shown = feature.stability_of(part_obj, p)
        rating = limits.current()
        critical = len(rated) - len(unprintable)
        lines = []
        if critical:
            lines.append(translate("FinSnap", NOTE_OVERHANGS) % (critical, rating.overhang_critical))
        if unprintable:
            lines.append(translate("FinSnap", NOTE_UNPRINTABLE) % (len(unprintable), rating.overhang_unprintable))
        if not rated:
            lines.append(translate("FinSnap", NOTE_NO_OVERHANGS))
        lines += _bridge_lines(part_obj, spans)
        lines.append(translate("FinSnap", NOTE_ISLANDS_FOUND) % len(found) if found
                     else translate("FinSnap", NOTE_NO_ISLANDS))
        lines.append(_with_colours(note, shown))
        # Faces too flat to print, bridges too long and islands keep the part
        # from printing; critical ones are a risk, as coming close to tipping is.
        levels = {rated_level for _, rated_level in rated} | {spanned.level for spanned in spans}
        worst = (feature.TIPS if limits.UNPRINTABLE in levels or found
                 else feature.CLOSE if limits.CRITICAL in levels and level == feature.STANDS else level)
        overhangs = [(part.getElement(name), rated_level) for name, rated_level in rated]
        # The level of its stability, whose colour its plumb line shows.
        _in_tree(check.record(part_obj, fins_on(part_obj), check.PART, level, "\n".join(lines), shown,
                              _layer_cut(part_obj, p, shown), overhangs, found, spans))
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()
    return worst, "\n".join(lines)


def check_bridges(part_obj, p):
    """Check `part_obj` as it stands for bridges, in the layers and beads of
    `p`, and keep them in its bridge check in the tree, which shows them.
    Returns the level of the longest found, as those of a stability check,
    and a note."""
    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
    try:
        spans = feature.bridges_of(part_obj, part_obj.Document, p)
        levels = {spanned.level for spanned in spans}
        level = (feature.TIPS if limits.UNPRINTABLE in levels
                 else feature.CLOSE if limits.CRITICAL in levels else feature.STANDS)
        note = "\n".join(_bridge_lines(part_obj, spans))
        _in_tree(check.record(part_obj, fins_on(part_obj), check.BRIDGES, level, note, None, bridges=spans))
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()
    return level, note


def _bridge_lines(part_obj, spans):
    """The lines saying what the bridges `spans` of `part_obj` are, by level;
    one saying none spans too far where none does."""
    lines = [note for note, _ in feature.bridge_notes(part_obj, spans)]
    return lines or [translate("FinSnap", NOTE_NO_BRIDGES) % limits.current().bridge_critical]


def fins_on(part_obj):
    """The FinSnap objects whose fins stand under `part_obj`."""
    return [other for other in feature.fins_of(outermost(part_obj), part_obj.Document)
            if other.Base and other.Base[0] is part_obj]


def check_params(part_obj):
    """The parameters to check `part_obj` with: those of its first fins, or
    the standard for new fins where it has none."""
    fins = fins_on(part_obj)
    return feature.params_of(fins[0]) if fins else presets.standard()


def check_again(check_obj):
    """Check the part of `check_obj`, a check in the tree, again, as it was
    checked: its stability, its bridges or the whole part. Returns the note
    found."""
    part_obj = check_obj.Part
    run = {check.PART: check_part, check.BRIDGES: check_bridges}.get(check_obj.Kind, check_stability)
    return run(part_obj, check_params(part_obj))[1]


def _in_tree(check_obj):
    """Give `check_obj` its look in the tree and the 3D view, where it has no
    look of its own yet: it was just made."""
    view = getattr(check_obj, "ViewObject", None)
    if view is not None and not isinstance(getattr(view, "Proxy", None), ViewProviderCheck):
        ViewProviderCheck(view)


class ViewProviderCheck:
    """The look of a check in the tree (check.py): its marks in the 3D view,
    shown and hidden with the eye, while it is up to date; its icon, with a
    warning once it is out of date; a double click checks again and says what
    it found."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        vobj.addDisplayMode(self.root, CHECK_DISPLAY_MODE)
        self.draw()

    def getDisplayModes(self, vobj):  # noqa: N802 - FreeCAD API
        return [CHECK_DISPLAY_MODE]

    def getDefaultDisplayMode(self):  # noqa: N802 - FreeCAD API
        return CHECK_DISPLAY_MODE

    def setDisplayMode(self, mode):  # noqa: N802 - FreeCAD API
        return mode

    def updateData(self, obj, prop):  # noqa: N802 - FreeCAD API
        if prop in check.SHOWN:
            self.draw()
        if prop == check.OUT_OF_DATE and obj.ViewObject is not None:
            obj.ViewObject.signalChangeIcon()

    def draw(self):
        """Show the marks of the check as it stands now."""
        if not hasattr(self, "root"):
            return
        self.root.removeAllChildren()
        for node in check_nodes(self.Object):
            self.root.addChild(node)

    def getIcon(self):  # noqa: N802 - FreeCAD API
        obj = getattr(self, "Object", None)
        if obj is not None and obj.OutOfDate:
            return ICON_CHECK_OUTDATED
        return ICON_CHECK_PART if obj is not None and obj.Kind == check.PART else ICON_STABILITY

    def doubleClicked(self, vobj):  # noqa: N802 - FreeCAD API
        if vobj.Object.Part is None:
            note = translate("FinSnap", NOTE_PART_GONE)
        else:
            note = check_again(vobj.Object)
        QtWidgets.QMessageBox.information(Gui.getMainWindow(), NAME, note)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None


def _layer_cut(part_obj, p, shown):
    """The layer of `shown`, a stability.Stability of `part_obj` in the layers
    of `p`, cut out of the part at the middle of that layer; None for none."""
    if shown is None:
        return None
    return stability.section(global_shape(part_obj), shown.foot.z + shown.height - p.layer_height / 2)


def check_nodes(check_obj):
    """The Coin nodes showing `check_obj`, a check in the tree (check.py): the
    part coloured by height from green, where it stands, over yellow, where
    it comes close to tipping, to red, where it tips; the layer it tips at,
    or comes closest to tipping at, cut out of it; the plumb line of that
    layer over what it stands on; and for a check of the part, the faces
    overhanging without fins and the islands. None for a check out of date,
    whose marks no longer tell the truth."""
    if check_obj.OutOfDate or check_obj.Part is None:
        return []
    nodes = []
    if check_obj.Footprint:
        bed = check_obj.Foot.z
        profile = [(bed + height, margin) for height, margin in zip(check_obj.ProfileHeights,
                                                                    check_obj.ProfileMargins)]

        # Checks saved by an older version rated by the built-in margin.
        close = check_obj.TippingMargin if "TippingMargin" in check_obj.PropertiesList else d.STABILITY_CLOSE

        def color_at(z):
            return margin_color(_margin_at(profile, z), close)

        color = LEVEL_COLORS.get(check_obj.Level, handles.INVALID_COLOR)
        nodes.append(handles.gradient(global_shape(check_obj.Part), color_at, [z for z, _ in profile],
                                      GRADIENT_TRANSPARENCY))
        if not check_obj.Cut.isNull():
            nodes.append(handles.layer_cut(check_obj.Cut, color))
        shown = stability.Stability(check_obj.Tips, check_obj.Layer, check_obj.Height, check_obj.Centre,
                                    check_obj.Foot, check_obj.Margin, None, list(check_obj.Footprint), profile)
        label = translate("FinSnap", LAYER_TIPS if check_obj.Tips else LAYER_CLOSEST) % (check_obj.Layer + 1,
                                                                                        check_obj.Height)
        # Beside the layer cut out, where the plumb line passes it.
        at = App.Vector(check_obj.Foot.x, check_obj.Foot.y, bed + check_obj.Height)
        nodes.append(handles.plumb(shown, color, label, at))
    # Checks saved by an older version kept every overhanging face in
    # Overhangs, all of them shown red then.
    older = "UnprintableOverhangs" not in check_obj.PropertiesList
    for shape, level in ((check_obj.Overhangs, limits.UNPRINTABLE if older else limits.CRITICAL),
                         (getattr(check_obj, "UnprintableOverhangs", Part.Shape()), limits.UNPRINTABLE)):
        if not shape.isNull():
            nodes.append(handles.overhang_faces(shape.Faces, level))
    for level, name in check.BRIDGE_PROPERTIES.items():
        regions = getattr(check_obj, name, Part.Shape())
        if not regions.isNull():
            nodes.append(handles.bridge_regions(regions, level))
    if not check_obj.IslandLayers.isNull():
        nodes.append(handles.island_layers(check_obj.IslandLayers))
    if check_obj.IslandsUncut:
        nodes.append(handles.island_spots(list(check_obj.IslandsUncut)))
    return nodes


def _longest_span(spans):
    """The bridges `spans` that span too far, as the table of ways shows them:
    how many, and the longest span in brackets, "1 (17.9 mm)"; 0 where none
    does, None where not checked."""
    if spans is None:
        return None
    far = [found.span for found in spans if found.level != limits.GOOD]
    return STAND_BRIDGES % (len(far), max(far), LENGTH_SUFFIX) if far else 0


def _rated_cell(levels, shown, tip):
    """A cell of the table of ways showing `shown`, blank for None, shaded by
    the worst of `levels`, limits.CRITICAL or UNPRINTABLE, its tooltip `tip`
    saying how many of each."""
    cell = QtWidgets.QTableWidgetItem("" if shown is None else str(shown))
    if levels:
        for level in (limits.UNPRINTABLE, limits.CRITICAL):
            if level in levels:
                cell.setBackground(QtGui.QColor(STAND_LEVEL_COLORS[level]))
                break
        cell.setToolTip(translate("FinSnap", tip) % (levels.count(limits.CRITICAL), levels.count(limits.UNPRINTABLE)))
    return cell


def _with_colours(note, shown):
    """`note`, followed by what the colours of the part mean, where they show."""
    if shown is None:
        return note
    return note + "\n" + translate("FinSnap", NOTE_COLOURS) % limits.current().tipping_margin


def _margin_at(profile, z):
    """The margin at height `z`, between those of `profile`, (height, margin)
    pairs from the bed up; that of the nearest end beyond them."""
    if z <= profile[0][0]:
        return profile[0][1]
    for (low, below), (high, above) in zip(profile, profile[1:]):
        if z <= high:
            share = (z - low) / (high - low) if high > low else 1.0
            return below + (above - below) * share
    return profile[-1][1]


def margin_color(margin, close):
    """The colour of a layer whose plumb line lies `margin` mm inside its
    footprint: green from `close`, the tipping margin, on, blended over to
    yellow at 0, red below, where it tips. A margin of 0 leaves no yellow."""
    if margin < 0:
        return handles.INVALID_COLOR
    share = min(1.0, margin / close) if close > 0 else 1.0
    return tuple(at_risk + (stands - at_risk) * share
                 for at_risk, stands in zip(handles.BETWEEN_COLOR, handles.VALID_COLOR))


def discard_created(obj, on_cancel=None):
    """Delete the fins `obj` a command just made, then call `on_cancel` to undo
    what the command did besides: Cancel in the panel, and a panel that could
    not open. One step on the undo stack, after the one that made the fins; a
    failure in between leaves no transaction open for the next action."""
    doc = obj.Document
    doc.openTransaction(translate("FinSnap", "Cancel fins"))
    try:
        # Fins just made stood at no turn: a part turned about its round side
        # in the panel turns back, in the same step.
        if feature.on_round_side(obj):
            feature.set_round_shift(obj, 0.0)
        doc.removeObject(obj.Name)
        if on_cancel is not None:
            on_cancel()
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    doc.recompute()


class Section(QtWidgets.QWidget):
    """A section of the panel that folds away: a header to click, with an
    arrow and the caption, and below it `content`, the widget it holds.
    Whether it is open is kept under `key` in FinSnap's preferences, so the
    panel opens as it was left; never opened or closed, it is `open_first`."""

    def __init__(self, caption, key, open_first):
        super().__init__()
        self.key = key
        self.header = QtWidgets.QToolButton()
        self.header.setText(caption)
        self.header.setCheckable(True)
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.header.setStyleSheet(SECTION_HEADER_STYLE)
        self.content = QtWidgets.QGroupBox()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.header)
        layout.addWidget(self.content)
        self.header.setChecked(App.ParamGet(SECTION_PREFERENCES).GetBool(key, open_first))
        self.show_open(self.header.isChecked())
        self.header.toggled.connect(self.toggled)

    def show_open(self, opened):
        self.header.setArrowType(QtCore.Qt.DownArrow if opened else QtCore.Qt.RightArrow)
        self.content.setVisible(opened)

    def toggled(self, opened):
        self.show_open(opened)
        App.ParamGet(SECTION_PREFERENCES).SetBool(self.key, opened)

    def mark(self, modified):
        """Mark the header while a field in it differs from the standard,
        so a change stays in sight with the section folded away."""
        self.header.setStyleSheet(SECTION_HEADER_STYLE + (MODIFIED_HEADER_STYLE if modified else ""))


class EnterTakes(QtCore.QObject):
    """Takes Enter in a field as the value typed, by calling `take`, and keeps
    it from the task dialog, which would close the panel on it."""

    def __init__(self, take, parent):
        super().__init__(parent)
        self.take = take

    def eventFilter(self, watched, event):  # noqa: N802 - Qt's name
        if event.type() == QtCore.QEvent.KeyPress and event.key() in ENTER_KEYS:
            watched.interpretText()
            self.take()
            return True
        return False


def _icon_button(icon, text):
    """A button with its icon and text side by side, flush left, a fixed gap
    between them, so the buttons of a group line up."""
    button = QtWidgets.QPushButton()
    # The text lives in a label of its own; the button still needs it as its name.
    button.setAccessibleName(text)
    row = QtWidgets.QHBoxLayout(button)
    row.setContentsMargins(BUTTON_PADDING, BUTTON_PADDING, BUTTON_PADDING, BUTTON_PADDING)
    row.setSpacing(ICON_GAP)
    picture = QtWidgets.QLabel()
    picture.setPixmap(QtGui.QIcon(icon).pixmap(BUTTON_ICON_SIZE, BUTTON_ICON_SIZE))
    label = QtWidgets.QLabel(text)
    for part in (picture, label):
        # The button takes the clicks, not its parts.
        part.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        row.addWidget(part)
    row.addStretch(1)
    button.setMinimumHeight(row.sizeHint().height())
    return button


def _wrapped(*paragraphs):
    """A tooltip Qt wraps: plain text it shows on one line however long, rich
    text it breaks to a readable width. Each paragraph its own."""
    return "".join("<p>%s</p>" % html.escape(paragraph) for paragraph in paragraphs)


def _widget(prop, value):
    if prop.kind == feature.CHOICE:
        box = QtWidgets.QComboBox()
        for choice in prop.choices:
            box.addItem(translate("FinSnap", feature.CHOICE_LABELS[choice]), choice)
    elif prop.kind == feature.BOOL:
        box = QtWidgets.QCheckBox()
    elif prop.kind == feature.INTEGER:
        box = QtWidgets.QSpinBox()
        box.setRange(0, MAX_INTEGER)
    else:
        box = QtWidgets.QDoubleSpinBox()
        if prop.kind == feature.LENGTH:
            box.setRange(0, MAX_LENGTH)
            box.setDecimals(LENGTH_DECIMALS)
            box.setSuffix(LENGTH_SUFFIX)
        else:
            box.setRange(0, MAX_RATIO)
            box.setDecimals(RATIO_DECIMALS)
        if prop.step not in (None, feature.STEP_LAYER):
            box.setSingleStep(prop.step)
    _write(prop, box, value)
    return box


def _write(prop, widget, value):
    if prop.kind == feature.CHOICE:
        widget.setCurrentIndex(prop.choices.index(value))
    elif prop.kind == feature.BOOL:
        widget.setChecked(bool(value))
    else:
        widget.setValue(value)


def _same(prop, first, second):
    if prop.kind in (feature.CHOICE, feature.BOOL):
        return first == second
    return abs(first - second) < d.TOLERANCE


def _shown(prop, value):
    """A value as the panel shows it, for a tooltip."""
    if prop.kind == feature.CHOICE:
        return translate("FinSnap", feature.CHOICE_LABELS[value])
    if prop.kind == feature.BOOL:
        return translate("FinSnap", SHOWN_ON if value else SHOWN_OFF)
    if prop.kind == feature.LENGTH:
        return "%g%s" % (value, LENGTH_SUFFIX)
    return "%g" % value


def _changed_signal(widget):
    if isinstance(widget, QtWidgets.QComboBox):
        return widget.currentIndexChanged
    if isinstance(widget, QtWidgets.QCheckBox):
        return widget.toggled
    return widget.valueChanged


def _read(prop, widget):
    if prop.kind == feature.CHOICE:
        return widget.currentData()
    if prop.kind == feature.BOOL:
        return widget.isChecked()
    return widget.value()


def _same_mm(a, b):
    """Whether two lengths in mm, each possibly None, are the same."""
    if a is None or b is None:
        return a is b
    return abs(a - b) < d.TOLERANCE


class FinSnapTaskPanel:
    def __init__(self, obj, created=False, on_cancel=None, stands=None):
        self.obj = obj
        # Fins just made: Cancel deletes them, then calls on_cancel, if any.
        self.created = created
        self.on_cancel = on_cancel
        # The ways Quick fins found to stand the part, if more than one.
        self.stands = stands if stands is not None and len(stands) > 1 else None
        self.widgets = {}
        self.labels = {}
        self.resets = {}
        self.standard = presets.standard()
        # The field whose value is the step of the fields on the layer grid.
        self.layer_prop = next(prop for prop in feature.PROPERTIES if prop.field == LAYER_FIELD)
        # Every change is written to the object at once; Cancel puts these back.
        self.original = {prop.name: feature.value_of(obj, prop.name) for prop in feature.PROPERTIES}
        # And what Edit fins changes: the fins removed, moved or set to a height
        # of their own, and the counter face. A property the fins do not have
        # yet counts as empty: nothing changed.
        self.original_edits = {name: getattr(obj, name, empty) for names, empty in
                               ((feature.REMOVED.values(), []), (feature.SHIFTS.values(), {}),
                                (feature.HEIGHTS.values(), {}), (feature.EDITED_OF.values(), 0))
                               for name in names}
        self.original_counter = obj.CounterFace
        # How far the part was turned about a round side by hand; Cancel turns it back.
        self.original_turn = feature.round_shift(obj)

        self.form = QtWidgets.QWidget()
        # A child of the form, so it goes with the panel and never fires on a
        # closed document.
        self.timer = QtCore.QTimer(self.form)
        self.timer.setSingleShot(True)
        self.timer.setInterval(PREVIEW_DELAY_MS)
        self.timer.timeout.connect(self.preview)
        self.drag_timer = QtCore.QTimer(self.form)
        self.drag_timer.setSingleShot(True)
        self.drag_timer.setInterval(DRAG_PREVIEW_MS)
        self.drag_timer.timeout.connect(self.drag_step)
        self.ends_timer = QtCore.QTimer(self.form)
        self.ends_timer.setSingleShot(True)
        self.ends_timer.setInterval(ENDS_DELAY_MS)
        self.ends_timer.timeout.connect(self.update_ends)
        # Takes a value typed into a field of the fin with the handles once
        # typing pauses, as the other fields do; the field typed into last.
        self.field_timer = QtCore.QTimer(self.form)
        self.field_timer.setSingleShot(True)
        self.field_timer.setInterval(PREVIEW_DELAY_MS)
        self.field_timer.timeout.connect(lambda: self.field_entered(self.typed_field, paused=True))
        self.typed_field = None
        # The field of the fin being typed into while its value is taken after
        # a pause: the panel leaves it as typed.
        self.typing = None
        # The fin with the handles on it, as (MAIN or COUNTER, number); the
        # arrow being dragged with how far, as (kind, mm); and the shift and
        # height of the fin, and the values in its fields, when it was grabbed.
        self.handled = None
        # The fin the ends of the arrows were last tried on.
        self.ends_of = None
        # The arrow ends found, by what they depend on (ends_key).
        self.known_ends = {}
        self.dragged = None
        self.drag_base, self.drag_own, self.drag_values = {}, {}, {}
        self.drag_mm_per_degree = None
        self.released = False
        # True while the panel fills the fields of the fin, not the user.
        self.filling_fields = False
        self.handles = handles.Handles(obj.ViewObject, self.handle_started, self.handle_moved, self.handle_done)
        # The fins keep their last build for the arrows while the panel is open.
        obj.Proxy.editing = True
        Gui.Selection.addObserver(self)
        self.form.setWindowTitle("%s (%s)" % (translate("FinSnap", "FinSnap parameters"), application()))
        layout = QtWidgets.QVBoxLayout(self.form)
        if self.stands is not None:
            layout.addWidget(self.stand_table())
        intro = QtWidgets.QLabel(translate(
            "FinSnap", "Hover over a field for an explanation. Letters in brackets point to the drawings "
            "below. Every change is shown in the 3D view right away. Greyed-out fields have no effect "
            "with the current choices; their tooltip says why."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        # The drawings always show, as the letters in the fields point to them.
        self.drawings = []
        for path, caption in DRAWINGS:
            box = QtWidgets.QGroupBox(translate("FinSnap", caption))
            picture = QtWidgets.QLabel()
            picture.setPixmap(QtGui.QPixmap(path))
            QtWidgets.QVBoxLayout(box).addWidget(picture)
            layout.addWidget(box)
            self.drawings.append(picture)

        # The sections below fold away, each kept by its caption untranslated.
        self.sections = {}
        groups = {}
        for prop in feature.PROPERTIES:
            if prop.group not in groups:
                section = self.add_section(layout, prop.group, translate("App::Property", prop.group))
                groups[prop.group] = QtWidgets.QFormLayout(section.content)
                info = QtWidgets.QLabel(translate("FinSnap", feature.GROUP_INFO[prop.group]))
                info.setWordWrap(True)
                groups[prop.group].addRow(info)
            widget = _widget(prop, feature.value_of(obj, prop.name))
            widget.setToolTip(_wrapped(translate("App::Property", prop.tip)))
            label = translate("FinSnap", prop.label)
            if prop.name in feature.MARKS:
                label = "%s (%s)" % (label, feature.MARKS[prop.name])
            self.labels[prop.name] = QtWidgets.QLabel(label)
            reset = QtWidgets.QToolButton()
            reset.setText(RESET_SIGN)
            reset.clicked.connect(functools.partial(self.back_to_standard, prop))
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(widget, 1)
            row_layout.addWidget(reset)
            groups[prop.group].addRow(self.labels[prop.name], row)
            self.widgets[prop.name] = widget
            self.resets[prop.name] = reset
            _changed_signal(widget).connect(self.changed)

        edit = self.add_section(layout, EDIT_SECTION, translate("FinSnap", EDIT_SECTION)).content
        edit_layout = QtWidgets.QGridLayout(edit)
        edit_info = QtWidgets.QLabel(translate(
            "FinSnap", "To remove one fin, click it in the 3D view and press Remove selected fin, or the "
            "Delete key. The counter fin goes on the face leaning the other way, or on a face of the part "
            "you select. Drag the two arrows on a fin to move it along the face or to change its height, "
            "or type the values below; click another fin, or pick it in the list of fins, to put the arrows "
            "there. Reset fins undoes every change by hand."))
        edit_info.setWordWrap(True)
        edit_layout.addWidget(edit_info, 0, 0, 1, 2)
        for column, row, icon, text, action in (
                (0, 1, ICON_REMOVE_FIN, QT_TRANSLATE_NOOP("FinSnap", "Remove selected fin"), self.remove_selected),
                (1, 1, ICON_RESET_FINS, QT_TRANSLATE_NOOP("FinSnap", "Reset fins"), self.reset),
                (0, 2, ICON_COUNTER, QT_TRANSLATE_NOOP("FinSnap", "Add counter fin"), self.add_counter),
                (1, 2, ICON_REMOVE_COUNTER, QT_TRANSLATE_NOOP("FinSnap", "Remove counter fin"),
                 self.remove_counter)):
            button = _icon_button(icon, translate("FinSnap", text))
            button.clicked.connect(action)
            edit_layout.addWidget(button, row, column)
        # Every fin built, one below the other; the one with the arrows is marked.
        # Picking one also reaches a fin behind the part.
        self.fin_list = QtWidgets.QListWidget()
        self.fin_list.setToolTip(_wrapped(translate("FinSnap", "The fins, the main fins from the left, then the "
                                                    "counter fins. Pick one to put the arrows on it and select it.")))
        # A changed row, by mouse or keyboard, and a click on the row already
        # marked, to pick that fin again once the selection went elsewhere.
        self.fin_list.currentRowChanged.connect(self.pick_fin)
        self.fin_list.itemClicked.connect(lambda item: self.pick_fin(self.fin_list.row(item)))
        self.listed_fins = []
        edit_layout.addWidget(self.fin_list, 3, 0, 1, 2)
        self.fin_label = QtWidgets.QLabel(translate("FinSnap", NOTE_CLICK_FIN))
        self.fin_label.setWordWrap(True)
        edit_layout.addWidget(self.fin_label, 4, 0, 1, 2)
        # Where the fin with the arrows stands, to read or to type in: taken
        # once typing pauses, at once with Enter or on leaving the field.
        self.fin_fields, self.fin_field_labels = {}, {}
        for row, kind in ((5, handles.ALONG), (6, handles.UP)):
            label = QtWidgets.QLabel()
            box = QtWidgets.QDoubleSpinBox()
            box.valueChanged.connect(functools.partial(self.field_typed, kind))
            box.editingFinished.connect(functools.partial(self.field_entered, kind))
            box.installEventFilter(EnterTakes(functools.partial(self.field_entered, kind), box))
            edit_layout.addWidget(label, row, 0)
            edit_layout.addWidget(box, row, 1)
            self.fin_fields[kind], self.fin_field_labels[kind] = box, label
            self.set_field(kind, FIN_FIELD_PLACE if kind == handles.ALONG else FIN_FIELD_HEIGHT)
        # Whether the field along the face takes the angle on a round side.
        self.angle_field = False

        standard_buttons = QtWidgets.QHBoxLayout()
        save = QtWidgets.QPushButton(translate("FinSnap", "Save as standard"))
        save.setToolTip(_wrapped(translate("FinSnap", "New fins start with these values. Fields that differ from "
                                                      "the standard are marked, and their button puts the "
                                                      "standard back.")))
        save.clicked.connect(self.save_standard)
        factory = QtWidgets.QPushButton(translate("FinSnap", "Factory settings"))
        factory.setToolTip(_wrapped(translate("FinSnap", "Forget the saved standard and set every field to the "
                                                         "built-in value.")))
        factory.clicked.connect(self.factory_settings)
        standard_buttons.addWidget(save)
        standard_buttons.addWidget(factory)
        layout.addLayout(standard_buttons)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notes = QtWidgets.QLabel()
        self.notes.setWordWrap(True)
        self.notes.setTextFormat(QtCore.Qt.RichText)
        # A note that names a place is a link: a click marks what it is about.
        self.notes.setTextInteractionFlags(QtCore.Qt.LinksAccessibleByMouse)
        self.notes.linkActivated.connect(self.show_note)
        self.notes.hide()
        layout.addWidget(self.notes)
        # Whether the part stays standing while it is printed: checked on
        # demand, as it takes a moment on a large part.
        stability_button = _icon_button(ICON_STABILITY, translate("FinSnap", "Check stability"))
        stability_button.setToolTip(_wrapped(translate("FinSnap", STABILITY_TIP)))
        stability_button.clicked.connect(self.check_stability)
        layout.addWidget(stability_button)
        self.stability = QtWidgets.QLabel()
        self.stability.setWordWrap(True)
        self.stability.hide()
        layout.addWidget(self.stability)
        # Whether the note below the button tells the result of a check that
        # still holds.
        self.stability_checked = False
        self.update_steps()
        self.update_enabled()
        self.update_marks()
        self.preview()

    def stand_table(self):
        """The section at the top that lists the ways Quick fins found to stand
        the part, one row each, the one it stands in now marked."""
        box = QtWidgets.QGroupBox(translate("FinSnap", STAND_CAPTION))
        headers = [translate("FinSnap", text) for text in STAND_HEADERS[self.stands.by_edge]]
        self.stand_list = QtWidgets.QTableWidget(len(self.stands), len(headers))
        self.stand_list.setHorizontalHeaderLabels(headers)
        self.stand_list.verticalHeader().hide()
        self.stand_list.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.stand_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.stand_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.stand_list.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.stand_list.setToolTip(_wrapped(translate("FinSnap", STAND_TIP)))
        self.fill_stands()
        shown = min(len(self.stands), STAND_ROWS)
        self.stand_list.setFixedHeight(self.stand_list.horizontalHeader().height()
                                       + shown * self.stand_list.rowHeight(0) + 2 * self.stand_list.frameWidth())
        self.stand_list.currentCellChanged.connect(lambda row, *_: self.choose_stand(row))
        self.show_stand()
        QtWidgets.QVBoxLayout(box).addWidget(self.stand_list)
        return box

    def fill_stands(self):
        """Fill the table of ways from the rows of the ways found."""
        suffix = LENGTH_SUFFIX if self.stands.by_edge else AREA_SUFFIX
        for row, (name, size, islands, overhangs, spans) in enumerate(self.stands.rows):
            # Ways not checked, with the checks while editing off, are left blank.
            cells = [QtWidgets.QTableWidgetItem(name or STAND_ROW % (row + 1)),
                     QtWidgets.QTableWidgetItem("%.1f%s" % (size, suffix)),
                     QtWidgets.QTableWidgetItem("" if islands is None else str(islands)),
                     _rated_cell(overhangs, None if overhangs is None else len(overhangs), STAND_OVERHANGS_TIP),
                     _rated_cell([found.level for found in spans] if spans is not None else None,
                                 _longest_span(spans), STAND_BRIDGES_TIP)]
            for column, cell in enumerate(cells):
                self.stand_list.setItem(row, column, cell)

    def rate_stands(self):
        """Rate the ways of the table where they were found unchecked, and show
        them; the row the part stands in stays marked."""
        if self.stands is None or not self.stands.unrated():
            return
        self.stands.rate()
        self.stand_list.blockSignals(True)
        self.fill_stands()
        self.stand_list.blockSignals(False)
        self.show_stand()

    def show_stand(self):
        """Mark the row of the way the part stands in now."""
        self.stand_list.blockSignals(True)
        self.stand_list.setCurrentCell(self.stands.current, 0)
        self.stand_list.blockSignals(False)

    def choose_stand(self, row):
        """Stand the part the way in `row` of the table. Changes by hand belong
        to the way before and go with it, once the user agrees; otherwise the
        mark goes back to the way it stands in."""
        if row < 0 or row == self.stands.current:
            return
        self.take_typed()
        if feature.changed_by_hand(self.obj):
            answer = QtWidgets.QMessageBox.question(self.form, translate("FinSnap", "Stand another way"),
                                                    translate("FinSnap", STAND_ASK))
            if answer != QtWidgets.QMessageBox.Yes:
                self.show_stand()
                return
        self.stands.stand(self.obj, row)
        # The fin with the arrows is chosen anew on the face as it stands now.
        self.handled = None
        self.show_stand()
        self.edited()

    def set_field(self, kind, spec):
        """Make the field of the handled fin for `kind` the one `spec` describes,
        FIN_FIELD_PLACE, FIN_FIELD_ANGLE or FIN_FIELD_HEIGHT."""
        text, tip, suffix, decimals, lowest, highest, wraps = spec
        box, label = self.fin_fields[kind], self.fin_field_labels[kind]
        self.filling_fields = True
        box.setDecimals(decimals)
        box.setSuffix(suffix)
        box.setRange(lowest, highest)
        box.setWrapping(wraps)
        self.filling_fields = False
        box.setToolTip(_wrapped(translate("FinSnap", tip)))
        label.setText(translate("FinSnap", text))
        label.setToolTip(box.toolTip())

    def current(self, name):
        """A field's value as entered; a link that is no field counts as set or not."""
        for prop in feature.PROPERTIES:
            if prop.name == name:
                return _read(prop, self.widgets[name])
        return bool(getattr(self.obj, name))

    def update_steps(self):
        """Fields on the layer grid step by the layer height entered."""
        layer = _read(self.layer_prop, self.widgets[self.layer_prop.name])
        for prop in feature.PROPERTIES:
            if prop.step == feature.STEP_LAYER and layer > 0:
                self.widgets[prop.name].setSingleStep(layer)

    def update_enabled(self):
        for prop in feature.PROPERTIES:
            notes = feature.unused_notes(prop.name, self.current)
            paragraphs = [translate("App::Property", prop.tip)]
            if notes:
                paragraphs.append(" ".join(translate("FinSnap", note) for note in notes))
            self.widgets[prop.name].setEnabled(not notes)
            self.widgets[prop.name].setToolTip(_wrapped(*paragraphs))
            self.labels[prop.name].setEnabled(not notes)

    def add_section(self, layout, key, caption):
        """A section under `caption` added to `layout`, kept as `key`."""
        section = Section(caption, key, key == EDIT_SECTION)
        layout.addWidget(section)
        self.sections[key] = section
        return section

    def update_marks(self):
        """Mark every field whose value differs from the standard for new fins,
        and the header of each section holding one."""
        modified_groups = set()
        for prop in feature.PROPERTIES:
            value = getattr(self.standard, prop.field)
            modified = not _same(prop, _read(prop, self.widgets[prop.name]), value)
            if modified:
                modified_groups.add(prop.group)
            self.labels[prop.name].setStyleSheet(MODIFIED_STYLE if modified else "")
            self.resets[prop.name].setVisible(modified)
            self.resets[prop.name].setToolTip(_wrapped(translate("FinSnap", "Back to the standard: %s")
                                                       % _shown(prop, value)))
        for group in {prop.group for prop in feature.PROPERTIES}:
            self.sections[group].mark(group in modified_groups)

    def back_to_standard(self, prop):
        _write(prop, self.widgets[prop.name], getattr(self.standard, prop.field))

    def save_standard(self):
        values = {prop.field: _read(prop, self.widgets[prop.name]) for prop in feature.PROPERTIES}
        try:
            presets.save(FinParams(**values))
        except ValueError as error:
            self.refuse(error)
            return
        self.standard = presets.standard()
        self.update_marks()

    def factory_settings(self):
        answer = QtWidgets.QMessageBox.question(
            self.form, translate("FinSnap", "Factory settings"),
            translate("FinSnap", "Forget the saved standard and set every field to the built-in value?"))
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        presets.reset()
        self.standard = presets.standard()
        for prop in feature.PROPERTIES:
            self.back_to_standard(prop)
        self.update_marks()

    def edited(self):
        """After a fin or the counter fin was removed or added: rebuild and show it."""
        self.update_enabled()
        self.preview()

    def selected_fins(self):
        """The fins of these fins picked in the 3D view, as (MAIN or COUNTER, number)."""
        fins = [feature.fin_at(self.obj, sub) for sel in Gui.Selection.getSelectionEx()
                if sel.Object is self.obj for sub in sel.SubElementNames]
        return [fin for fin in fins if fin]

    def remove_selected(self):
        self.remove_fins(self.selected_fins())

    def remove_fins(self, fins):
        """Remove the fins in `fins`, as (MAIN or COUNTER, number), from the
        button or the Delete key. The last main fins take the whole object
        with them, once the user agrees."""
        if self.obj.Connection == d.CONNECTION_MERGED:
            self.show_notes(translate("FinSnap", "Nothing removed"),
                            [translate("FinSnap", feature.NOTE_MERGED_SINGLE)], WARNING_COLOR)
            return
        if not fins:
            self.show_notes(translate("FinSnap", "Nothing removed"),
                            [translate("FinSnap", NOTE_CLICK_FIN)], WARNING_COLOR)
            return
        if not feature.remove_fins(self.obj, fins):
            self.edited()
            return
        answer = QtWidgets.QMessageBox.question(
            self.form, translate("FinSnap", "Delete the fins?"),
            translate("FinSnap", "These are the last fins. Delete the fins object? A part stood on an edge "
                      "for these fins alone is laid flat again."))
        if answer == QtWidgets.QMessageBox.Yes:
            self.delete_all()

    def close(self):
        """Close the panel as it is: on OK, on Cancel, or before the fins object goes."""
        self.timer.stop()
        self.release_handles()
        Gui.Control.closeDialog()
        self.leave_edit()

    def delete_all(self):
        """Close the panel and delete the fins object, as deleting it in the tree does."""
        self.close()
        doc = self.obj.Document
        doc.openTransaction(translate("FinSnap", "Delete fins"))
        feature.prepare_delete(self.obj)
        doc.removeObject(self.obj.Name)
        doc.commitTransaction()
        doc.recompute()

    def reset(self):
        if feature.on_round_side(self.obj):
            feature.set_round_shift(self.obj, 0.0)
        feature.reset_fins(self.obj)
        self.edited()

    def add_counter(self):
        part = self.obj.Base[0]
        faces = [name for sel in Gui.Selection.getSelectionEx() if sel.Object is part
                 for name in sel.SubElementNames if name.startswith(FACE_PREFIX)]
        try:
            found = feature.add_counter(self.obj, part, faces[0]) if faces else feature.add_counter(self.obj)
        except geometry.FinError as error:
            self.show_notes(translate("FinSnap", "No counter fin"),
                            [translate("FinSnap", feature.NOTE_NO_COUNTER_ON_FACE) % error], WARNING_COLOR)
            return
        if found is None:
            self.show_notes(translate("FinSnap", "No counter fin"),
                            [translate("FinSnap", feature.NOTE_NO_OPPOSITE)], WARNING_COLOR)
            return
        self.edited()

    def remove_counter(self):
        feature.remove_counter(self.obj)
        self.edited()

    def changed(self):
        self.update_enabled()
        self.update_steps()
        self.update_marks()
        self.timer.start()

    def apply(self):
        for prop in feature.PROPERTIES:
            setattr(self.obj, prop.name, _read(prop, self.widgets[prop.name]))
        # A failed build does not raise here; FreeCAD marks the object and
        # keeps the message, which the panel has to show.
        if not self.obj.recompute():
            raise ValueError(self.obj.getStatusString())

    def show_notes(self, title, lines, color, linked=()):
        """A framed box with a sign and a title, one line per note; hidden without
        notes. The notes whose index is in `linked` are links to show_note()."""
        if not lines:
            self.notes.hide()
            return

        def item(index, line):
            text = html.escape(line)
            return "<li><a href='%d'>%s</a></li>" % (index, text) if index in linked else "<li>%s</li>" % text
        items = "".join(item(index, line) for index, line in enumerate(lines))
        self.notes.setText("<b>%s %s</b><ul style='margin: 0'>%s</ul>" % (WARNING_SIGN, html.escape(title), items))
        self.notes.setStyleSheet(NOTE_STYLE % color)
        self.notes.show()

    def note_targets(self):
        """What each note of the last build is about, a feature.NoteTarget or
        None, in the order of Warnings; empty once they no longer match."""
        targets = list(getattr(self.obj.Proxy, "note_targets", []))
        return targets if len(targets) == len(self.obj.Warnings) else []

    def show_note(self, link):
        """A click on note `link`, its index: select what it is about, as Check
        Geometry does, mark what cannot be selected in the selection colour,
        and fit the view to it; the first fin it names gets the arrows.

        INPUTS this has to withstand:
          a note naming fins                    ->  their faces selected, the first fin
                                                    with the arrows
          a note naming the face or faces of
            the part                            ->  those faces selected, the fin kept
          a note naming tines left out or
            islands                             ->  marked, as they are no faces of any object;
                                                    an island without its first layer as a
                                                    ball at its lowest point
          a note naming a fin merged into the
            part                                ->  its body marked, as it has no faces of its own
          a fin named no longer built           ->  passed over
          an index the last build has no target
            for, or not a number                ->  selection and marks cleared, the view kept
        """
        targets = self.note_targets()
        target = targets[int(link)] if link.isdigit() and int(link) < len(targets) else None
        Gui.Selection.clearSelection()
        if target is None:
            self.handles.show_noted([])
            return
        results = getattr(self.obj.Proxy, "results", {})
        fins = [(target.which, number) for number in target.fins
                if results.get(target.which) and number in results[target.which].numbers]
        marks = list(target.marks)
        # What is selected, as shapes, to fit the view to it.
        selected = []
        for which, number in fins:
            faces = feature.fin_faces(self.obj, which, number)
            if faces:
                Gui.Selection.addSelection(self.obj, [FACE_PREFIX + str(index + 1) for index in faces])
                selected += [self.obj.Shape.Faces[index] for index in faces]
            else:
                built = results[which]
                marks.append(built.bodies[built.numbers.index(number)])
        for owner, name in target.faces:
            Gui.Selection.addSelection(owner, name)
            selected.append(global_shape(owner).getElement(name))
        self.handles.show_noted(marks, target.points)
        self.handles.fit(selected + marks, target.points)
        # After the selection, which gives the arrows to the fin picked last.
        if fins:
            self.take_typed()
            self.handled = fins[0]
            self.place_handles()

    def addSelection(self, doc, name, sub, point):  # noqa: N802 - FreeCAD API
        """A fin picked in the 3D view gets the handles."""
        try:
            mine = doc == self.obj.Document.Name and name == self.obj.Name
        except ReferenceError:
            # The fins were deleted with the panel still listening; it stops
            # once FreeCAD is through with the selection.
            QtCore.QTimer.singleShot(0, functools.partial(Gui.Selection.removeObserver, self))
            return
        if not mine:
            return
        # An arrow stands inside its see-through fin, so grabbing it picks the
        # fin as well; the arrows must not move while held.
        if self.handles.held:
            return
        fin = feature.fin_at(self.obj, sub)
        if fin and fin != self.handled:
            self.take_typed()
            self.handled = fin
            self.place_handles()

    def built_fins(self):
        """Every fin built, as (MAIN or COUNTER, number): the main fins from
        the left, then the counter fins."""
        results = getattr(self.obj.Proxy, "results", {})
        return [(which, number) for which in (feature.MAIN, feature.COUNTER) if results.get(which)
                for number in results[which].numbers]

    def fin_name(self, fin):
        """The name of `fin`, (MAIN or COUNTER, number), as the panel shows it: "Main fin 2"."""
        which, number = fin
        return translate("FinSnap", "%s %d") % (translate("FinSnap", SIDES[which]), number)

    def list_fins(self):
        """Show every fin built in the list, the one with the arrows marked."""
        fins = self.built_fins()
        self.fin_list.blockSignals(True)
        if fins != self.listed_fins:
            self.fin_list.clear()
            self.fin_list.addItems([self.fin_name(fin) for fin in fins])
            self.listed_fins = fins
            # As high as its rows, up to FIN_LIST_ROWS; more scroll.
            rows = min(len(fins), FIN_LIST_ROWS)
            self.fin_list.setFixedHeight(self.fin_list.sizeHintForRow(0) * rows + 2 * self.fin_list.frameWidth())
            self.fin_list.setVisible(bool(fins))
        self.fin_list.setCurrentRow(fins.index(self.handled) if self.handled in fins else -1)
        self.fin_list.blockSignals(False)

    def pick_fin(self, row):
        """A fin picked in the list: it gets the arrows and is selected, so
        Remove selected fin and the Delete key take this fin."""
        if row < 0 or row >= len(self.listed_fins) or self.handles.held:
            return
        # A click on a new row comes as a changed row as well; once is enough.
        if self.listed_fins[row] == self.handled and self.selected_fins() == [self.handled]:
            return
        self.take_typed()
        self.handled = self.listed_fins[row]
        Gui.Selection.clearSelection()
        face = feature.fin_face(self.obj, *self.handled)
        if face:
            Gui.Selection.addSelection(self.obj, face)
        self.place_handles()

    def handled_result(self):
        """The last build of the side of the fin with the handles, and the
        index of that fin in it; None while no fin built has them."""
        if self.handled is None:
            return None
        which, number = self.handled
        result = getattr(self.obj.Proxy, "results", {}).get(which)
        if result is None or number not in result.numbers:
            return None
        return result, result.numbers.index(number)

    def choose_fin(self):
        """The fin to put the handles on when none has them: the one selected,
        or else the first fin built."""
        picked = self.selected_fins()
        if picked:
            return picked[0]
        for which in (feature.MAIN, feature.COUNTER):
            result = getattr(self.obj.Proxy, "results", {}).get(which)
            if result is not None and result.numbers:
                return which, result.numbers[0]
        return None

    def fin_values(self):
        """Where the handled fin stands, from the last build: its middle from the
        start of the face along it (ALONG), in mm, or under a round side the
        angle of the middle of its tines round it, in degrees; and its height
        (UP), in mm."""
        result = self.handled_result()[0]
        number = self.handled[1]
        # The angle rounded as the field shows it: just below 360 is 0.
        along = (geometry.round_angle(geometry.side_angle(feature.round_side(self.obj)), ANGLE_TOLERANCE)
                 if self.turns_part()
                 else result.starts[number] + result.thickness / 2 - result.face_start)
        return {handles.ALONG: along, handles.UP: result.heights[number]}

    def turn_of_handles(self):
        """The axis of the round side the handled fin stands under, as a point
        on it and its direction, and how far the fin moves along the face (mm)
        for every degree the part turns about it, for handles.Handles.show()."""
        face = feature.round_side(self.obj)
        surface = face.Surface
        return App.Vector(surface.Center), App.Vector(surface.Axis).normalize(), geometry.turn_mm(face, 1.0)

    def place_handles(self):
        if self.handled_result() is None:
            self.handled = self.choose_fin()
        found = self.handled_result()
        enabled = found is not None
        for box in self.fin_fields.values():
            box.setEnabled(enabled)
        self.list_fins()
        if not enabled:
            self.handles.hide()
            self.fin_label.setText(translate("FinSnap", NOTE_CLICK_FIN))
            return
        result = found[0]
        which, number = self.handled
        turning = self.turns_part()
        if turning != self.angle_field:
            self.set_field(handles.ALONG, FIN_FIELD_ANGLE if turning else FIN_FIELD_PLACE)
            self.angle_field = turning
        # A held arrow stays where it was grabbed; only the numbers follow it.
        if not self.handles.held:
            self.handles.show(result.edges[number], result.along, result.out,
                              self.turn_of_handles() if turning else None)
            # On another fin, both ends until tried, rather than those of the fin before.
            if self.handled != self.ends_of:
                for kind in handles.KINDS:
                    self.handles.show_ends(kind, (handles.BACK, handles.FORTH))
            self.ends_timer.start()
        self.show_fin_values(self.fin_values())
        self.fin_label.setText(self.fin_name(self.handled))

    def show_fin_values(self, values):
        """Show `values` in the fields of the handled fin, without taking them as typed."""
        self.filling_fields = True
        for kind, value in values.items():
            # A field still being typed into keeps what is typed.
            if kind != self.typing:
                self.fin_fields[kind].setValue(value)
        self.filling_fields = False

    def turns_part(self):
        """Whether moving the handled fin along the face turns the part instead:
        the main fin under the round side of a cylinder or tube stays under its
        lowest line, and the part turns about its axis. Asked of the face, not
        of the last build, which a failed build leaves empty: a turn that fails
        is still turned back."""
        return self.handled is not None and self.handled[0] == feature.MAIN and feature.on_round_side(self.obj)

    def own_value(self, kind):
        """What the handled fin has by hand now: its shift along the face
        (ALONG) or its own height (UP), in mm, or None."""
        which, number = self.handled
        return feature.edits(self.obj, which)[1 if kind == handles.ALONG else 2].get(number)

    def write_fin(self, kind, value):
        """Store `value` as the shift (ALONG) or the own height (UP) of the
        handled fin; None takes it away."""
        which, number = self.handled
        if kind == handles.ALONG:
            if self.turns_part():
                feature.set_round_shift(self.obj, value or 0.0)
                return
            feature.set_fin_shift(self.obj, which, number, value or 0.0)
        else:
            feature.set_fin_height(self.obj, which, number, value)

    def set_fin(self, kind, value):
        """Give the handled fin the shift along the face (ALONG) or the height
        (UP) `value` and build the fins, once. Where it cannot stand so, the
        panel says why, the object is left as it was, and False is returned.

        Tried first with a build alone: written and then taken back, a place
        that fails would mark the object broken and fill FreeCAD's report
        with a traceback at every step of a drag."""
        error = self.stand_error(kind, value)
        if error is None:
            before = self.own_value(kind)
            self.write_fin(kind, value)
            try:
                self.apply()
            except ValueError as failed:
                # The other side may still fail with this one changed.
                error = failed
                self.write_fin(kind, before)
                self.preview()
        if error is None:
            self.update_enabled()
            self.show_result()
            return True
        self.refuse(error)
        return False

    def built_value(self, kind):
        """What the handled fin is built with: its shift along the face (ALONG)
        from where it was planned, by hand and where it was moved beside a
        hole, or its height (UP), in mm. Typing and dragging start from here,
        so a fin moved beside a hole is moved on from where it stands."""
        result, _ = self.handled_result()
        number = self.handled[1]
        if kind == handles.ALONG:
            return (self.own_value(kind) or 0.0) + result.moved.get(number, 0.0)
        return result.heights[number]

    def can_stand(self, kind, value):
        """Whether the handled fin can stand with the shift along the face
        (ALONG) or the height (UP) `value`; see stand_error()."""
        return self.stand_error(kind, value) is None

    def stand_error(self, kind, value):
        """Why the handled fin cannot stand with the shift along the face
        (ALONG) or the height (UP) `value`, or None where it can. Tried with a
        build of its side alone: the object is left as it is, so a place where
        the fin cannot stand is never built into it.

        INPUTS this has to withstand:
          value where the fin stands                  ->  None
          shift onto or past a neighbour              ->  the error saying so
          shift where no tine of the fin finds the
            face, beyond a corner or over a recess    ->  error: no tine finds the face there
          height above the face or below the first
            tine                                      ->  the error saying so
          the build fails in OpenCASCADE              ->  that error
          its side has no fins (counter fin removed)  ->  error: no tine finds the face there
        """
        nowhere = geometry.FinError(translate("FinSnap", "no tine of the fin finds the face there"))
        # Moving the fin on a round side turns the part, which stands on its rim at
        # any turn; a turn that fails is taken back by set_fin().
        if kind == handles.ALONG and self.turns_part():
            return None
        which, number = self.handled
        part_and_build = self.obj.Proxy.side_builder(self.obj, which)
        if part_and_build is None:
            return nowhere
        left, shifts, heights = feature.edits(self.obj, which)
        tried = dict(shifts if kind == handles.ALONG else heights)
        # As the value would be stored, so a drag's real build finds this trial.
        tried[number] = feature.stored_mm(value)
        if kind == handles.ALONG:
            if abs(value) < d.TOLERANCE:
                del tried[number]
            shifts = tried
        else:
            heights = tried
        try:
            result = part_and_build[1](left, shifts, heights)
        except (ValueError, Part.OCCError) as error:
            return error
        return None if number in result.numbers else nowhere

    def nearest_standing(self, kind, good, bad):
        """A limit between `good`, where the handled fin stands, and `bad`,
        where it does not: a value where it still stands, within
        SNAP_RESOLUTION of one where it does not, found by halving the way.

        INPUTS this has to withstand:
          one limit on the way, a corner or a
            neighbour                            ->  that limit
          a recess on the way, the fin standing
            again beyond it                      ->  one of the limits, before or beyond
                                                     the recess, whichever the halving
                                                     meets; the fin always stands there
          good and bad closer than SNAP_RESOLUTION  ->  good
        """
        while abs(bad - good) > SNAP_RESOLUTION:
            middle = (good + bad) / 2
            if self.can_stand(kind, middle):
                good = middle
            else:
                bad = middle
        return good

    def ends_key(self):
        """What the arrow ends of the handled fin depend on: the fin, the
        parameters, the changes by hand of its side, and the face it stands
        under, with the shape and the place of its part."""
        which = self.handled[0]
        part, faces = self.obj.Base if which == feature.MAIN else self.obj.CounterFace
        return (self.handled, repr(feature.params_of(self.obj)),
                feature.edits_key(*feature.edits(self.obj, which)), tuple(faces),
                part.Shape.hashCode(), str(part.getGlobalPlacement()))

    def update_ends(self):
        """Leave out each end of an arrow where the handled fin cannot go.
        Tried once for each fin as it stands: a rebuild that changed nothing
        it depends on takes the ends found before."""
        if self.handles.held or self.handled_result() is None:
            return
        self.ends_of = self.handled
        key = self.ends_key()
        if key not in self.known_ends:
            while len(self.known_ends) >= ENDS_KEPT:
                self.known_ends.pop(next(iter(self.known_ends)))
            self.known_ends[key] = {
                kind: tuple(end for end, value in self.next_values(kind, self.built_value(kind))
                            if self.can_stand(kind, value))
                for kind in handles.KINDS}
        for kind, ends in self.known_ends[key].items():
            self.handles.show_ends(kind, ends)

    def handle_started(self, kind):
        """An arrow grabbed: note where the fin stands and what it has by hand;
        the drag starts from there."""
        self.ends_timer.stop()
        # A value typed just before is built first, or the drag would keep the
        # parameters from before it, or the value would come in the middle of it.
        if self.timer.isActive():
            self.preview()
        self.take_typed()
        # While the drag lasts, builds with the same changes by hand are made once;
        # not while the part turns about a round side, as the builds keep the part.
        self.obj.Proxy.reuse = None if kind == handles.ALONG and self.turns_part() else {}
        # Nothing of an earlier drag carries over; without a fin the drag is passed over.
        self.drag_base, self.drag_own, self.drag_values = {}, {}, {}
        self.drag_mm_per_degree = None
        if self.handled_result() is None:
            return
        which, number = self.handled
        self.drag_base = {handles.ALONG: self.built_value(handles.ALONG),
                          handles.UP: self.handled_result()[0].heights[number]}
        self.drag_own = {one: self.own_value(one) for one in handles.KINDS}
        self.drag_values = self.fin_values()
        # Under a round side, the mm the fin moves for every degree the part turns.
        self.drag_mm_per_degree = self.turn_of_handles()[2] if self.turns_part() else None

    def tine_tops(self):
        """The heights of the handled fin that end with a tine on top, from
        the bed, lowest first: no fin stands above its last tine there. Only
        tines that find the face count; a tine over a recess is passed over,
        up to the next one beyond it."""
        result, _ = self.handled_result()
        tine_height = feature.params_of(self.obj).tine_height
        return [z + tine_height for z in result.touching_z.get(self.handled[1], [])]

    def dragged_mm(self, kind, mm, reach=None):
        """Where the fin goes for an arrow dragged `mm` from where it was
        grabbed, as (mm, True), or (mm, False) where it goes nowhere yet:
        along the face as dragged; up to the nearest height that ends with a
        tine, if one lies within `reach` (any, without). A click without a
        move goes nowhere: a height typed by hand is kept."""
        tops = self.tine_tops() if kind == handles.UP else []
        if not tops or abs(mm) < d.TOLERANCE:
            return mm, True
        wanted = self.drag_base[kind] + mm
        nearest = min(tops, key=lambda top: abs(top - wanted))
        if reach is not None and abs(nearest - wanted) > reach:
            return mm, False
        return nearest - self.drag_base[kind], True

    def standing_step(self, last, limit):
        """The height that ends with a tine nearest to `limit` on the way from
        `last`, where the handled fin stands; `last` where none does."""
        low, high = sorted((last, limit))
        steps = [top for top in self.tine_tops() if low - d.TOLERANCE <= top <= high + d.TOLERANCE]
        for top in sorted(steps, key=lambda top: abs(top - limit)):
            if self.can_stand(handles.UP, top):
                return top
        return last

    def next_values(self, kind, value):
        """Where the handled fin would go one step back and one step forth from
        `value`, as (BACK, value) and (FORTH, value): along the face a little
        either way; up and down to the next height that ends with a tine,
        none where there is no such height."""
        if kind == handles.ALONG:
            return [(end, value + end * SNAP_RESOLUTION) for end in (handles.BACK, handles.FORTH)]
        tops = self.tine_tops()
        lower = [top for top in tops if top < value - d.TOLERANCE]
        higher = [top for top in tops if top > value + d.TOLERANCE]
        return ([(handles.BACK, lower[-1])] if lower else []) + ([(handles.FORTH, higher[0])] if higher else [])

    def handle_moved(self, kind, mm):
        if kind not in self.drag_base:
            return
        self.dragged = (kind, mm)
        if kind == handles.ALONG and self.drag_mm_per_degree:
            # The angle of the fin on the part goes the other way round than the part turns.
            shown = geometry.round_angle(self.drag_values[kind] - mm / self.drag_mm_per_degree, ANGLE_TOLERANCE)
        else:
            shown = self.drag_values[kind] + mm
        self.show_fin_values({kind: shown})
        # The value at the arrow as well, as the field shows it, in mm or degrees.
        self.handles.show_value(kind, self.fin_fields[kind].text())
        self.drag_timer.start()

    def drag_to(self, kind, mm):
        """Build the fins with the handled fin `mm` from where it was grabbed.
        A move too small to count gives it back what it had when grabbed, so a
        click on an arrow alone changes nothing."""
        if abs(mm) >= d.TOLERANCE:
            return self.set_fin(kind, self.drag_base[kind] + mm)
        if not _same_mm(self.own_value(kind), self.drag_own[kind]):
            self.write_fin(kind, self.drag_own[kind])
            self.edited()
        return True

    def drag_step(self):
        """While an arrow is held, the fins are built with the fin where the
        arrow is. Up, near a tine the fin is built ending with it, green;
        between tines, also over a recess, it is built as high as the arrow
        and shown yellow, as it goes to the nearest tine when let go. Where it
        cannot stand, it stays at its last place, red, with a red preview."""
        if self.dragged is None or self.handled_result() is None or self.dragged[0] not in self.drag_base:
            return
        kind, raw = self.dragged
        mm, on_step = self.dragged_mm(kind, raw, HEIGHT_REACH)
        if self.drag_to(kind, mm):
            self.handles.clear_preview()
            if not on_step:
                self.tint_handled(handles.BETWEEN_COLOR)
            return
        self.show_dragged(kind, mm, handles.INVALID_COLOR)

    def tint_handled(self, color):
        """The handled fin in `color`, the other fins green; the whole object
        for merged fins, which have no faces of their own."""
        faces = feature.fin_faces(self.obj, *self.handled)
        if faces:
            self.handles.tint_faces(set(faces), color)
        else:
            self.handles.tint_all(color)

    def show_dragged(self, kind, mm, color):
        """Show the handled fin `mm` from where its arrow was grabbed as a
        preview, and the fin itself, in `color`; the other fins stay green."""
        result, index = self.handled_result()
        wanted = self.drag_base[kind] + mm
        if kind == handles.UP:
            # The fin as it would be at the height dragged to, its flank on
            # along the face, rather than stretched, which would tilt it.
            shapes = geometry.fin_at(feature.params_of(self.obj), result, self.handled[1],
                                     max(wanted, MIN_PREVIEW_HEIGHT))
        else:
            fin = result.fins.childShapes()[index].copy()
            # Under a round side the fin stays and the part turns instead.
            if not self.turns_part():
                fin.translate(result.along * (wanted - self.built_value(kind)))
            shapes = [fin]
        # The fin in the colour as well: a preview over a green fin would mix
        # to neither.
        self.tint_handled(color)
        self.handles.show_preview(shapes, color)

    def handle_done(self, kind, mm):
        # Coin still handles the drag here; rebuilding would move the arrow
        # under it, so the last step is made once the event is through.
        self.drag_timer.stop()
        self.dragged = None
        QtCore.QTimer.singleShot(0, functools.partial(self.finish_drag, kind, mm))

    def finish_drag(self, kind, mm):
        """An arrow let go: the fin goes where it is, or, where it cannot stand
        there, as far towards it as it can; the arrows return onto it, and its
        field takes the keyboard, so a value can be typed right away."""
        try:
            if self.handled_result() is None or kind not in self.drag_base:
                self.place_handles()
                return
            # Let go between tines, the fin goes to the nearest.
            mm = self.dragged_mm(kind, mm)[0]
            if not self.drag_to(kind, mm) and self.handled_result() is not None:
                last = self.built_value(kind)
                limit = self.nearest_standing(kind, last, self.drag_base[kind] + mm)
                if kind == handles.UP:
                    limit = self.standing_step(last, limit)
                if abs(limit - last) >= d.TOLERANCE:
                    self.set_fin(kind, limit)
        finally:
            # The drag is over, also after an error: every build is made afresh,
            # and nothing failing was built into the object, so the colours of
            # the drag go.
            self.obj.Proxy.reuse = None
            self.handles.tint(True)
            self.handles.clear_preview()
            self.handles.hide_value()
        self.place_handles()
        box = self.fin_fields[kind]
        box.setFocus()
        box.selectAll()

    def field_typed(self, kind, _value):
        """A field of the handled fin changed while typing: its value is taken
        once typing pauses; a value the panel fills in is not."""
        if self.filling_fields:
            return
        self.typed_field = kind
        self.field_timer.start()

    def take_typed(self):
        """Take a value still waiting for typing to pause, before the handles
        go to another fin or an arrow is grabbed, so it is neither lost nor
        taken in the middle of a drag."""
        if self.field_timer.isActive():
            self.field_entered(self.typed_field)

    def field_entered(self, kind, paused=False):
        """A value typed into a field of the handled fin: where it stands along
        the face (ALONG) or how high it is (UP). With `paused`, typing has only
        paused: the field may still be typed into, so it is left as typed.

        INPUTS this has to withstand:
          paused, the fin stands there          ->  built there, the field left as typed
          paused, the fin cannot stand there    ->  nothing built, the reason shown, the
                                                    field left as typed
          paused, the build fails all the same  ->  taken back, the reason shown, the
                                                    field left as typed
          Enter or the field left, the fin
            stands there                        ->  built there, the field shows it
          Enter or the field left, it cannot    ->  the reason shown, the field shows
                                                    where the fin stands
          the value as shown, untouched         ->  nothing
          no fin with the handles               ->  nothing
        """
        self.field_timer.stop()
        if self.filling_fields or self.handled_result() is None:
            return
        value = self.fin_fields[kind].value()
        current = self.fin_values()[kind]
        if kind == handles.ALONG and self.turns_part():
            # The part turns the other way round than the angle of the fin on
            # it goes, the shorter way.
            turn = math.remainder(current - value, geometry.FULL_CIRCLE)
            # The field shows the angle rounded; leaving it untouched changes nothing.
            if abs(turn) < ANGLE_TOLERANCE:
                return
            value = (self.own_value(kind) or 0.0) + geometry.turn_mm(feature.round_side(self.obj), turn)
        else:
            # The field shows the value rounded; leaving it untouched changes nothing.
            if abs(value - current) < FIELD_TOLERANCE:
                return
            if kind == handles.ALONG:
                value = self.built_value(kind) + value - current
        if not paused:
            if not self.set_fin(kind, value):
                self.place_handles()
            return
        # set_fin() tries the value first and shows why where the fin cannot
        # stand; the field it leaves as typed meanwhile.
        self.typing = kind
        try:
            self.set_fin(kind, value)
        finally:
            self.typing = None

    def release_handles(self):
        """Take the arrows away and stop listening, once, whichever way the panel closes."""
        if self.released:
            return
        self.released = True
        # Closed by FreeCAD first, the panel's form and its timers are gone already.
        for timer in (self.timer, self.drag_timer, self.ends_timer, self.field_timer):
            try:
                timer.stop()
            except RuntimeError:
                pass
        Gui.Selection.removeObserver(self)
        self.handles.remove()
        self.obj.Proxy.editing = False
        self.obj.Proxy.reuse = None
        self.obj.Proxy.results = {}

    def leave_edit(self):
        """Leave edit mode once the panel is closed, as FreeCAD's own panels do."""
        gui_doc = Gui.getDocument(self.obj.Document)
        if gui_doc.getInEdit() is not None and gui_doc.getInEdit().Object is self.obj:
            gui_doc.resetEdit()

    def refuse(self, error):
        self.status.setText("")
        self.show_notes(translate("FinSnap", "Not possible"), [str(error)], ERROR_COLOR)

    def check_stability(self):
        """Check whether the part stays standing while it is printed with these
        fins as they are built now, and say so below the button."""
        if self.timer.isActive():
            self.preview()
        level, note = check_stability(self.obj.Base[0], feature.params_of(self.obj))
        self.stability.setText(note)
        self.stability.setStyleSheet(NOTE_STYLE % STABILITY_FRAMES[level])
        self.stability.show()
        self.stability_checked = True

    def stability_outdated(self):
        """After a change: a stability check shown no longer holds."""
        if self.stability_checked:
            self.stability_checked = False
            self.stability.setText(translate("FinSnap", NOTE_STABILITY_OUTDATED))
            self.stability.setStyleSheet(NOTE_STYLE % OUTDATED_COLOR)

    def preview(self):
        self.timer.stop()
        self.stability_outdated()
        try:
            self.apply()
        except ValueError as error:
            self.handles.tint(False)
            self.refuse(error)
            return
        self.show_result()

    def show_result(self):
        """After a build: the colour of the fins, the red tines, the arrows, the
        result and the notes."""
        self.handles.tint(True)
        results = getattr(self.obj.Proxy, "results", {}).values()
        self.handles.show_dropped([tine for result in results if result for tine in result.dropped])
        # Every build can move the fins or change their height: the arrows follow.
        self.place_handles()
        self.status.setText(translate("FinSnap", "%d fin(s), %.2f mm high, %.2f mm thick")
                            % (self.obj.ResultFinCount, self.obj.ResultHeight.Value,
                               self.obj.ResultThickness.Value))
        # A new build: what a note was about may have moved.
        self.handles.show_noted([])
        placed = [index for index, target in enumerate(self.note_targets())
                  if target and (target.fins or target.faces or target.marks or target.points)]
        self.show_notes(translate("FinSnap", "Notes"), list(self.obj.Warnings), WARNING_COLOR, placed)

    def accept(self):
        self.timer.stop()
        try:
            self.apply()
        except ValueError as error:
            self.refuse(error)
            return False
        self.close()
        App.ActiveDocument.recompute()
        return True

    def reject(self):
        """Cancel: fins just made are deleted, and the part turned back with
        them, in one undo step (discard_created()); fins edited get back what
        they had, and then the part turns back to where the panel found it.

        INPUTS this has to withstand:
          fins just made, the part turned       ->  fins deleted, part turned back
          fins edited, the part turned          ->  values, changes by hand and counter
                                                    fin back, then the part turned back
          fins edited, the part not turned      ->  values back, placement untouched
          fins edited, the face of the main fin
            no round side any more              ->  values back, no turn
        """
        self.close()
        if self.created:
            discard_created(self.obj, self.on_cancel)
            return True
        # How far the part is turned now, read before the changes by hand,
        # which hold it, are put back.
        turned = feature.round_shift(self.obj)
        for name, value in self.original.items():
            setattr(self.obj, name, value)
        for name, value in self.original_edits.items():
            if name in self.obj.PropertiesList:
                setattr(self.obj, name, value)
        self.obj.CounterFace = self.original_counter
        # Turned last, so a turn that fails leaves nothing else half put back;
        # what is put back is built all the same.
        try:
            if feature.on_round_side(self.obj):
                feature.turn_part(self.obj, self.original_turn - turned)
        finally:
            self.obj.recompute()
        return True
