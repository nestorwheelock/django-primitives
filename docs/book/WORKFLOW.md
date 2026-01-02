# Book Writing Workflow

This document defines the cycle for writing book chapters using LLM assistance.

---

## The Cycle

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. WRITER DRAFT                                            │
│     └─ Use WRITER_PROMPT.md                                 │
│     └─ Creative expansion, examples, flow                   │
│     └─ Output: First draft                                  │
│                                                             │
│                        ↓                                    │
│                                                             │
│  2. EDITOR REVIEW                                           │
│     └─ Use EDITOR_PROMPT.md                                 │
│     └─ Verify sources, anticipate criticism                 │
│     └─ Create report with proposed changes                  │
│     └─ Output: Editorial report + revised draft             │
│                                                             │
│                        ↓                                    │
│                                                             │
│  3. WRITER EMBELLISH                                        │
│     └─ Use WRITER_PROMPT.md                                 │
│     └─ Add texture, smooth transitions, improve readability │
│     └─ Output: Polished draft                               │
│                                                             │
│                        ↓                                    │
│                                                             │
│  4. EDITOR FINAL PASS                                       │
│     └─ Use EDITOR_PROMPT.md                                 │
│     └─ Final fact-check, consistency, sources               │
│     └─ Output: Publication-ready draft                      │
│                                                             │
│                        ↓                                    │
│                                                             │
│  5. HUMAN READ-ALOUD                                        │
│     └─ Author reads chapter aloud                           │
│     └─ Check voice, rhythm, "does this sound like me?"      │
│     └─ Catch AI patterns, cringe, awkward phrases           │
│     └─ Output: Final approval or revision notes             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## When to Use Each Role

| Role | Purpose | Prompt File |
|------|---------|-------------|
| **Writer** | Draft new content, expand ideas, add examples, improve flow | `WRITER_PROMPT.md` |
| **Editor** | Verify facts, find weak arguments, add sources, tighten prose, anticipate criticism | `EDITOR_PROMPT.md` |
| **Human** | Final voice check, rhythm, authenticity | (No prompt - author reads) |

---

## Cycle Variations

### Full Cycle (New Chapter)
```
Writer Draft → Editor Review → Writer Embellish → Editor Final → Human Read
```
Use for: New chapters, major rewrites

### Quick Cycle (Revisions)
```
Writer Revise → Editor Check → Human Read
```
Use for: Adding sections, responding to feedback

### Editorial Only
```
Editor Review → Human Approve
```
Use for: Fact-checking existing content, adding sources

---

## Commit Points

Commit after each major step:

1. After Writer Draft: `docs(book): draft ch[X] - [title]`
2. After Editor Review: `docs(book): editorial pass on ch[X]`
3. After Writer Embellish: `docs(book): writer pass on ch[X] - add texture`
4. After Editor Final: `docs(book): final edit on ch[X]`
5. After Human Read: `docs(book): ch[X] approved` or revision notes

---

## Chapter Status Markers

Use these in each chapter file:

```
*Status: Outline*        # Structure only, no prose
*Status: Draft*          # Writer pass complete
*Status: Edited*         # Editor pass complete
*Status: Polished*       # Writer embellish complete
*Status: Final*          # Editor final + Human approved
```

---

## Parallelization

While the human reads one chapter, the LLM can:
- Run 1-2 cycles on the next chapter
- Draft outlines for future chapters
- Create editorial reports for review

Example:
```
Human reads Ch1 → LLM runs Writer+Editor+Writer+Editor on Ch2
Human reviews Ch2 → LLM drafts Ch3
```

---

## Quality Gates

### Before Editor Pass
- [ ] Chapter has clear structure (sections with headings)
- [ ] Examples are concrete (not abstract)
- [ ] Core idea is stated explicitly

### Before Writer Embellish
- [ ] All factual claims are verified or flagged
- [ ] Sources are cited where needed
- [ ] Weak arguments are identified

### Before Human Read
- [ ] No unverified claims remain
- [ ] Prose flows naturally
- [ ] Transitions are smooth
- [ ] References section is complete

### Before Final Approval
- [ ] Read aloud without stumbling
- [ ] Voice sounds authentic (not AI-generic)
- [ ] No cringe phrases
- [ ] Ready for external readers

---

## File Structure

```
docs/book/
├── WORKFLOW.md           # This file
├── WRITER_PROMPT.md      # Prompt for writer role
├── EDITOR_PROMPT.md      # Prompt for editor role
├── README.md             # Book overview and status
├── 00-introduction.md    # Introduction chapter
├── part-1-the-lie/
│   ├── ch01-*.md
│   ├── ch02-*.md
│   └── ch03-*.md
├── part-2-the-primitives/
│   └── ch04-ch11-*.md
├── part-3-constraining-the-machine/
│   └── ch12-ch15-*.md
└── part-4-composition/
    └── ch16-ch19-*.md
```
