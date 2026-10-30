# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The FinSnap page in Edit > Preferences: the limits the checks rate by
(limits.py).

A choice of strictness on top fills all fields at once; a field changed by
hand turns it to custom, and back to a strictness whose limits the fields
show again. The fields keep the limits in order as they are typed: the limit
of faces too flat to print never lies steeper than the critical one, so what
is saved always validates. Saved limits that changed rebuild the fins of
every open document, so their marks and warnings follow, and mark their
checks out of date.

INPUTS this has to withstand (the page):
  strict or normal chosen               ->  the fields show its limits
  custom chosen                         ->  the fields stay as they are
  a field changed by hand               ->  custom, or the strictness the
                                            fields match again
  the critical limit set below the
    unprintable one                     ->  the unprintable one follows it down
  the critical span set over the
    unprintable one                     ->  the unprintable one follows it up

INPUTS this has to withstand (saveSettings()):
  the limits shown unchanged            ->  nothing rebuilt
  a limit changed                       ->  saved, the fins of every open
                                            document rebuilt, every check
                                            marked out of date
  no document open                      ->  saved, nothing rebuilt
"""

from PySide import QtWidgets

from . import limits
from .i18n import QT_TRANSLATE_NOOP, translate

# The title of the page, in the group of FinSnap in Edit > Preferences.
TITLE = QT_TRANSLATE_NOOP("FinSnap", "Check limits")
DEGREE, LENGTH, AREA = "degree", "length", "area"
# The fields show this many decimals; the largest area and span they take.
DECIMALS = 1
MAX_AREA = 1000.0
MAX_SPAN = 1000.0
# The fields of the page, by section: the Limits field each sets, its label,
# tooltip, unit and range.
SECTIONS = (
    (QT_TRANSLATE_NOOP("FinSnap", "Overhangs"), (
        ("overhang_critical", QT_TRANSLATE_NOOP("FinSnap", "Critical below"),
         QT_TRANSLATE_NOOP("FinSnap", "Faces lying flatter than this from the bed, without fins, are critical "
                                      "and marked yellow. 0 degrees is a face lying flat over the bed, 90 a "
                                      "vertical wall, as PrusaSlicer measures its overhang threshold; Cura "
                                      "measures from the vertical, its value is 90 degrees minus this one."),
         DEGREE, (limits.ANGLE_MIN, limits.ANGLE_MAX)),
        ("overhang_unprintable", QT_TRANSLATE_NOOP("FinSnap", "Not printable below"),
         QT_TRANSLATE_NOOP("FinSnap", "Faces lying flatter than this from the bed, without fins, are too flat "
                                      "to print and marked red. At most the critical limit."),
         DEGREE, (limits.ANGLE_MIN, limits.ANGLE_MAX)),
        ("overhang_min_area", QT_TRANSLATE_NOOP("FinSnap", "Least area"),
         QT_TRANSLATE_NOOP("FinSnap", "Overhanging faces smaller than this, like the corner facets of a "
                                      "chamfer, are printed over by the slicer without trouble and not reported."),
         AREA, (0.0, MAX_AREA)),
    )),
    (QT_TRANSLATE_NOOP("FinSnap", "Bridges"), (
        ("bridge_critical", QT_TRANSLATE_NOOP("FinSnap", "Critical over"),
         QT_TRANSLATE_NOOP("FinSnap", "A bridge, a face resting on the layer below at two or more sides, "
                                      "spanning further than this between its supports, is critical and marked "
                                      "yellow."),
         LENGTH, (0.0, MAX_SPAN)),
        ("bridge_unprintable", QT_TRANSLATE_NOOP("FinSnap", "Not printable over"),
         QT_TRANSLATE_NOOP("FinSnap", "A bridge spanning further than this sags too far to print and is marked "
                                      "red. At least the critical span."),
         LENGTH, (0.0, MAX_SPAN)),
    )),
    (QT_TRANSLATE_NOOP("FinSnap", "Stability"), (
        ("tipping_angle", QT_TRANSLATE_NOOP("FinSnap", "At risk of tipping below"),
         QT_TRANSLATE_NOOP("FinSnap", "The tipping angle: how far the part would have to lean before the plumb "
                                      "line from its centre of mass left the footprint. A tall part needs a wider "
                                      "tipping margin than a flat one for the same angle. Below this, the part is "
                                      "at risk of tipping and shown yellow; below 0 it tips, shown red. Check "
                                      "stability says which acceleration from the side it withstands."),
         DEGREE, (limits.ANGLE_MIN, limits.ANGLE_MAX)),
    )),
)
# The choice of strictness, in the order offered, and its tooltip.
STRICTNESS_LABEL = QT_TRANSLATE_NOOP("FinSnap", "Strictness")
STRICTNESS_CHOICES = ((limits.STRICT, QT_TRANSLATE_NOOP("FinSnap", "Strict")),
                      (limits.NORMAL, QT_TRANSLATE_NOOP("FinSnap", "Normal")),
                      (limits.CUSTOM, QT_TRANSLATE_NOOP("FinSnap", "Custom")))
STRICTNESS_TIP = QT_TRANSLATE_NOOP(
    "FinSnap", "How strictly the checks rate a part. Normal, built in, allows for what common printers manage and "
    "for the grip of the first layer on the bed. Strict counts the geometry alone: what would need support is not "
    "printable, and the part needs a larger tipping angle. Custom: the limits set below by hand.")


class LimitsPage:
    """The page; FreeCAD makes it when the preferences open."""

    def __init__(self, parent=None):
        # Here, not at the top: this module is loaded when FreeCAD starts,
        # the task panel only once the page is opened.
        from .taskpanel import AREA_SUFFIX, DEGREE_SUFFIX, LENGTH_SUFFIX

        suffixes = {DEGREE: DEGREE_SUFFIX, LENGTH: LENGTH_SUFFIX, AREA: AREA_SUFFIX}
        self.form = QtWidgets.QWidget(parent)
        self.form.setWindowTitle(translate("FinSnap", TITLE))
        layout = QtWidgets.QVBoxLayout(self.form)
        self.strictness = QtWidgets.QComboBox()
        for name, caption in STRICTNESS_CHOICES:
            self.strictness.addItem(translate("FinSnap", caption), name)
        self.strictness.setToolTip(translate("FinSnap", STRICTNESS_TIP))
        # Chosen by hand only: set to follow the fields, it fills nothing.
        self.strictness.activated.connect(self.choose)
        chooser = QtWidgets.QFormLayout()
        text = QtWidgets.QLabel(translate("FinSnap", STRICTNESS_LABEL))
        text.setToolTip(self.strictness.toolTip())
        chooser.addRow(text, self.strictness)
        layout.addLayout(chooser)
        self.fields = {}
        for caption, rows in SECTIONS:
            box = QtWidgets.QGroupBox(translate("FinSnap", caption))
            form = QtWidgets.QFormLayout(box)
            for name, label, tip, unit, (low, high) in rows:
                field = QtWidgets.QDoubleSpinBox()
                field.setDecimals(DECIMALS)
                field.setRange(low, high)
                field.setSuffix(suffixes[unit])
                field.setToolTip(translate("FinSnap", tip))
                text = QtWidgets.QLabel(translate("FinSnap", label))
                text.setToolTip(field.toolTip())
                form.addRow(text, field)
                field.valueChanged.connect(self.follow)
                self.fields[name] = field
            layout.addWidget(box)
        # The limit of faces too flat to print stays at most the critical one.
        self.fields["overhang_critical"].valueChanged.connect(self.fields["overhang_unprintable"].setMaximum)
        # The unprintable span stays at least the critical one.
        self.fields["bridge_critical"].valueChanged.connect(self.fields["bridge_unprintable"].setMinimum)
        layout.addStretch()

    def choose(self, index):
        """Fill the fields with the limits of the strictness chosen at `index`;
        custom leaves them as they are."""
        name = self.strictness.itemData(index)
        if name in limits.STRICTNESS:
            self.show(limits.STRICTNESS[name])

    def follow(self, _value=None):
        """Show the strictness whose limits the fields show, custom for none."""
        self.strictness.setCurrentIndex(self.strictness.findData(limits.strictness_of(self.shown())))

    def show(self, shown):
        """Fill the fields with `shown`, a limits.Limits."""
        # The critical limits first: they bound the others.
        for name in sorted(self.fields, key=lambda name: name not in ("overhang_critical", "bridge_critical")):
            self.fields[name].setValue(getattr(shown, name))

    def shown(self):
        """The limits the fields show."""
        return limits.Limits(**{name: field.value() for name, field in self.fields.items()})

    def loadSettings(self):  # noqa: N802 - FreeCAD API
        self.show(limits.current())

    def saveSettings(self):  # noqa: N802 - FreeCAD API
        before, after = limits.current(), self.shown()
        limits.save(after)
        if before != after:
            # Here, not at the top, as the task panel above.
            from . import feature

            feature.follow_limits()
