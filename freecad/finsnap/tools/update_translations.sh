#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2026 Maik-0000FF
# SPDX-License-Identifier: GPL-3.0-or-later

# Collect the texts of the workbench into the template translations/FinSnap.ts
# and into every translation FinSnap_<language>.ts, and compile the
# translations to .qm. Needs lupdate and lrelease from Qt 6 (qttools); LUPDATE
# and LRELEASE override the commands, for example with the PySide6 versions.
# A language code as argument adds that language, for example:
#   freecad/finsnap/tools/update_translations.sh fr
set -eu

PACKAGE=$(cd "$(dirname "$0")/.." && pwd)
TRANSLATIONS="$PACKAGE/translations"
NAME=FinSnap

# collect <.ts file> [lupdate options]
collect() {
    ts=$1
    shift
    "${LUPDATE:-lupdate}" "$PACKAGE"/*.py -no-obsolete -source-language en "$@" -ts "$ts"
}

# The template carries every text untranslated, as the starting point of a
# new language and for translation services.
collect "$TRANSLATIONS/$NAME.ts"
if [ $# -gt 0 ] && [ ! -e "$TRANSLATIONS/${NAME}_$1.ts" ]; then
    collect "$TRANSLATIONS/${NAME}_$1.ts" -target-language "$1"
fi
# A running FreeCAD keeps the .qm mapped in memory; writing over it in place
# crashes FreeCAD at its next translated text. The new file is written beside
# it and renamed, so FreeCAD keeps reading the old one until it restarts.
for ts in "$TRANSLATIONS/${NAME}"_*.ts; do
    # Without any language the pattern stays as it is, naming no file.
    [ -e "$ts" ] || continue
    # Cut after the fixed prefix: a code may hold an underscore itself (pt_BR).
    language=${ts##*/"${NAME}"_}
    collect "$ts" -target-language "${language%.ts}"
    qm="${ts%.ts}.qm"
    "${LRELEASE:-lrelease}" "$ts" -qm "$qm.tmp"
    mv "$qm.tmp" "$qm"
done
