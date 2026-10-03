# Ollama Cloud Dashboard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/github/v/tag/leckminartor/ollama-cloud-dashboard)](https://github.com/leckminartor/ollama-cloud-dashboard/releases)
[![CI](https://github.com/leckminartor/ollama-cloud-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/leckminartor/ollama-cloud-dashboard/actions)

A local web dashboard for your Ollama Cloud subscription: every current cloud model with peak & off-peak pricing, sortable by name or cost, plus **session usage** (5 h window) and **weekly usage** with reset countdowns.

*by Klaus Perner*

**By [Klaus Perner](https://github.com/leckminartor)** · [☕ Buy me a coffee](https://paypal.me/klausminator)

## Features

- **Model table** – all current Ollama Cloud models with input / cached / output prices (per 1 M tokens)
- **Peak & Off-Peak toggle** – peak applies 12:00–18:00 UTC on weekdays; the dashboard shows the current phase as a live badge with a local-time countdown, and the peak window translated to your timezone
- **Usage panel** – session (5 h) and weekly (7 days) usage with progress bars, reset countdown *and* absolute local reset time (cookie source)
- **Usage sources with fallback** – undocumented `/api/usage` API first, settings-page scrape (`__Secure-session` cookie) as fallback; both merged when available
- **Sorting** – click any column header; family rows like `gpt-oss` sort by their cheapest variant
- **Auto-refresh** – usage every 60 s, models every 10 min, manual refresh button
- **Variant sub-rows** – e.g. `gpt-oss:120b` / `gpt-oss:20b` with their own prices

## Quick start

```powershell
uv sync                          # once: creates venv + installs deps
uv run python dashboard.py       # starts http://localhost:8765
```

Open **http://localhost:8765** in your browser. Requires [uv](https://docs.astral.sh/uv/); plain `pip install -e .` works too (Python 3.12+).

## Configuration (optional, for usage display)

Model list and pricing work **without** any credentials. For *session usage* / *weekly usage* you need one or both of:

### 1. API key (recommended first step)

1. Create a key at <https://ollama.com/settings/keys>
2. Copy `config.example.json` to `config.json` and fill it in:

```json
{
  "api_key": "your-key-here",
  "session_cookie": ""
}
```

Note: `GET /api/usage` is **undocumented** — it exists (per community) but may not return everything; reset timestamps always come from the cookie source (see below).

### 2. Session cookie (for reset times)

1. Log in at <https://ollama.com/settings> in your browser
2. Open DevTools (F12) → *Network* tab → reload the page → click the first request (`settings`) → copy the *Cookie* request header
3. Put it in `config.json` (whole cookie string or just the `__Secure-session` value):

```json
{
  "api_key": "",
  "session_cookie": "__Secure-session=eyJ...; other=..."
}
```

The cookie expires periodically — the dashboard then shows `cookie rejected (redirected to sign-in)` and you simply copy a fresh one.

Environment variables work as well: `OLLAMA_API_KEY`, `OLLAMA_SESSION_COOKIE`.

> ⚠️ `config.json` contains secrets and is git-ignored. Never commit it.

## Data sources

| Data | Source |
|---|---|
| Model list | `GET https://ollama.com/api/tags` (official, public) |
| Prices | `https://ollama.com/pricing` (HTML parse) |
| Usage (try 1) | `GET https://ollama.com/api/usage` with Bearer key (undocumented — no reset timestamps, sliding windows) |
| Usage (fallback / reset times) | `https://ollama.com/settings` with session cookie (HTML parse) |
| Plan info | `POST https://ollama.com/api/me` with Bearer key |

## Limitations / notes

- As of September 2026 there is **no official usage API** (several open GitHub issues: ollama/ollama #12532, #16448, …) — hence the fallback chain above.
- The pricing parser targets the current HTML structure of `ollama.com/pricing`. If Ollama restructures the page, the dashboard shows a clear error message.
- Reset timestamps are read from the settings page; `/api/usage` exposes none. Session/weekly windows behave as sliding windows — capacity frees up some time after each request.
- Development server (Flask built-in) — intended for local use only.

## Documentation

- [docs/usage.md](docs/usage.md) – detailed usage & configuration guide
- [docs/troubleshooting.md](docs/troubleshooting.md) – common errors and fixes
- [CHANGELOG.md](CHANGELOG.md) – version history
- [CONTRIBUTING.md](CONTRIBUTING.md) – how to contribute

## Contributing

Issues and PRs are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and conventions. Please run `uv run ruff check .` before submitting.

## Support

If this dashboard saves you money or time, consider

☕ **[Buy me a coffee on PayPal](https://paypal.me/klausminator)**

## License

[MIT](LICENSE) © 2026 Klaus Perner