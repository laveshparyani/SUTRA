"""Repo-level test isolation — loaded by pytest BEFORE tests/conftest.py.

`backend/.env` configures a developer's machine as a live edge node (role,
central URL, sync key, portal credentials). pydantic-settings lets a real
environment variable override the dotenv file, so the test process pins every
network-facing setting to a harmless value here, before `app.config` is ever
imported:

* role `full` — matches CI (which has no .env) and mounts every router.
* central URL / sync key blank — the edge syncer must never push test rows
  to the hosted central tier.
* portal credentials blank — no test can log into the feed portal by accident
  (tests that need credentials monkeypatch fakes in).

Only variables not already set are touched, so a caller can still override.
"""

import os

_ISOLATION = {
    "SUTRA_ROLE": "full",
    "SUTRA_CENTRAL_URL": "",
    "SUTRA_SYNC_API_KEY": "",
    "SUTRA_PORTAL_EMAIL": "",
    "SUTRA_PORTAL_PASSWORD": "",
}

for _key, _value in _ISOLATION.items():
    os.environ.setdefault(_key, _value)
