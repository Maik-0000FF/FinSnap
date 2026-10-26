"""Task panel to tune the parameters of a FinSnap object.

The form is generated from feature.PROPERTIES, one group box per property
group, so it never falls out of step with the object.
"""

import functools
import html

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from . import defaults as d
from . import feature
from . import presets
from .i18n import QT_TRANSLATE_NOOP, translate
from .params import FinParams
from .paths import ICON_COUNTER, ICON_REMOVE_COUNTER, ICON_REMOVE_FIN, ICON_RESTORE_FINS, SIDE_VIEW, TOP_VIEW
from .shapes import FACE_PREFIX
from .version import application

# Upper limits of the input fields; generous, the geometry rejects nonsense.
MAX_LENGTH = 10000.0
MAX_INTEGER = 1000
MAX_RATIO = 10.0
LENGTH_DECIMALS = 3
RATIO_DECIMALS = 2
LENGTH_SUFFIX = " mm"
# Pause after the last change before the preview is rebuilt, so typing a
# number does not rebuild the fins at every keystroke.
PREVIEW_DELAY_MS = 400
# FinParams field of the layer height, the step of the fields on the layer grid.
LAYER_FIELD = "layer_height"
# Notes below the result: warnings in amber, a refusal in red, each in a framed
# box with a sign, so they stand out from the result line above.
WARNING_COLOR = "#e0a000"
ERROR_COLOR = "#d03030"
NOTE_STYLE = "QLabel { border: 2px solid %s; border-radius: 4px; padding: 6px; }"
WARNING_SIGN = "⚠"
# A field whose value differs from the standard for new fins: its label in
# this colour, and a button beside it that puts the standard value back.
MODIFIED_COLOR = "#e07000"
MODIFIED_STYLE = "QLabel { color: %s; font-weight: bold; }" % MODIFIED_COLOR
RESET_SIGN = "↺"
# Icon buttons: icon size, the gap to the text and the margin inside, in pixels.
BUTTON_ICON_SIZE = 20
ICON_GAP = 8
BUTTON_PADDING = 6
DRAWINGS = (
    (SIDE_VIEW, QT_TRANSLATE_NOOP("FinSnap", "Side view")),
    (TOP_VIEW, QT_TRANSLATE_NOOP("FinSnap", "Top view")),
)


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
    else:
        widget.setValue(value)


def _same(prop, first, second):
    if prop.kind == feature.CHOICE:
        return first == second
    return abs(first - second) < d.TOLERANCE


def _shown(prop, value):
    """A value as the panel shows it, for a tooltip."""
    if prop.kind == feature.CHOICE:
        return translate("FinSnap", feature.CHOICE_LABELS[value])
    if prop.kind == feature.LENGTH:
        return "%g%s" % (value, LENGTH_SUFFIX)
    return "%g" % value


def _changed_signal(widget):
    if isinstance(widget, QtWidgets.QComboBox):
        return widget.currentIndexChanged
    return widget.valueChanged


def _read(prop, widget):
    if prop.kind == feature.CHOICE:
        return widget.currentData()
    return widget.value()


class FinSnapTaskPanel:
    def __init__(self, obj, created=False):
        self.obj = obj
        self.created = created
        self.widgets = {}
        self.labels = {}
        self.resets = {}
        self.standard = presets.standard()
        # The field whose value is the step of the fields on the layer grid.
        self.layer_prop = next(prop for prop in feature.PROPERTIES if prop.field == LAYER_FIELD)
        # Every change is written to the object at once; Cancel puts these back.
        self.original = {prop.name: feature.value_of(obj, prop.name) for prop in feature.PROPERTIES}
        # And what Edit fins changes: the removed fins and the counter face.
        # A property the fins do not have yet counts as empty: nothing removed.
        self.original_edits = {name: getattr(obj, name, empty) for names, empty in
                               ((feature.REMOVED.values(), []), (feature.REMOVED_OF.values(), 0))
                               for name in names}
        self.original_counter = obj.CounterFace

        self.form = QtWidgets.QWidget()
        # A child of the form, so it goes with the panel and never fires on a
        # closed document.
        self.timer = QtCore.QTimer(self.form)
        self.timer.setSingleShot(True)
        self.timer.setInterval(PREVIEW_DELAY_MS)
        self.timer.timeout.connect(self.preview)
        self.form.setWindowTitle("%s (%s)" % (translate("FinSnap", "FinSnap parameters"), application()))
        layout = QtWidgets.QVBoxLayout(self.form)
        intro = QtWidgets.QLabel(translate(
            "FinSnap", "Hover over a field for an explanation. Letters in brackets point to the drawings "
            "below. Every change is shown in the 3D view right away. Greyed-out fields have no effect "
            "with the current choices; their tooltip says why."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.drawings = []
        for path, caption in DRAWINGS:
            box = QtWidgets.QGroupBox(translate("FinSnap", caption))
            picture = QtWidgets.QLabel()
            picture.setPixmap(QtGui.QPixmap(path))
            QtWidgets.QVBoxLayout(box).addWidget(picture)
            layout.addWidget(box)
            self.drawings.append(picture)

        groups = {}
        for prop in feature.PROPERTIES:
            if prop.group not in groups:
                box = QtWidgets.QGroupBox(translate("App::Property", prop.group))
                groups[prop.group] = QtWidgets.QFormLayout(box)
                info = QtWidgets.QLabel(translate("FinSnap", feature.GROUP_INFO[prop.group]))
                info.setWordWrap(True)
                groups[prop.group].addRow(info)
                layout.addWidget(box)
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

        edit = QtWidgets.QGroupBox(translate("FinSnap", "Edit fins"))
        edit_layout = QtWidgets.QGridLayout(edit)
        edit_info = QtWidgets.QLabel(translate(
            "FinSnap", "To remove one fin, click it in the 3D view and press Remove selected fin, or the "
            "Delete key. The counter fin goes on the face leaning the other way, or on a face of the part "
            "you select."))
        edit_info.setWordWrap(True)
        edit_layout.addWidget(edit_info, 0, 0, 1, 2)
        for column, row, icon, text, action in (
                (0, 1, ICON_REMOVE_FIN, QT_TRANSLATE_NOOP("FinSnap", "Remove selected fin"), self.remove_selected),
                (1, 1, ICON_RESTORE_FINS, QT_TRANSLATE_NOOP("FinSnap", "Bring removed fins back"), self.restore),
                (0, 2, ICON_COUNTER, QT_TRANSLATE_NOOP("FinSnap", "Add counter fin"), self.add_counter),
                (1, 2, ICON_REMOVE_COUNTER, QT_TRANSLATE_NOOP("FinSnap", "Remove counter fin"),
                 self.remove_counter)):
            button = _icon_button(icon, translate("FinSnap", text))
            button.clicked.connect(action)
            edit_layout.addWidget(button, row, column)
        layout.addWidget(edit)

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
        self.notes.hide()
        layout.addWidget(self.notes)
        self.update_steps()
        self.update_enabled()
        self.update_marks()
        self.preview()

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

    def update_marks(self):
        """Mark every field whose value differs from the standard for new fins."""
        for prop in feature.PROPERTIES:
            value = getattr(self.standard, prop.field)
            modified = not _same(prop, _read(prop, self.widgets[prop.name]), value)
            self.labels[prop.name].setStyleSheet(MODIFIED_STYLE if modified else "")
            self.resets[prop.name].setVisible(modified)
            self.resets[prop.name].setToolTip(_wrapped(translate("FinSnap", "Back to the standard: %s")
                                                       % _shown(prop, value)))

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

    def remove_selected(self):
        if self.obj.Connection == d.CONNECTION_MERGED:
            self.show_notes(translate("FinSnap", "Nothing removed"),
                            [translate("FinSnap", feature.NOTE_MERGED_SINGLE)], WARNING_COLOR)
            return
        fins = [feature.fin_at(self.obj, sub) for sel in Gui.Selection.getSelectionEx()
                if sel.Object is self.obj for sub in sel.SubElementNames]
        fins = [fin for fin in fins if fin]
        if not fins:
            self.show_notes(translate("FinSnap", "Nothing removed"),
                            [translate("FinSnap", "Click a fin of these fins in the 3D view first.")], WARNING_COLOR)
            return
        for which, number in set(fins):
            feature.remove_fin(self.obj, which, number)
        self.edited()

    def restore(self):
        feature.restore_fins(self.obj)
        self.edited()

    def add_counter(self):
        part = self.obj.Base[0]
        faces = [name for sel in Gui.Selection.getSelectionEx() if sel.Object is part
                 for name in sel.SubElementNames if name.startswith(FACE_PREFIX)]
        found = feature.add_counter(self.obj, part, faces[0]) if faces else feature.add_counter(self.obj)
        if found is None:
            self.show_notes(translate("FinSnap", "No counter fin"),
                            [translate("FinSnap", "The part has no face leaning the other way. Select one "
                                                  "yourself.")], WARNING_COLOR)
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

    def show_notes(self, title, lines, color):
        """A framed box with a sign and a title, one line per note; hidden without notes."""
        if not lines:
            self.notes.hide()
            return
        items = "".join("<li>%s</li>" % html.escape(line) for line in lines)
        self.notes.setText("<b>%s %s</b><ul style='margin: 0'>%s</ul>" % (WARNING_SIGN, html.escape(title), items))
        self.notes.setStyleSheet(NOTE_STYLE % color)
        self.notes.show()

    def refuse(self, error):
        self.status.setText("")
        self.show_notes(translate("FinSnap", "Not possible"), [str(error)], ERROR_COLOR)

    def preview(self):
        self.timer.stop()
        try:
            self.apply()
        except ValueError as error:
            self.refuse(error)
            return
        self.status.setText(translate("FinSnap", "%d fin(s), %.2f mm high, %.2f mm thick")
                            % (self.obj.ResultFinCount, self.obj.ResultHeight.Value,
                               self.obj.ResultThickness.Value))
        self.show_notes(translate("FinSnap", "Notes"), list(self.obj.Warnings), WARNING_COLOR)

    def accept(self):
        self.timer.stop()
        try:
            self.apply()
        except ValueError as error:
            self.refuse(error)
            return False
        Gui.Control.closeDialog()
        App.ActiveDocument.recompute()
        return True

    def reject(self):
        self.timer.stop()
        Gui.Control.closeDialog()
        if self.created:
            App.ActiveDocument.removeObject(self.obj.Name)
        else:
            for name, value in self.original.items():
                setattr(self.obj, name, value)
            for name, value in self.original_edits.items():
                if name in self.obj.PropertiesList:
                    setattr(self.obj, name, value)
            self.obj.CounterFace = self.original_counter
            self.obj.recompute()
        return True
