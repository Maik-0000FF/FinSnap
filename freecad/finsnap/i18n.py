# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

"""Translation helpers.

Every user-visible text goes through translate() with a context, so lupdate
can collect it into translations/FinSnap_<lang>.ts. Adding a language means
adding one .ts file and compiling it to .qm; no code changes.
"""

import FreeCAD as App


def translate(context, text):
    """Same argument order as Qt and FreeCAD, so lupdate recognises the calls."""
    return App.Qt.translate(context, text)


def QT_TRANSLATE_NOOP(context, text):  # noqa: N802 - name required by lupdate
    """Marks text for lupdate without translating it, for property tooltips."""
    return text
