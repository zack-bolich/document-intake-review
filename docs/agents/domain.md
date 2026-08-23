# Domain docs

This repository uses a single-context domain-documentation layout.

Before exploring, read the root `CONTEXT.md` when it exists and any relevant ADRs under
`docs/adr/`. Missing domain files are created lazily when terminology or architectural decisions
are resolved.

Use the glossary vocabulary from `CONTEXT.md` consistently. Surface any proposed change that
contradicts an existing ADR rather than silently overriding it.

Expected layout:

```text
/
|-- CONTEXT.md
`-- docs/adr/
```
