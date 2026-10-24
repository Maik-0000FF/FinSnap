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
for ts in "$TRANSLATIONS"/finsnap_*.ts; do
    "${LRELEASE:-lrelease}" "$ts"
done
