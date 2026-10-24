"""Task panel to tune the parameters of a FinSnap object.

The form is generated from feature.PROPERTIES, one group box per property
group, so it never falls out of step with the object.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from . import feature
from .i18n import QT_TRANSLATE_NOOP, translate
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
IMAGES = os.path.join(os.path.dirname(__file__), "images")
DRAWINGS = (
    (os.path.join(IMAGES, "side_view.svg"), QT_TRANSLATE_NOOP("FinSnap", "Side view")),
    (os.path.join(IMAGES, "top_view.svg"), QT_TRANSLATE_NOOP("FinSnap", "Top view")),
)


def _widget(prop, value):
    if prop.kind == feature.CHOICE:
        box = QtWidgets.QComboBox()
        for choice in prop.choices:
            box.addItem(translate("FinSnap", feature.CHOICE_LABELS[choice]), choice)
        box.setCurrentIndex(prop.choices.index(value))
        return box
    if prop.kind == feature.INTEGER:
        box = QtWidgets.QSpinBox()
        box.setRange(0, MAX_INTEGER)
        box.setValue(value)
        return box
    box = QtWidgets.QDoubleSpinBox()
    if prop.kind == feature.LENGTH:
        box.setRange(0, MAX_LENGTH)
        box.setDecimals(LENGTH_DECIMALS)
        box.setSuffix(LENGTH_SUFFIX)
    else:
        box.setRange(0, MAX_RATIO)
        box.setDecimals(RATIO_DECIMALS)
    box.setValue(value)
    return box


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
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(PREVIEW_DELAY_MS)
        self.timer.timeout.connect(self.preview)

        self.form = QtWidgets.QWidget()
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
            widget.setToolTip(translate("App::Property", prop.tip))
            label = translate("FinSnap", prop.label)
            if prop.name in feature.MARKS:
                label = "%s (%s)" % (label, feature.MARKS[prop.name])
            self.labels[prop.name] = QtWidgets.QLabel(label)
            groups[prop.group].addRow(self.labels[prop.name], widget)
            self.widgets[prop.name] = widget
            _changed_signal(widget).connect(self.changed)

        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.update_enabled()
        self.preview()

    def current(self, name):
        """A field's value as entered; a link that is no field counts as set or not."""
        for prop in feature.PROPERTIES:
            if prop.name == name:
                return _read(prop, self.widgets[name])
        return bool(getattr(self.obj, name))

    def update_enabled(self):
        for prop in feature.PROPERTIES:
            notes = feature.unused_notes(prop.name, self.current)
            tip = translate("App::Property", prop.tip)
            if notes:
                tip += "\n" + " ".join(translate("FinSnap", note) for note in notes)
            self.widgets[prop.name].setEnabled(not notes)
            self.widgets[prop.name].setToolTip(tip)
            self.labels[prop.name].setEnabled(not notes)

    def changed(self):
        self.update_enabled()
        self.timer.start()

    def apply(self):
        for prop in feature.PROPERTIES:
            setattr(self.obj, prop.name, _read(prop, self.widgets[prop.name]))
        # A failed build does not raise here; FreeCAD marks the object and
        # keeps the message, which the panel has to show.
        if not self.obj.recompute():
            raise ValueError(self.obj.getStatusString())

    def preview(self):
        self.timer.stop()
        try:
            self.apply()
        except ValueError as error:
            self.status.setText(translate("FinSnap", "Not possible: %s") % error)
            return
        lines = [translate("FinSnap", "%d fin(s), %.2f mm high, %.2f mm thick")
                 % (self.obj.ResultFinCount, self.obj.ResultHeight.Value,
                    self.obj.ResultThickness.Value)]
        lines += list(self.obj.Warnings)
        self.status.setText("\n".join(lines))

    def accept(self):
        self.timer.stop()
        try:
            self.apply()
        except ValueError as error:
            self.status.setText(translate("FinSnap", "Not possible: %s") % error)
            return False
        Gui.Control.closeDialog()
        App.ActiveDocument.recompute()
        return True

    def reject(self):
        self.timer.stop()
        Gui.Control.closeDialog()
        if self.created:
            App.ActiveDocument.removeObject(self.obj.Name)
        return True
