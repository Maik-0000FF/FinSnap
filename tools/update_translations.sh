#!/usr/bin/env sh
# Collect the texts of the workbench into every translations/finsnap_*.ts and
# compile them to .qm. Needs lupdate and lrelease from Qt 6 (qttools); LUPDATE
# and LRELEASE override the commands, for example with the PySide6 versions.
# Without an argument the German file is updated; a language code adds or
# updates that language, for example: tools/update_translations.sh fr
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PACKAGE="$ROOT/freecad/finsnap"
TRANSLATIONS="$PACKAGE/translations"
LANGUAGE=${1:-de}

"${LUPDATE:-lupdate}" "$PACKAGE"/*.py -no-obsolete -source-language en -target-language "$LANGUAGE" \
    -ts "$TRANSLATIONS/finsnap_$LANGUAGE.ts"
# A running FreeCAD keeps the .qm mapped in memory; writing over it in place
# crashes FreeCAD at its next translated text. The new file is written beside
# it and renamed, so FreeCAD keeps reading the old one until it restarts.
for ts in "$TRANSLATIONS"/finsnap_*.ts; do
    qm="${ts%.ts}.qm"
    "${LRELEASE:-lrelease}" "$ts" -qm "$qm.tmp"
    mv "$qm.tmp" "$qm"
done
