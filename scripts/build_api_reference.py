"""Generate docs/API.md from the application's own OpenAPI schema.

Written rather than hand-maintained so the reference cannot drift from the
code: it is built by importing the app, so anything added, removed or renamed
shows up the next time this runs.

Role requirements are not expressed in OpenAPI, so they are recovered by
reading each router for the dependency guarding the endpoint.

    python scripts/build_api_reference.py
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "API.md"

GROUPS = [
    ("auth", "Authentication",
     "Sign in, sign out and introspect the current session."),
    ("atlas", "Registry and GIS (Model 1)",
     "The camera registry: onboarding, metadata, search, export, gap analysis and the audit trail."),
    ("bridge", "Feed integration (Model 3)",
     "Live ingest control and the video relay. The scheduler multiplexes cameras through a "
     "concurrency budget; these endpoints start, stop and pin streams and expose health."),
    ("insight", "Analytics and trace",
     "Plate reads at three levels of grouping, scene analytics, the vehicle route reconstruction "
     "and the output report export."),
    ("watch", "Watchlist and alerting",
     "The watchlist registry, the alert queue and its acknowledgement workflow, and "
     "government-database correlation."),
    ("sync", "Edge to central sync",
     "The federation boundary. Mounted **only when `SUTRA_ROLE=central`**."),
]

AUTH_LABEL = {
    "require_roles": "admin or operator",
    "current_user": "any signed-in user",
    "verify_media_access": "media cookie or bearer",
    "require_sync_key": "`X-Sync-Key` header",
    None: "none",
}

DEP_ORDER = ("require_roles", "require_sync_key", "verify_media_access", "current_user")
# Guards called inside the function body rather than declared as a dependency.
# Only these two are safe to detect this way; "current_user" appears too
# often as an ordinary name to infer anything from its presence in a body.
BODY_GUARDS = ("require_sync_key", "verify_media_access")


def schema() -> dict:
    """Import the app as the central tier so every router, including sync, mounts."""
    code = (
        "import json, os; os.environ['SUTRA_ROLE'] = 'central'; "
        "from app.main import app; print(json.dumps(app.openapi()))"
    )
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)
    env = {**os.environ, "SUTRA_ROLE": "central"}
    out = subprocess.run([str(py), "-c", code], cwd=BACKEND,
                         capture_output=True, text=True, env=env)
    if out.returncode:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def _dep_names(node) -> set:
    """Every Depends(...) argument named anywhere under an AST node."""
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and getattr(sub.func, "id", "") == "Depends":
            for arg in sub.args:
                if isinstance(arg, ast.Name):
                    names.add(arg.id)
                elif isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                    names.add(arg.func.id)
        elif isinstance(sub, ast.Name):
            names.add(sub.id)
    return names


def guards() -> dict:
    """Map (METHOD, path) to the auth dependency guarding that endpoint.

    OpenAPI carries no role information, so the routers are parsed instead.
    The dependency can sit in the decorator (`dependencies=[Depends(...)]`) or
    in the signature, so both are searched.
    """
    found = {}
    files = sorted((BACKEND / "app" / "routers").glob("*.py")) + [BACKEND / "app" / "main.py"]
    for f in files:
        src = f.read_text(encoding="utf-8")
        tree = ast.parse(src)
        prefix = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "APIRouter":
                for kw in node.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = kw.value.value
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                holder = getattr(fn.value, "id", "")
                if not (isinstance(fn, ast.Attribute) and holder in ("router", "app")):
                    continue
                method = fn.attr.upper()
                if method not in ("GET", "POST", "PATCH", "DELETE", "PUT"):
                    continue
                path = ""
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    # strip Starlette converters ("{rel_path:path}") so the key
                    # matches the path as OpenAPI reports it
                    path = re.sub(r":[^}]+}", "}", dec.args[0].value)
                names = _dep_names(dec) | _dep_names(node.args)
                body_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                names |= {g for g in BODY_GUARDS if g in body_names}
                dep = next((n for n in DEP_ORDER if n in names), None)
                found[(method, ("" if holder == "app" else prefix) + path)] = dep
    return found


def row(method: str, path: str, op: dict, dep) -> str:
    desc = (op.get("description") or "").strip().split("\n")[0]
    purpose = (desc or op.get("summary") or "-").replace("|", "\\|")
    if len(purpose) > 110:
        purpose = purpose[:107].rstrip() + "..."
    return f"| `{method}` | `{path}` | {AUTH_LABEL[dep]} | {purpose} |"


def main() -> int:
    spec = schema()
    guard = guards()
    total = sum(len(v) for v in spec["paths"].values())

    L = []
    w = L.append
    w("# SUTRA - API reference")
    w("")
    w("Generated from the application's own OpenAPI schema by")
    w("`scripts/build_api_reference.py`, so it cannot drift from the code.")
    w("Regenerate after changing any route:")
    w("")
    w("```")
    w("python scripts/build_api_reference.py")
    w("```")
    w("")
    w("Every running instance also serves an interactive version at `/docs` and")
    w("the raw schema at `/openapi.json`.")
    w("")
    w(f"**{total} endpoints.** The base URL is the instance root:")
    w("`https://sutra-central.onrender.com` for the hosted central tier, or")
    w("`http://localhost:8010` for a local edge node.")
    w("")
    w("## Authentication")
    w("")
    w("`POST /api/auth/login` returns a JWT and sets an HttpOnly media cookie.")
    w("Send the token as `Authorization: Bearer <token>` on API calls. The cookie")
    w("exists because `<img>` tags and WebSocket handshakes cannot carry a header;")
    w("it authenticates `/data/...` evidence and the alert socket.")
    w("")
    w("Three roles, enforced server side rather than only in the interface:")
    w("")
    w("| Role | Can |")
    w("|---|---|")
    w("| `admin` | everything |")
    w("| `operator` | everything except user administration, scoped to their department |")
    w("| `viewer` | read only - every state-changing endpoint returns 403 |")
    w("")
    w("The sync endpoint uses no session at all. It is authenticated by a shared")
    w("`X-Sync-Key` header, because it is called by an edge node rather than by a person.")
    w("")
    w("## Conventions")
    w("")
    w("- Timestamps are ISO-8601. The output report carries both UTC and IST.")
    w("- Errors return `{\"detail\": \"...\"}` with a conventional status code:")
    w("  401 unauthenticated, 403 wrong role, 404 not found, 422 validation.")
    w("- List endpoints take `limit`; most also take `hours` to bound the window.")
    w("- Evidence images are served from `/data/{path}` and require authentication.")
    w("")

    for tag, title, blurb in GROUPS:
        rows = [(m.upper(), p, o)
                for p, ops in spec["paths"].items()
                for m, o in ops.items()
                if tag in o.get("tags", [])]
        if not rows:
            continue
        w(f"## {title}")
        w("")
        w(blurb)
        w("")
        w("| Method | Path | Auth | Purpose |")
        w("|---|---|---|---|")
        for method, path, op in sorted(rows, key=lambda r: (r[1], r[0])):
            w(row(method, path, op, guard.get((method, path))))
        w("")

    untagged = [(m.upper(), p, o)
                for p, ops in spec["paths"].items()
                for m, o in ops.items()
                if not o.get("tags")]
    if untagged:
        w("## Service and media")
        w("")
        w("Not part of a feature area: liveness, runtime introspection and the")
        w("authenticated evidence store.")
        w("")
        w("| Method | Path | Auth | Purpose |")
        w("|---|---|---|---|")
        for method, path, op in sorted(untagged, key=lambda r: r[1]):
            w(row(method, path, op, guard.get((method, path))))
        w("")

    w("## Worked example")
    w("")
    w("Sign in, then export the output report:")
    w("")
    w("```bash")
    w("TOKEN=$(curl -s -X POST http://localhost:8010/api/auth/login \\")
    w("  -H 'Content-Type: application/json' \\")
    w("  -d '{\"username\":\"admin\",\"password\":\"...\"}' | jq -r .token)")
    w("")
    w("curl -s -H \"Authorization: Bearer $TOKEN\" \\")
    w("  'http://localhost:8010/api/insight/report?since=2026-09-26T00:00:00Z' \\")
    w("  -o output_report.csv")
    w("```")
    w("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} - {total} endpoints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
