## What this changes

<!-- The behaviour that differs, in one or two sentences. -->

## Why

<!-- The reasoning, and any measurement behind it. This is the expensive part
     to reconstruct later — a number here saves someone re-deriving it. -->

## How it was verified

<!-- Tests alone are not enough for anything observable in the UI or on the
     hosted tier. Say what you actually drove, and what you saw. -->

- [ ] `cd backend && ../.venv/Scripts/python -m pytest -q` passes
- [ ] `npm run build --prefix frontend` builds clean
- [ ] Exercised in the running UI, if user-visible
- [ ] Checked against the hosted tier, if it touches sync, schema or deployment

## Risk

<!-- What breaks if this is wrong, and how it is reverted. Note explicitly if
     it touches: database schema, the edge↔central contract, portal
     credentials, or anything an operator acts on. -->

- [ ] No secrets, credentials or tokens added to the repository
- [ ] Schema changes work on **both** SQLite (edge) and Postgres (central)
- [ ] Any new runtime file ships inside the package, not in gitignored `data/`
