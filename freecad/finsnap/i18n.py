# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Translation helpers.

Every user-visible text goes through translate() with a context, so lupdate
can collect it into translations/FinSnap_<lang>.ts. Adding a language means
adding one .ts file and compiling it to .qm; no code changes.
"""

import FreeCAD as App
import FreeCADGui as Gui


def translate(context, text):
    """Same argument order as Qt and FreeCAD, so lupdate recognises the calls."""
    return App.Qt.translate(context, text)


def language():
    """The language FreeCAD shows its texts in, as FreeCAD names it: what is
    kept with a translated text in it is told apart by this.

    INPUTS this has to withstand:
      FreeCAD with its window               ->  the name of its language, "German"
      the language switched while it runs   ->  the name of the new one
      FreeCAD without its window, where
        nothing is translated               ->  None
    """
    told = getattr(Gui, "getLocale", None)
    return told() if told is not None else None


def QT_TRANSLATE_NOOP(context, text):  # noqa: N802 - name required by lupdate
    """Marks text for lupdate without translating it, for property tooltips."""
    return text
