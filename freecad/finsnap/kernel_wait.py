# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""What the task panel does only once nothing is at work in the kernel.

FreeCAD's progress display lets timers fire during a recompute, from any
command, and a build started inside one can stop in the kernel and never
return, so FreeCAD freezes. KernelWait puts the timeouts of the panel off
until the kernel is free, and keeps what is to be done once the events under
way are through.
"""

import functools
import time

import FreeCAD as App
from PySide import QtCore, QtWidgets

from .shapes import at_work

# How long the probe for an operation of FreeCAD is believed while it alone
# says one runs (s): longer than an operation of another workbench the panel
# would wait out takes, far shorter than a user waits for arrows that never
# come.
PROBE_BELIEVED_S = 60.0
# How soon a timer put off because something is at work in the kernel asks
# again at the least (ms): what is put off with no delay of its own would
# otherwise ask without a pause.
BUSY_RETRY_MS = 50


class _Reached(QtCore.QObject):
    """Notes whether an event sent to it reaches it."""

    def __init__(self):
        super().__init__()
        self.reached = False

    def event(self, event):
        self.reached = True
        return True


def operation_runs():
    """Whether FreeCAD shows the progress of a long operation of the kernel,
    its own or of any workbench. While one runs, its progress bar filters
    the events of the application and drops, among others, every event
    saying the mouse left something: one sent to an object of its own here
    does not reach it then. It tells of no operation that shows no progress.

    INPUTS this has to withstand:
      no operation running                  ->  False: the event reaches its object
      an operation showing its progress     ->  True: FreeCAD drops the event
      the event dropped by something else,
        as a FreeCAD that filters otherwise ->  True, wrongly: who asks does not
                                                believe it for ever (busy())
    """
    probe = _Reached()
    QtWidgets.QApplication.sendEvent(probe, QtCore.QEvent(QtCore.QEvent.Leave))
    return not probe.reached


class KernelWait:
    """The timeouts of one task panel put off while the kernel is at work, and
    what it is to do once the events under way are through. `parent`, the form
    of the panel, holds its timer, so it goes with the panel and never fires on
    a closed document."""

    def __init__(self, parent):
        # When the probe for an operation of FreeCAD first said one runs with
        # nothing else saying so (operation_runs()), and whether it is believed.
        self.probe_alone_since = None
        self.probe_believed = True
        # What is to be done once the events under way are through and nothing
        # is being built (once_free()), in its order.
        self.to_do = []
        self.closed = False
        self.free_timer = QtCore.QTimer(parent)
        self.free_timer.setSingleShot(True)
        self.free_timer.timeout.connect(functools.partial(self.when_built, self.free_timer, self.do_waiting))

    def when_built(self, timer, action):
        """Do `action`, what the timeout of `timer` asks for, once no recompute is
        running. FreeCAD's progress display lets timers fire during one, from
        any command, and a build started inside it can stop in the kernel and
        never return, so FreeCAD freezes.

        INPUTS this has to withstand:
          nothing at work                       ->  done now
          FinSnap building fins, whoever asked:
            the panel recomputing them, a build
            tried to see whether a fin can
            stand, a command                    ->  not done, the timer started again
          FinSnap checking a part: islands,
            bridges, overhangs, stability, the
            ways to stand it                    ->  the same
          a recompute of this document running  ->  the same
          a recompute of another document       ->  the same: rebuild_fins() goes through
                                                    all of them, and it is one kernel
          an operation of FreeCAD or another
            workbench showing its progress      ->  the same, as long as the probe for it
                                                    is believed (busy())
          several timeouts during a long one    ->  put off each time, done once after
        """
        if self.busy():
            # No sooner than BUSY_RETRY_MS: a timer of no delay would fire again at once.
            timer.start(max(timer.interval(), BUSY_RETRY_MS))
            return
        action()

    def busy(self):
        """Whether something is at work in the kernel, so nothing may be built
        now: FinSnap itself (shapes.at_work()), a recompute of a document, or
        an operation of FreeCAD or another workbench showing its progress
        (operation_runs()). The first two are told outright; the last is a net
        under them, taken from how FreeCAD behaves, and not believed for ever:
        once it alone has said so for longer than PROBE_BELIEVED_S, with
        neither of the others saying so, it is not asked again for this
        panel, or a probe gone wrong would put every timer off for good."""
        if at_work() or any(document.Recomputing for document in App.listDocuments().values()):
            self.probe_alone_since = None
            return True
        if not self.probe_believed or not operation_runs():
            self.probe_alone_since = None
            return False
        now = time.monotonic()
        if self.probe_alone_since is None:
            self.probe_alone_since = now
        self.probe_believed = now - self.probe_alone_since <= PROBE_BELIEVED_S
        return self.probe_believed

    def once_free(self, action):
        """Do `action` once the events under way are through and nothing is at
        work in the kernel, after what was put here before it. A plain timer
        of no delay fires inside a build started meanwhile as well."""
        self.to_do.append(action)
        self.free_timer.start(0)

    def do_waiting(self):
        """Do what once_free() was given, in its order; not once closed. Where
        one of them raises, its error passes on and those after it are kept,
        to be done next: one failing does not lose the others."""
        while self.to_do:
            action = self.to_do.pop(0)
            if self.closed:
                continue
            try:
                action()
            except Exception:
                if self.to_do:
                    self.free_timer.start(0)
                raise

    def close(self):
        """Do nothing more of what waits, as the panel closes. Closed by FreeCAD
        first, the form of the panel and the timer with it are gone already."""
        self.closed = True
        try:
            self.free_timer.stop()
        except RuntimeError:
            pass
