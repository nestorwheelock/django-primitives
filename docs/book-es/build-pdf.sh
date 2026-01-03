#!/bin/bash
# Build Spanish PDF from markdown chapters

BOOK_DIR="/home/nwheelo/projects/django/django-primitives/docs/book-es"
OUTPUT="$BOOK_DIR/domesticando-la-maquina-prueba.pdf"

# Order of chapters
FILES=(
    "$BOOK_DIR/00-title.md"
    "$BOOK_DIR/00-copyright.md"
    "$BOOK_DIR/00-introduction.md"
    # Parte 1: La Mentira
    "$BOOK_DIR/part-1-title.md"
    "$BOOK_DIR/part-1-the-lie/ch01-modern-software-is-old.md"
    "$BOOK_DIR/part-1-the-lie/ch02-ai-does-not-understand-business.md"
    "$BOOK_DIR/part-1-the-lie/ch03-you-will-refactor-later.md"
    # Parte 2: Las Primitivas
    "$BOOK_DIR/part-2-title.md"
    "$BOOK_DIR/part-2-the-primitives/ch04-project-structure.md"
    "$BOOK_DIR/part-2-the-primitives/ch05-foundation-layer.md"
    "$BOOK_DIR/part-2-the-primitives/ch06-identity.md"
    "$BOOK_DIR/part-2-the-primitives/ch07-time.md"
    "$BOOK_DIR/part-2-the-primitives/ch08-agreements.md"
    "$BOOK_DIR/part-2-the-primitives/ch09-catalog.md"
    "$BOOK_DIR/part-2-the-primitives/ch10-ledger.md"
    "$BOOK_DIR/part-2-the-primitives/ch11-workflow.md"
    "$BOOK_DIR/part-2-the-primitives/ch12-decisions.md"
    "$BOOK_DIR/part-2-the-primitives/ch13-audit.md"
    "$BOOK_DIR/part-2-the-primitives/ch14-worklog.md"
    "$BOOK_DIR/part-2-the-primitives/ch15-geo.md"
    "$BOOK_DIR/part-2-the-primitives/ch16-documents.md"
    "$BOOK_DIR/part-2-the-primitives/ch17-notes.md"
    "$BOOK_DIR/part-2-the-primitives/ch18-sequence.md"
    # Parte 3: Domesticando la Maquina
    "$BOOK_DIR/part-3-title.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch19-the-instruction-stack.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch20-prompt-contracts.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch21-schema-first-generation.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch22-forbidden-operations.md"
    # Parte 4: Composicion
    "$BOOK_DIR/part-4-title.md"
    "$BOOK_DIR/part-4-composition/ch23-build-a-clinic.md"
    "$BOOK_DIR/part-4-composition/ch24-build-a-marketplace.md"
    "$BOOK_DIR/part-4-composition/ch25-build-a-subscription-service.md"
    "$BOOK_DIR/part-4-composition/ch26-build-a-government-form-workflow.md"
    # Conclusion
    "$BOOK_DIR/ch27-conclusion.md"
)

echo "Construyendo PDF de ${#FILES[@]} capitulos..."

# Preprocess to remove/convert problematic Unicode
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

for f in "${FILES[@]}"; do
    fname=$(basename "$f")
    # Convert Unicode characters to ASCII equivalents - comprehensive list
    sed -e 's/├/|--/g' \
        -e 's/└/\\--/g' \
        -e 's/│/|/g' \
        -e 's/─/-/g' \
        -e 's/┌/+/g' \
        -e 's/┐/+/g' \
        -e 's/┘/+/g' \
        -e 's/┴/+/g' \
        -e 's/┬/+/g' \
        -e 's/┼/+/g' \
        -e 's/≠/!=/g' \
        -e 's/→/->/g' \
        -e 's/←/<-/g' \
        -e 's/▼/v/g' \
        -e 's/▲/^/g' \
        -e 's/►/>/g' \
        -e 's/◄/</g' \
        -e 's/▶/>/g' \
        -e 's/◀/</g' \
        -e 's/•/*/g' \
        -e 's/◦/o/g' \
        -e 's/▪/*/g' \
        -e 's/✓/[x]/g' \
        -e 's/✗/[ ]/g' \
        -e 's/✅/[x]/g' \
        -e 's/❌/[ ]/g' \
        -e 's/⚠️/[!]/g' \
        -e 's/⚠/[!]/g' \
        -e 's/🚦/[*]/g' \
        -e 's/📝/[nota]/g' \
        -e 's/🔧/[fix]/g' \
        -e 's/🎯/[meta]/g' \
        -e 's/💡/[tip]/g' \
        -e 's/🛑/[ALTO]/g' \
        -e 's/📋/[lista]/g' \
        -e 's/📊/[grafico]/g' \
        -e 's/🔨/[build]/g' \
        -e 's/🔄/[ciclo]/g' \
        -e 's/🎓/[aprende]/g' \
        -e 's/🚨/[alerta]/g' \
        -e 's/🛠️/[herramientas]/g' \
        -e 's/🛠/[herramientas]/g' \
        -e 's/💰/[dinero]/g' \
        -e 's/🐛/[bug]/g' \
        -e 's/🤖/[IA]/g' \
        -e 's/📦/[pkg]/g' \
        -e 's/🎪/[demo]/g' \
        -e "s/'/'/g" \
        -e "s/'/'/g" \
        -e 's/"/"/g' \
        -e 's/"/"/g' \
        -e 's/—/--/g' \
        -e 's/–/-/g' \
        -e 's/…/.../g' \
        -e 's/©/(c)/g' \
        -e 's/®/(R)/g' \
        -e 's/™/(TM)/g' \
        "$f" > "$TEMP_DIR/$fname"
done

# Build list of preprocessed files
PROCESSED_FILES=()
for f in "${FILES[@]}"; do
    PROCESSED_FILES+=("$TEMP_DIR/$(basename $f)")
done

pandoc "${PROCESSED_FILES[@]}" \
    -o "$OUTPUT" \
    --pdf-engine=pdflatex \
    --toc \
    --toc-depth=2 \
    --top-level-division=chapter \
    --highlight-style=tango \
    -V geometry:margin=1in \
    -V fontsize=11pt \
    -V documentclass=book \
    -V colorlinks=true \
    -V linkcolor=blue \
    -V urlcolor=blue \
    -V toccolor=black \
    -V lang=es \
    --metadata title="Domesticando la Maquina" \
    --metadata author="Nestor Wheelock" \
    --metadata date="Enero 2026"

if [ $? -eq 0 ]; then
    echo "PDF creado: $OUTPUT"
    ls -lh "$OUTPUT"
else
    echo "Fallo la generacion del PDF"
    exit 1
fi
