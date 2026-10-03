"""Ollama Cloud Dashboard - local web dashboard for models, pricing and usage.

Author: Klaus Perner

Data sources (verified):
- Model list:   GET https://ollama.com/api/tags            (public JSON)
- Pricing:      GET https://ollama.com/pricing             (public HTML, parsed)
- Usage (try):  GET https://ollama.com/api/usage           (undocumented, Bearer API key)
- Usage (fallback): GET https://ollama.com/settings        (HTML, needs __Secure-session cookie)
- Plan info:    POST https://ollama.com/api/me             (Bearer API key)
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template

log = logging.getLogger("dashboard")

__version__ = "1.0.0"
__author__ = "Klaus Perner"

BASE_URL = "https://ollama.com"
SETTINGS_URL = f"{BASE_URL}/settings"
PRICING_URL = f"{BASE_URL}/pricing"
TAGS_URL = f"{BASE_URL}/api/tags"
USAGE_API_URL = f"{BASE_URL}/api/usage"
ME_API_URL = f"{BASE_URL}/api/me"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

MODELS_CACHE_TTL = 600  # 10 min
USAGE_CACHE_TTL = 30  # 30 s

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json"

_models_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}
_usage_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict[str, str]:
    """Load api_key and session_cookie from config.json, falling back to env vars."""
    import os

    cfg: dict[str, str] = {"api_key": "", "session_cookie": ""}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg["api_key"] = str(data.get("api_key") or "").strip()
                cfg["session_cookie"] = str(data.get("session_cookie") or "").strip()
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("config.json could not be read: %s", exc)
    # env fallbacks
    if not cfg["api_key"]:
        cfg["api_key"] = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not cfg["session_cookie"]:
        cfg["session_cookie"] = os.environ.get("OLLAMA_SESSION_COOKIE", "").strip()
    # tolerate a raw cookie value (only the value of __Secure-session)
    raw = cfg["session_cookie"]
    if raw and "=" not in raw:
        cfg["session_cookie"] = f"__Secure-session={raw}"
    return cfg


# ---------------------------------------------------------------------------
# Pricing scraper (ollama.com/pricing HTML table)
# ---------------------------------------------------------------------------

_PricingTable = dict[str, dict[str, float | None]]


def parse_pricing(html: str) -> _PricingTable:
    """Parse the /pricing model pricing table.

    Returns a mapping: label -> {"input", "cached", "output"} in USD per 1M tokens.
    Labels look like "gpt-oss:120b" or "kimi-k3 (Off-Peak)". Prices may be "-" (unknown).
    Raises ValueError when no rows can be parsed (page structure changed).
    """
    soup = BeautifulSoup(html, "html.parser")
    table: dict[str, dict[str, float | None]] = {}
    for tbody in soup.find_all("tbody"):
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            link = cells[0].find("a")
            if link is None:
                continue
            label = link.get_text(strip=True)
            if not label:
                continue
            values: list[float | None] = []
            for cell in cells[1:4]:
                text = cell.get_text(strip=True).replace("$", "").strip()
                try:
                    values.append(float(text))
                except ValueError:
                    values.append(None)
            table[label] = {"input": values[0], "cached": values[1], "output": values[2]}
    if not table:
        raise ValueError("pricing table not found on page - Ollama may have changed the HTML structure")
    return table


def fetch_pricing(client: httpx.Client) -> _PricingTable:
    resp = client.get(PRICING_URL)
    resp.raise_for_status()
    return parse_pricing(resp.text)


def split_pricing_label(label: str) -> tuple[str, bool]:
    """Split 'kimi-k3 (Off-Peak)' into ('kimi-k3', True)."""
    m = re.match(r"^(.*?)\s*\(Off-Peak\)$", label)
    if m:
        return m.group(1).strip(), True
    return label, False


# ---------------------------------------------------------------------------
# Model list (public /api/tags)
# ---------------------------------------------------------------------------

def fetch_tags(client: httpx.Client) -> list[dict[str, Any]]:
    resp = client.get(TAGS_URL)
    resp.raise_for_status()
    data = resp.json()
    models = data.get("models") or []
    return models if isinstance(models, list) else []


def base_name(name: str) -> str:
    """'mistral-large-3:675b' -> 'mistral-large-3'; 'gpt-oss:120b' -> 'gpt-oss'."""
    return name.split(":", 1)[0]


def build_models_payload(client: httpx.Client) -> list[dict[str, Any]]:
    """Merge /api/tags model list with pricing table into display rows."""
    tags = fetch_tags(client)
    pricing = fetch_pricing(client)

    # Index pricing rows by base name. Family-level rows (e.g. "gemma4") map to
    # the base directly; variant-level rows (e.g. "gpt-oss:120b", where several
    # variants differ in price) are kept as sub-rows below the family entry.
    tag_names = {m.get("name") or m.get("model") or "" for m in tags}
    tag_names.discard("")
    by_base: dict[str, dict[str, Any]] = {}
    for label, prices in pricing.items():
        base, offpeak = split_pricing_label(label)
        rate = "offpeak" if offpeak else "peak"
        if label in tag_names and ":" in label:
            # variant-specific pricing: store under the family base, keyed by full label
            family = base_name(label)
            entry = by_base.setdefault(family, {"peak": {}, "offpeak": {}, "variants": {}})
            entry["variants"][label] = entry["variants"].get(label) or {}
            entry["variants"][label][rate] = prices
        else:
            entry = by_base.setdefault(base, {"peak": {}, "offpeak": {}, "variants": {}})
            entry[rate] = prices

    models_by_base: dict[str, list[str]] = {}
    for m in tags:
        name = m.get("name") or m.get("model") or ""
        if not name:
            continue
        models_by_base.setdefault(base_name(name), []).append(name)

    rows: list[dict[str, Any]] = []
    for base in sorted(models_by_base):
        entry = by_base.get(base, {"peak": {}, "offpeak": {}, "variants": {}})
        peak = entry["peak"]
        off = entry["offpeak"]
        row = {
            "name": base,
            "tags": sorted(models_by_base.get(base, [])),
            "input": peak.get("input"),
            "cached": peak.get("cached"),
            "output": peak.get("output"),
            "offpeak_input": off.get("input"),
            "offpeak_cached": off.get("cached"),
            "offpeak_output": off.get("output"),
            "has_pricing": bool(peak or off or entry["variants"]),
        }
        # attach variant-level prices when the family row has none of its own
        variants = []
        for vlabel, vprices in sorted(entry["variants"].items()):
            vp = vprices.get("peak", {})
            vo = vprices.get("offpeak", {})
            variants.append(
                {
                    "name": vlabel,
                    "input": vp.get("input"),
                    "cached": vp.get("cached"),
                    "output": vp.get("output"),
                    "offpeak_input": vo.get("input"),
                    "offpeak_cached": vo.get("cached"),
                    "offpeak_output": vo.get("output"),
                }
            )
        row["variants"] = variants
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Usage: undocumented API first, cookie scrape as fallback
# ---------------------------------------------------------------------------

def _coerce_pct(value: Any) -> float | None:
    """Accept 5.1, '5.1', 0.051 (fraction), '5.1%'."""
    if value is None:
        return None
    try:
        num = float(str(value).rstrip("%"))
    except (ValueError, TypeError):
        return None
    if 0 <= num <= 1:
        return num * 100
    if num <= 100:
        return num
    return None


def _find_usage_fields(obj: Any, found: dict[str, Any]) -> None:
    """Recursively look for session/weekly percentage-ish fields in an unknown JSON shape."""

    def _store(kind: str, entry: dict[str, Any]) -> None:
        """Keep the best entry: a real pct beats a placeholder claim (pct=None)."""
        existing = found.get(kind)
        if existing is None or (existing.get("pct") is None and entry.get("pct") is not None):
            found[kind] = entry

    if isinstance(obj, dict):
        lower_keys = {k.lower(): k for k in obj}
        # dict items may identify themselves via kind/window/name values, e.g.
        # {"window": "session", "percentage": 7.7} or {"kind": "weekly", "pct": 12}
        self_kind: str | None = None
        for id_key in ("kind", "window", "name", "type", "period", "id"):
            raw = obj.get(id_key)
            if isinstance(raw, str):
                low = raw.lower()
                if "session" in low or "5h" in low:
                    self_kind = "session"
                    break
                if "weekly" in low or "week" in low or "7d" in low:
                    self_kind = "weekly"
                    break
        if self_kind and (self_kind not in found or found[self_kind].get("pct") is None):
            pct = None
            for pk in ("percentage", "percent", "pct", "used", "usage", "value"):
                if pk in obj:
                    pct = _coerce_pct(obj[pk])
                    if pct is not None:
                        break
            entry: dict[str, Any] = {"pct": pct}
            reset = obj.get("reset_at") or obj.get("resets_at") or obj.get("resets") or obj.get("reset_time")
            if reset:
                entry["resets_at"] = reset
            _store(self_kind, entry)
        # match keys like "session", "session_usage", "sessionUsage"
        kind_map: dict[str, str] = {}
        for key in lower_keys:
            kl = key.lower()
            for kind in ("session", "weekly"):
                if kind in kl and (kind not in found or found[kind].get("pct") is None):
                    kind_map[kind] = key
        for kind, key in kind_map.items():
            val = obj[lower_keys[key]]
            pct = None
            if isinstance(val, dict):
                for pk in ("percentage", "percent", "pct", "used", "usage", "value"):
                    if pk in val:
                        pct = _coerce_pct(val[pk])
                        if pct is not None:
                            break
                reset = val.get("reset_at") or val.get("resets_at") or val.get("resets") or val.get("reset_time")
                entry: dict[str, Any] = {"pct": pct}
                if reset:
                    entry["resets_at"] = reset
                _store(kind, entry)
            else:
                pct = _coerce_pct(val)
                if pct is not None:
                    _store(kind, {"pct": pct})
        for v in obj.values():
            _find_usage_fields(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _find_usage_fields(item, found)


def try_usage_api(client: httpx.Client, api_key: str) -> tuple[dict[str, Any] | None, str]:
    """Attempt the undocumented GET /api/usage endpoint. Returns (usage, error)."""
    if not api_key:
        return None, "no api key configured"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = client.get(USAGE_API_URL, headers=headers)
        if resp.status_code == 401:
            return None, "api key rejected (401)"
        if resp.status_code == 404:
            return None, "usage endpoint not available (404)"
        resp.raise_for_status()
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return None, f"unexpected non-JSON response from /api/usage ({resp.status_code})"
        if not isinstance(data, dict):
            return None, "unexpected response format from /api/usage"
        found: dict[str, Any] = {}
        _find_usage_fields(data, found)
        if not found:
            log.debug("usage api returned: %s", json.dumps(data)[:2000])
            return None, "usage endpoint reachable but contained no recognizable usage data"
        return found, ""
    except httpx.HTTPError as exc:
        return None, f"usage api request failed: {exc}"


def try_fetch_plan(client: httpx.Client, api_key: str) -> dict[str, Any]:
    """Best-effort POST /api/me for plan metadata (name, subscription period)."""
    if not api_key:
        return {}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = client.post(ME_API_URL, headers=headers, json={})
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if not isinstance(data, dict):
            return {}
        plan = data.get("plan") or data.get("Plan")
        result: dict[str, Any] = {}
        if plan:
            result["plan"] = str(plan)
        for key in ("SubscriptionPeriodStart", "SubscriptionPeriodEnd"):
            if data.get(key):
                result[key] = data[key]
        return result
    except (httpx.HTTPError, json.JSONDecodeError):
        return {}


def _normalize_reset_ts(raw: str) -> str:
    """Normalize a scraped reset timestamp to an ISO string.

    Ollama's settings page embeds Unix seconds in data-time attriutes, e.g.
    '1717600000'. Community scrapers have also seen epoch milliseconds. Anything
    already ISO-shaped is passed through unchanged, so the frontend can
    Date.parse() it as before.
    """
    raw = (raw or "").strip()
    # already ISO-like (contains '-' and ':'), e.g. 2026-10-03T12:00:00Z
    if "-" in raw and ":" in raw:
        return raw
    # pure digits: epoch seconds or epoch milliseconds
    if raw.isdigit():
        n = int(raw)
        if n >= 10_000_000_000:  # ms epoch -> seconds
            n //= 1000
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(n))
    return raw


def try_usage_cookie(client: httpx.Client, cookie: str) -> tuple[dict[str, Any] | None, str]:
    """Scrape ollama.com/settings with the browser session cookie.

    Looks for aria-labels like 'Session usage 5.1%' / 'Weekly usage 42%' and
    data-time reset timestamps (community-proven approach).
    """
    if not cookie:
        return None, "no session cookie configured"
    headers = {
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = client.get(SETTINGS_URL, headers=headers, follow_redirects=False)
        if resp.status_code in (301, 302, 303):
            return None, "cookie rejected (redirected to sign-in) - refresh the session cookie"
        if resp.status_code != 200:
            return None, f"settings page returned HTTP {resp.status_code}"
        html = resp.text
    except httpx.HTTPError as exc:
        return None, f"settings request failed: {exc}"

    found: dict[str, Any] = {}
    # aria-label pattern, e.g. <div aria-label="Session usage 3.3% used">
    # (trailing text after the percentage is tolerated - Ollama changed the
    # label wording over time)
    label_matches = list(
        re.finditer(
            r'aria-label="\s*(Session|Weekly)\s+usage\s+([0-9]+(?:\.[0-9]+)?)\s*%',
            html,
            re.IGNORECASE,
        )
    )
    # ISO reset timestamps, e.g. data-time="2026-10-03T09:00:00Z" ("Resets in 1 hour.")
    time_matches = list(re.finditer(r'data-time="([^"]+)"', html))

    for i, match in enumerate(label_matches):
        kind = match.group(1).lower()
        pct = _coerce_pct(match.group(2))
        if pct is None or (kind in found and found[kind].get("pct") is not None):
            continue
        entry: dict[str, Any] = {"pct": pct}
        # first data-time after this label but before the next usage label —
        # distance is unbounded (weekly has a model list in between), so no
        # fixed-length window
        scope_end = label_matches[i + 1].start() if i + 1 < len(label_matches) else len(html)
        for tm in time_matches:
            if match.start() < tm.start() < scope_end:
                entry["resets_at"] = _normalize_reset_ts(tm.group(1))
                break
        found[kind] = entry

    if not found:
        # fallback: the width-percent parse used by community scripts
        for kind in ("session", "weekly"):
            m = re.search(
                rf"{kind}\s+usage.*?width:\s*([0-9]+(?:\.[0-9]+)?)\s*%", html, re.IGNORECASE | re.DOTALL
            )
            if m:
                found[kind] = {"pct": _coerce_pct(m.group(1))}
        if not found:
            return None, "no usage markers found on settings page (page structure may have changed)"
    return found, ""


def get_usage(cfg: dict[str, str], force: bool = False) -> dict[str, Any]:
    with _cache_lock:
        cached = _usage_cache["data"]
        if cached and not force and time.time() - _usage_cache["fetched_at"] < USAGE_CACHE_TTL:
            return cached

    def _result(payload: dict[str, Any]) -> dict[str, Any]:
        _usage_cache["data"] = payload
        _usage_cache["fetched_at"] = time.time()
        return payload

    result: dict[str, Any] = {"session": None, "weekly": None, "source": "none", "plan": None, "error": None}
    errors: list[str] = []
    api_key = cfg.get("api_key", "")
    cookie = cfg.get("session_cookie", "")

    if api_key:
        data, err = try_usage_api(get_http_client(), api_key)
        if data:
            result.update(data)
            result["source"] = "api"
            plan_info = try_fetch_plan(get_http_client(), api_key)
            if plan_info:
                result["plan"] = plan_info.get("plan")
                result["subscription"] = {
                    k: v for k, v in plan_info.items() if k != "plan"
                }
            # merge reset timestamps from the cookie source when available -
            # /api/usage has none (sliding windows), the settings page does
            if cookie:
                cookie_data, cookie_err = try_usage_cookie(get_http_client(), cookie)
                if cookie_data:
                    for kind in ("session", "weekly"):
                        reset = (cookie_data.get(kind) or {}).get("resets_at")
                        if reset:
                            if result.get(kind) is None:
                                result[kind] = {}
                            result[kind]["resets_at"] = reset
                elif cookie_err:
                    result["cookie_hint"] = cookie_err
            return _result(result)
        errors.append(f"api: {err}")

    if cookie:
        data, err = try_usage_cookie(get_http_client(), cookie)
        if data:
            result.update(data)
            result["source"] = "cookie"
            return _result(result)
        errors.append(f"cookie: {err}")

    if not api_key and not cookie:
        result["error"] = "Keine Zugangsdaten konfiguriert. API-Key und/oder Session-Cookie in config.json eintragen."
    else:
        result["error"] = "; ".join(errors)
    return _result(result)


# ---------------------------------------------------------------------------
# HTTP client + Flask app
# ---------------------------------------------------------------------------

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def get_http_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        return _client


def get_models(force: bool = False) -> dict[str, Any]:
    with _cache_lock:
        cached = _models_cache["data"]
        if cached and not force and time.time() - _models_cache["fetched_at"] < MODELS_CACHE_TTL:
            cached = dict(cached)
            cached["cached"] = True
            return cached
    try:
        rows = build_models_payload(get_http_client())
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        log.exception("model fetch failed")
        return {"models": [], "error": str(exc), "fetched_at": None}
    payload = {"models": rows, "error": None, "fetched_at": time.time()}
    with _cache_lock:
        _models_cache["data"] = payload
        _models_cache["fetched_at"] = time.time()
    return payload


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/models")
    def api_models() -> Any:
        force = False
        # cheap query parsing without importing request everywhere
        from flask import request

        force = request.args.get("refresh") == "1"
        return jsonify(get_models(force=force))

    @app.get("/api/usage")
    def api_usage() -> Any:
        from flask import request

        force = request.args.get("refresh") == "1"
        return jsonify(get_usage(load_config(), force=force))

    @app.get("/api/health")
    def api_health() -> Any:
        cfg = load_config()
        return jsonify(
            {
                "api_key_configured": bool(cfg["api_key"]),
                "session_cookie_configured": bool(cfg["session_cookie"]),
            }
        )

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    if not cfg["api_key"]:
        log.info("No API key configured - usage panel will use cookie fallback or show a hint.")
    if not cfg["session_cookie"]:
        log.info("No session cookie configured - cookie fallback unavailable.")
    app = create_app()
    print("Ollama Cloud Dashboard: http://localhost:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)


if __name__ == "__main__":
    main()