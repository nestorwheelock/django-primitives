# Chapter 3: You Will Not Refactor Later

> "We'll clean this up after launch" is the most expensive lie in software.

## The Lie

"We'll refactor later."

No. You won't. Later never comes. Technical debt compounds. The mess becomes load-bearing.

## What This Chapter Covers

- Why "later" is a fiction
- How shortcuts become architecture
- The cost of deferred correctness
- Why primitives must be right from the start

## Key Points

1. **Debt Compounds** - Every shortcut breeds more shortcuts
2. **Mess Becomes Canon** - New code adapts to old mess
3. **Refactoring Requires Slack** - You will never have slack
4. **Primitives Are Foundation** - You cannot refactor foundations

## The Math

```
Day 1:   "Quick hack, we'll fix it"
Day 30:  3 systems depend on the hack
Day 90:  The hack is now "how we do things"
Day 180: New hire asks why, nobody remembers
Day 365: Hack is in production, documented, defended
```

Build it right or build it twice. You won't get a third chance.

---

*Status: Planned*
