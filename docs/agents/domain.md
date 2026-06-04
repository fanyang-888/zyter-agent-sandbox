# Domain Docs Layout: Single-Context

## Layout

```
prototype/
├── CONTEXT.md          ← primary domain reference (read this first)
└── docs/
    └── adr/            ← architecture decision records
        └── *.md
```

## Rules for skills reading these files

1. **Always read `CONTEXT.md` first** before any architecture or diagnosis task.
   It defines the domain vocabulary (Agent, Collection, Grounded claim, etc.)
   and the in-scope vs out-of-scope boundaries for Sprint 1.

2. **Check `docs/adr/`** for past architectural decisions before proposing changes.
   If an ADR exists for a component you're touching, honour it unless the user
   explicitly overrides it.

3. **Do not invent domain terms.** If a concept isn't in `CONTEXT.md`, ask before
   naming it — naming consistency matters across the capability cards and agent specs.

4. **Scope awareness.** Sprint 1 = local prototype only. Do not propose AWS
   infrastructure changes, LangGraph V2 patterns, or PHI handling unless the user
   explicitly starts a Sprint 2 conversation.

## Adding ADRs

When an architectural decision is made, create a new file:

```
docs/adr/NNNN-short-title.md
```

Template:

```markdown
# ADR-NNNN: Title

**Status**: Accepted | Superseded by ADR-XXXX | Deprecated  
**Date**: YYYY-MM-DD  
**Deciders**: Fan Yang, [others]

## Context
What problem does this decision solve?

## Decision
What was decided?

## Consequences
What are the trade-offs?
```
