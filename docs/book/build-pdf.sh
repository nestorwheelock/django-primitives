#!/bin/bash
# Build PDF from markdown chapters

BOOK_DIR="/home/nwheelo/projects/django/django-primitives/docs/book"
OUTPUT="$BOOK_DIR/constraining-the-machine-proof.pdf"

# Order of chapters
FILES=(
    "$BOOK_DIR/00-title.md"
    "$BOOK_DIR/00-copyright.md"
    "$BOOK_DIR/00-introduction.md"
    # Part 1: The Lie
    "$BOOK_DIR/part-1-title.md"
    "$BOOK_DIR/part-1-the-lie/ch01-modern-software-is-old.md"
    "$BOOK_DIR/part-1-the-lie/ch02-ai-does-not-understand-business.md"
    "$BOOK_DIR/part-1-the-lie/ch03-you-will-refactor-later.md"
    # Part 2: The Primitives
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
    # Part 3: Constraining the Machine
    "$BOOK_DIR/part-3-title.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch19-the-instruction-stack.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch20-prompt-contracts.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch21-schema-first-generation.md"
    "$BOOK_DIR/part-3-constraining-the-machine/ch22-forbidden-operations.md"
    # Part 4: Composition
    "$BOOK_DIR/part-4-title.md"
    "$BOOK_DIR/part-4-composition/ch23-build-a-clinic.md"
    "$BOOK_DIR/part-4-composition/ch24-build-a-marketplace.md"
    "$BOOK_DIR/part-4-composition/ch25-build-a-subscription-service.md"
    "$BOOK_DIR/part-4-composition/ch26-build-a-government-form-workflow.md"
    # Conclusion
    "$BOOK_DIR/ch27-conclusion.md"
)

echo "Building PDF from ${#FILES[@]} chapters..."

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
        -e 's/📝/[note]/g' \
        -e 's/🔧/[fix]/g' \
        -e 's/🎯/[goal]/g' \
        -e 's/💡/[tip]/g' \
        -e 's/🛑/[STOP]/g' \
        -e 's/📋/[list]/g' \
        -e 's/📊/[chart]/g' \
        -e 's/🔨/[build]/g' \
        -e 's/🔄/[cycle]/g' \
        -e 's/🎓/[learn]/g' \
        -e 's/🚨/[alert]/g' \
        -e 's/🛠️/[tools]/g' \
        -e 's/🛠/[tools]/g' \
        -e 's/💰/[money]/g' \
        -e 's/🐛/[bug]/g' \
        -e 's/🤖/[AI]/g' \
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
    --metadata title="Constraining the Machine" \
    --metadata author="Nestor Wheelock" \
    --metadata date="January 2026"

if [ $? -eq 0 ]; then
    echo "PDF created: $OUTPUT"
    ls -lh "$OUTPUT"
else
    echo "PDF generation failed"
    exit 1
fi
