# Usage Guide

Everything about running and configuring the dashboard day-to-day.

## Starting & stopping

| Action | Command |
|---|---|
| Start (foreground) | `uv run python dashboard.py` |
| Start (background, Windows) | `start.bat` |
| Stop (background instance) | `stop.bat` |
| Dashboard URL | <http://localhost:8765> |

Logs from a background run land in `_server.log` / `_server.err.log` next to the script (both git-ignored).

## What the status cards mean

| Card | Meaning |
|---|---|
| **Session usage** | Your share of the session capacity, resets on a rolling 5 h window |
| **Weekly usage** | Your share of the weekly capacity, rolling 7 days |
| **Datenquelle** | Which source provided the values: `Ollama API` (Bearer key, undocumented `/api/usage`) or `Settings-Cookie` (scraped from ollama.com/settings) |

Bars turn amber at ≥ 70 % and red at ≥ 90 %.

### Reset lines

- With the **cookie source merged in**: `Reset in 1 Std 4 Min · um 03.10., 11:00 Uhr` — countdown plus absolute local time
- With **API-only** data: `kein fester Reset (Sliding-Window)` — the API endpoint exposes no reset timestamps; capacity frees up gradually after each request instead

## Peak vs. off-peak

- **Peak** applies 12:00–18:00 **UTC** on weekdays (Mon–Fri)
- Outside that window, and on weekends, prices are **off-peak**
- The toolbar badge shows the current phase and counts down to the next *real* phase change (weekend 12:00 UTC boundaries are skipped — nothing changes there)
- The parenthetical hint translates the window into your local timezone and follows DST automatically

Use the toggle to re-sort the table by peak or off-peak prices.

## Sorting

Click a column header to sort by it; click again to reverse. Family rows without own prices (e.g. `gpt-oss`) sort by their cheapest variant, and variant sub-rows (`:120b`, `:20b`) are ordered by the same criterion as the table.

## Refresh behavior

| Data | Auto-refresh | Manual |
|---|---|---|
| Usage | every 60 s | "Jetzt aktualisieren" button |
| Models+pricing | every 10 min | same button |

Both honor a server-side cache (usage 30 s, models 10 min); the button forces a fetch bypassing it.

## Configuration details

Resolution order for both settings:
1. `config.json` next to `dashboard.py` (preferred)
2. Environment variables `OLLAMA_API_KEY` / `OLLAMA_SESSION_COOKIE`

A cookie value without a `=` is assumed to be the bare `__Secure-session` value and wrapped automatically. If `config.json` is malformed JSON, the dashboard logs a warning and falls back to env vars.

## API endpoints (local)

| Endpoint | Purpose |
|---|---|
| `GET /api/models` | Merged model+pricing rows (`?refresh=1` forces fetch) |
| `GET /api/usage` | Usage payload incl. `resets_at` when the cookie source has it (`?refresh=1`) |
| `GET /api/health` | `{api_key_configured, session_cookie_configured}` booleans |