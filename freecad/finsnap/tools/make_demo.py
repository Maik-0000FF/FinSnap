# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Render the frames of the demo GIF in the README.

Run by make_demo.sh, which starts FreeCAD on a virtual screen and turns the
frames into the GIF. Read from the environment:
    DEMO_MODEL   the FreeCAD document with the part, opened, never saved
    DEMO_PART    the name of the part in it
    DEMO_FACE    the face Quick fins stands the part on ("Face3")
    DEMO_FRAMES  the folder the numbered PNG frames go into

The demo: the part tilts onto the face with Quick fins, the fin's height is
dragged down and up again from tine to tine, then the fin is moved along the
face past its corner, where it stops, and back under the middle.
"""

import math
import os
import shutil
import sys

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from freecad.finsnap.shapes import FACE_PREFIX

SIZE = (960, 640)
# The look of the pictures in the README: a dark ground, the part blue.
BACKGROUND = "#1f1f1f"
PART_COLOR = (0.22, 0.42, 0.62)
VIEW_SETTINGS = "User parameter:BaseApp/Preferences/View"
NAVIGATION_ANIMATIONS = "UseNavigationAnimations"
CAMERA = "Orthographic"
# The camera between the side view along the face (0) and straight outside
# the fin (90), and how far above the bed it looks from, below with a
# negative angle (degrees): the fin shows its broad side, and a little of
# the face it stands under.
AZIMUTH = 35.0
ELEVATION = -10.0
# Frames a still picture is held for, at the frame rate of the GIF.
HOLD = 12
SHORT_HOLD = 6
# Frames the part takes to tilt onto its edge, so the tilt shows.
TILT_FRAMES = 12
# Frames of the drags: the height down to a tine about halfway, then up to
# the highest tine, so the fin is large when it is moved; along the face
# past its corner, by the length of the face, and back to the middle.
DOWN_FRAMES = 15
UP_FRAMES = 36
ALONG_FRAMES = 15
BACK_FRAMES = 10
FRAME_NAME = "%04d.png"

frames = os.environ.get("DEMO_FRAMES", "")
count = 0
panels = []


def say(*args):
    # sys.__stdout__: with the GUI running, print() goes to the report view.
    print("make_demo:", *args, file=sys.__stdout__)
    sys.__stdout__.flush()


def settle():
    """Draw the view as it is now. The timers of the panel would build again
    in between, as the demo builds each step itself; they are stopped."""
    for panel in panels:
        for timer in (panel.timer, panel.drag_timer, panel.ends_timer):
            timer.stop()
    Gui.updateGui()


def frame(times=1):
    """Save the view as the next frame, `times` frames long."""
    global count
    settle()
    first = os.path.join(frames, FRAME_NAME % count)
    Gui.ActiveDocument.ActiveView.saveImage(first, SIZE[0], SIZE[1], BACKGROUND)
    count += 1
    for _ in range(times - 1):
        shutil.copy(first, os.path.join(frames, FRAME_NAME % count))
        count += 1


def look(face_frame):
    """Look at the fin under the face of `face_frame`, from outside it and
    from the side. Set on the camera node, as Quick fins does:
    setViewDirection() starts an animation that does not take here."""
    from freecad.finsnap import commands
    Gui.ActiveDocument.ActiveView.setCameraType(CAMERA)
    up = App.Vector(0, 0, 1)
    slope, turn = math.radians(ELEVATION), math.radians(AZIMUTH)
    beside = face_frame.along * math.cos(turn) + face_frame.out * math.sin(turn)
    commands._show_on_bed(beside * -math.cos(slope) - up * math.sin(slope))


def steps(start, end, count_of):
    """`count_of` values from just after `start` to `end`, evenly apart."""
    return [start + (end - start) * (i + 1) / count_of for i in range(count_of)]


def drag(panel, kind, targets):
    """Drag the arrow of `kind` through the values `targets`, a frame at each, then let go."""
    base = panel.built_value(kind)
    panel.handle_started(kind)
    for value in targets:
        panel.handle_moved(kind, value - base)
        panel.drag_step()
        frame()
    panel.finish_drag(kind, targets[-1] - base)


def main():
    from freecad.finsnap import commands, feature, geometry, handles
    from freecad.finsnap.shapes import global_shape, moved, outermost

    model, part_name, face_name = (os.environ.get(name, "") for name in ("DEMO_MODEL", "DEMO_PART", "DEMO_FACE"))
    if not (model and part_name and face_name.startswith(FACE_PREFIX) and frames):
        raise ValueError("set DEMO_MODEL, DEMO_PART, DEMO_FACE (FaceN) and DEMO_FRAMES")
    os.makedirs(frames, exist_ok=True)
    Gui.activateWorkbench("FinSnapWorkbench")
    # FreeCAD runs with a home of its own (make_demo.sh): this setting stays
    # there. A camera animation would wait on itself here; a message is said
    # instead of waiting for a click.
    App.ParamGet(VIEW_SETTINGS).SetBool(NAVIGATION_ANIMATIONS, False)
    commands._message = lambda text: say("message:", text)
    QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.Yes)

    doc = App.openDocument(model)
    part = doc.getObject(part_name)
    part.ViewObject.ShapeColor = PART_COLOR
    # Where Quick fins will stand the part, worked out by the command's own
    # plan, to show the tilt as a movement that ends where the command stands
    # it, and to look at the fin from outside.
    plan = commands.quick_plan(part, [], [face_name])
    standing = moved(global_shape(part), plan.change)
    face_frame = geometry.frame_of(standing, standing.Faces[plan.number])
    owner = outermost(part)
    lying = App.Placement(owner.Placement)
    stood = plan.change.multiply(lying)
    # One camera for the whole demo, fitted to the part standing: it tilts
    # and stays, the view does not jump after.
    owner.Placement = stood
    doc.recompute()
    look(face_frame)
    owner.Placement = lying
    doc.recompute()
    frame(HOLD)

    # The tilt as a movement, then Quick fins itself.
    for step in range(1, TILT_FRAMES + 1):
        owner.Placement = lying.sclerp(stood, step / TILT_FRAMES)
        doc.recompute()
        frame()
    owner.Placement = lying
    doc.recompute()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(part, face_name)
    already = {o.Name for o in doc.Objects}
    Gui.runCommand("FinSnap_QuickFins")
    # The fins Quick fins made, also in a document that has fins already.
    fins = [o for o in doc.Objects if feature.is_fins(o) and o.Name not in already][0]
    panel = fins.ViewObject.Proxy.panel
    panels.append(panel)
    # Quick fins turns the view; the part stands as when the camera was fitted.
    look(face_frame)
    frame(HOLD)

    # The height, from tine to tine: down, then up to the highest tine.
    tops = panel.tine_tops()
    drag(panel, handles.UP, steps(panel.built_value(handles.UP), tops[len(tops) // 2 - 1], DOWN_FRAMES))
    frame(SHORT_HOLD)
    drag(panel, handles.UP, steps(panel.built_value(handles.UP), tops[-1], UP_FRAMES))
    frame(HOLD)

    # Along the face past its corner: red there, and let go it stops at the
    # corner; then back under the middle, where it stood.
    middle = panel.built_value(handles.ALONG)
    reach = face_frame.along_max - face_frame.along_min
    drag(panel, handles.ALONG, steps(middle, middle - reach, ALONG_FRAMES))
    frame(SHORT_HOLD)
    drag(panel, handles.ALONG, steps(panel.built_value(handles.ALONG), middle, BACK_FRAMES))
    frame(HOLD)
    say(count, "frames in", frames)


try:
    main()
    result = 0
except Exception:
    import traceback
    traceback.print_exc(file=sys.__stdout__)
    result = 1
sys.__stdout__.flush()
# The GUI ends with the script; nothing of the document is saved.
os._exit(result)
