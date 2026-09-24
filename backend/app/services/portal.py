"""Hackathon feed portal access: credentials, session, and URL handling.

The Sentinel Camera Grid (cctv.corp8.cloud) gates everything behind a
registered email and a system-issued access password:

  * the catalogue (`/cameras.json`) and the HLS playlists/segments want the
    session cookie a form login sets, and the HLS paths additionally refuse
    clients that do not look like a browser (a 403 "browser required");
  * the RTSP/WebRTC gateway (mediamtx on a public IP that Cloudflare cannot
    proxy) authenticates every connection with the same email and password
    embedded in the URL.

Credentials live only in the environment (`SUTRA_PORTAL_EMAIL` /
`SUTRA_PORTAL_PASSWORD`, normally via backend/.env). The registry stores
credential-free URLs; this module injects credentials at the moment a stream is
opened and strips them from anything that is logged or shown to an operator.
"""

import logging
import threading
import time
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from ..config import settings

log = logging.getLogger("sutra.portal")

# Without a browser-like UA the portal answers HLS requests with 403 even when
# the session cookie is valid; the catalogue does not care.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

_session_lock = threading.Lock()
_cookie: dict[str, str] = {}
_cookie_at = 0.0
_COOKIE_MAX_AGE_S = 6 * 3600   # the portal issues a year; re-login well before that anyway


class PortalAuthError(RuntimeError):
    """Raised when the portal cannot be logged into with the configured credentials."""


def configured() -> bool:
    return bool(settings.portal_email and settings.portal_password)


def redact(text: str) -> str:
    """Strip the portal credentials (raw and URL-encoded) from free text."""
    if not text:
        return text
    for secret in (settings.portal_password, quote(settings.portal_password, safe="")):
        if secret:
            text = text.replace(secret, "***")
    for ident in (settings.portal_email, quote(settings.portal_email, safe="")):
        if ident:
            text = text.replace(ident, "<portal-user>")
    return text


def redact_url(url: str) -> str:
    """Return a URL with any userinfo (user:password@) removed."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return redact(url)
    if not parts.username and not parts.password:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def is_portal_rtsp(url: str) -> bool:
    """True when `url` points at the portal's RTSP gateway (credentials required)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return (
        parts.scheme == "rtsp"
        and (parts.hostname or "") == settings.portal_rtsp_host
        and (parts.port or 554) == settings.portal_rtsp_port
    )


def is_portal_http(url: str) -> bool:
    """True when `url` lives on the portal's CDN host (cookie + UA required)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    base = urlsplit(settings.portal_base)
    return parts.scheme in ("http", "https") and parts.hostname == base.hostname


def authenticate_url(url: str) -> str:
    """Inject the portal credentials into a portal RTSP URL; other URLs pass
    through untouched. The email's '@' must be percent-encoded or the URL
    parser reads it as the host separator."""
    if not is_portal_rtsp(url) or not configured():
        return url
    if urlsplit(url).username:
        return url   # already carries credentials
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    userinfo = f"{quote(settings.portal_email, safe='')}:{quote(settings.portal_password, safe='')}"
    return urlunsplit((parts.scheme, f"{userinfo}@{host}", parts.path, parts.query, parts.fragment))


def login(force: bool = False) -> dict[str, str]:
    """Return the session cookie for the portal's HTTP side, logging in once
    and caching it. Thread-safe; re-logs in when the cookie is stale."""
    global _cookie, _cookie_at
    if not configured():
        raise PortalAuthError(
            "portal credentials not configured (SUTRA_PORTAL_EMAIL / SUTRA_PORTAL_PASSWORD)"
        )
    with _session_lock:
        if _cookie and not force and time.monotonic() - _cookie_at < _COOKIE_MAX_AGE_S:
            return dict(_cookie)
        try:
            r = httpx.post(
                f"{settings.portal_base}/auth/login",
                data={"email": settings.portal_email, "password": settings.portal_password},
                headers={"User-Agent": BROWSER_UA},
                timeout=30,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise PortalAuthError(f"portal login failed: {redact(str(exc))}") from exc
        # a successful login answers with a redirect to the grid and a cookie;
        # a rejected one re-renders the form (200) without one
        if not r.cookies:
            raise PortalAuthError(
                f"portal rejected the configured credentials (HTTP {r.status_code})"
            )
        _cookie = dict(r.cookies)
        _cookie_at = time.monotonic()
        log.info("portal: logged in (cookie %s)", ", ".join(_cookie))
        return dict(_cookie)


def http_headers(url: str = "") -> dict[str, str]:
    """Headers that make the portal's HTTP side serve a non-browser client:
    browser UA plus the session cookie. Non-portal URLs get nothing."""
    if url and not is_portal_http(url):
        return {}
    cookie = login()
    return {
        "User-Agent": BROWSER_UA,
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookie.items()),
    }


def get(path: str, *, retry_auth: bool = True) -> httpx.Response:
    """GET a portal path with the session; one automatic re-login when the
    portal bounces the request to its login page or refuses the session."""
    url = path if path.startswith("http") else f"{settings.portal_base}{path}"
    r = httpx.get(url, headers=http_headers(url), timeout=30, follow_redirects=False)
    if r.status_code in (302, 401, 403) and retry_auth:
        login(force=True)
        return get(path, retry_auth=False)
    r.raise_for_status()
    return r
