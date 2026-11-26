# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""The drag of a fin by its arrows in the task panel: where the fin goes
while an arrow is held, the builds on the way, and where it ends once the
arrow is let go.

FinDrag holds what a drag needs and works on the fin the panel has the
arrows on, through the panel: which fin that is, where it may stand
(FinSnapTaskPanel.can_stand() and the like) and how it is set are the
panel's.
"""

import functools

from PySide import QtCore, QtWidgets

from . import defaults as d
from . import face_frame, feature, geometry, handles

# Pause after the last move of a handle before the preview for it is built.
DRAG_PREVIEW_MS = 150
# How near a tine a fin dragged up or down goes to it (mm); farther from
# every tine, it is shown yellow where it is dragged and goes to the nearest
# when let go.
HEIGHT_REACH = 1.0
# The lowest a fin dragged down is previewed, so the preview never flattens
# to nothing or turns over (mm).
MIN_PREVIEW_HEIGHT = 0.1


def _same_mm(a, b):
    """Whether two lengths in mm, each possibly None, are the same."""
    if a is None or b is None:
        return a is b
    return abs(a - b) < d.TOLERANCE


class FinDrag:
    """The drag of the fin `panel` has the arrows on. Its timer is a child of
    `parent`, the form of the panel, and waits for the kernel through
    `waiting`, a KernelWait; `angle_tolerance` is how close an angle on a
    round side counts as the one the field of the panel shows."""

    def __init__(self, panel, parent, waiting, angle_tolerance):
        self.panel = panel
        self.waiting = waiting
        self.angle_tolerance = angle_tolerance
        self.timer = QtCore.QTimer(parent)
        self.timer.setSingleShot(True)
        self.timer.setInterval(DRAG_PREVIEW_MS)
        self.timer.timeout.connect(functools.partial(waiting.when_built, self.timer, self.step))
        # The arrow being dragged with how far, as (kind, mm); and the shift
        # and height of the fin, what it has by hand, and the values in its
        # fields, when it was grabbed.
        self.dragged = None
        self.base, self.own, self.values = {}, {}, {}
        # Under a round side, the mm the fin moves for every degree the part turns.
        self.mm_per_degree = None
        # Whether a drag of a side fin moves both side fins.
        self.together = False
        self.closed = False

    def started(self, kind):
        """An arrow grabbed: note where the fin stands and what it has by hand;
        the drag starts from there."""
        panel = self.panel
        panel.ends_timer.stop()
        # A field at an arrow is taken, as a click elsewhere takes it.
        panel.take_arrow_field()
        # A value typed just before is built first, taken or not, as grabbing
        # an arrow leaves its field; or the drag would keep the parameters from
        # before it, or the value would come in the middle of it.
        if panel.timer.isActive() or panel.differs():
            panel.preview()
        panel.take_typed()
        # While the drag lasts, builds with the same changes by hand are made once;
        # not while the part turns about a round side, as the builds keep the part.
        panel.obj.Proxy.reuse = None if kind == handles.ALONG and panel.turns_part() else {}
        # Nothing of an earlier drag carries over; without a fin the drag is passed over.
        self.base, self.own, self.values = {}, {}, {}
        self.mm_per_degree = None
        self.together = bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)
        if panel.handled_result() is None:
            return
        number = panel.handled[1]
        self.base = {handles.ALONG: panel.built_value(handles.ALONG),
                     handles.UP: panel.handled_result()[0].heights[number]}
        self.own = {one: panel.own_value(one) for one in handles.KINDS}
        self.values = panel.fin_values()
        self.mm_per_degree = panel.turn_of_handles()[2] if panel.turns_part() else None

    def dragged_mm(self, kind, mm, reach=None):
        """Where the fin goes for an arrow dragged `mm` from where it was
        grabbed, as (mm, True), or (mm, False) where it goes nowhere yet:
        along the face as dragged; up to the nearest height that ends with a
        tine, if one lies within `reach` (any, without). A click without a
        move goes nowhere: a height typed by hand is kept."""
        tops = self.panel.tine_tops() if kind == handles.UP else []
        if not tops or abs(mm) < d.TOLERANCE:
            return mm, True
        wanted = self.base[kind] + mm
        nearest = min(tops, key=lambda top: abs(top - wanted))
        if reach is not None and abs(nearest - wanted) > reach:
            return mm, False
        return nearest - self.base[kind], True

    def moved(self, kind, mm):
        if kind not in self.base:
            return
        self.dragged = (kind, mm)
        if kind == handles.ALONG and self.mm_per_degree:
            # The angle of the fin on the part goes the other way round than the part turns.
            shown = face_frame.round_angle(self.values[kind] - mm / self.mm_per_degree, self.angle_tolerance)
        else:
            shown = self.values[kind] + mm
        self.panel.show_fin_values({kind: shown})
        # The value at the arrow as well, as the field shows it, in mm or degrees.
        self.panel.handles.show_value(kind, self.panel.fin_fields[kind].text())
        self.timer.start()

    def move_to(self, kind, mm):
        """Build the fins with the handled fin `mm` from where it was grabbed.
        A move too small to count gives it back what it had when grabbed, so a
        click on an arrow alone changes nothing."""
        panel = self.panel
        if abs(mm) >= d.TOLERANCE:
            return panel.set_fin(kind, self.base[kind] + mm)
        if not _same_mm(panel.own_value(kind), self.own[kind]):
            panel.write_fin(kind, self.own[kind])
            panel.edited()
        return True

    def step(self):
        """While an arrow is held, the fins are built with the fin where the
        arrow is. Up, near a tine the fin is built ending with it, green;
        between tines, also over a recess, it is built as high as the arrow
        and shown yellow, as it goes to the nearest tine when let go. Where it
        cannot stand, it stays at its last place, red, with a red preview."""
        panel = self.panel
        if self.dragged is None or panel.handled_result() is None or self.dragged[0] not in self.base:
            return
        kind, raw = self.dragged
        mm, on_step = self.dragged_mm(kind, raw, HEIGHT_REACH)
        # With fins beside a lowest line a build takes too long for every step:
        # the fin is shown where it would go, and built once let go.
        if panel.side_fins_built():
            self.show(kind, mm, handles.BETWEEN_COLOR)
            return
        if self.move_to(kind, mm):
            panel.handles.clear_preview()
            if not on_step:
                panel.tint_handled(handles.BETWEEN_COLOR)
            return
        self.show(kind, mm, handles.INVALID_COLOR)

    def show(self, kind, mm, color):
        """Show the handled fin `mm` from where its arrow was grabbed as a
        preview, and the fin itself, in `color`; the other fins stay green."""
        panel = self.panel
        result, index = panel.handled_result()
        wanted = self.base[kind] + mm
        if kind == handles.UP:
            # The fin as it would be at the height dragged to, its flank on
            # along the face, rather than stretched, which would tilt it.
            shapes = geometry.fin_at(feature.params_of(panel.obj), result, panel.handled[1],
                                     max(wanted, MIN_PREVIEW_HEIGHT))
        else:
            fin = result.fins.childShapes()[index].copy()
            # Under a round side the fin stays and the part turns instead.
            if not panel.turns_part():
                fin.translate(result.along * (wanted - panel.built_value(kind)))
            shapes = [fin]
        # The fin in the colour as well: a preview over a green fin would mix
        # to neither.
        panel.tint_handled(color)
        panel.handles.show_preview(shapes, color)

    def done(self, kind, mm):
        # Coin still handles the drag here; rebuilding would move the arrow
        # under it, so the last step is made once the event is through.
        self.timer.stop()
        self.dragged = None
        self.waiting.once_free(functools.partial(self.finish, kind, mm))

    def finish(self, kind, mm):
        """An arrow let go: the fin goes where it is, or, where it cannot stand
        there, as far towards it as it can; the arrows return onto it, and its
        field takes the keyboard, so a value can be typed right away. Called
        once the arrow is let go: closed meanwhile, the panel has let go of
        the 3D view, and nothing is done."""
        if self.closed:
            return
        panel = self.panel
        try:
            if panel.handled_result() is None or kind not in self.base:
                panel.place_handles()
                return
            # Let go between tines, the fin goes to the nearest.
            mm = self.dragged_mm(kind, mm)[0]
            if not self.move_to(kind, mm) and panel.handled_result() is not None:
                last = panel.built_value(kind)
                limit = panel.nearest_standing(kind, last, self.base[kind] + mm)
                if kind == handles.UP:
                    limit = panel.standing_step(last, limit)
                if abs(limit - last) >= d.TOLERANCE:
                    panel.set_fin(kind, limit)
        finally:
            # The drag is over, also after an error: every build is made afresh,
            # and nothing failing was built into the object, so the colours of
            # the drag go.
            panel.obj.Proxy.reuse = None
            self.together = False
            panel.handles.tint(True)
            panel.handles.clear_preview()
            panel.handles.hide_value()
        panel.place_handles()
        box = panel.fin_fields[kind]
        box.setFocus()
        box.selectAll()

    def close(self):
        """Do nothing more of a drag, as the panel closes. Closed by FreeCAD
        first, the form of the panel and the timer with it are gone already."""
        self.closed = True
        try:
            self.timer.stop()
        except RuntimeError:
            pass
