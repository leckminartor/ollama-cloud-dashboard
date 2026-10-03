# Troubleshooting

Common problems and how to fix them.

## "Keine Zugangsdaten konfiguriert"

No API key **and** no cookie are set. Add one of them via `config.json` (copy `config.example.json` → `config.json`) or environment variables. Model/pricing data works without credentials — only the usage panel needs them.

## `api key rejected (401)`

The API key was refused by ollama.com. Generate a fresh one at <https://ollama.com/settings/keys> and update `config.json`.

## `cookie rejected (redirected to sign-in)`

The session cookie expired — this is expected every few days. Open <https://ollama.com/settings> in the browser, copy the fresh cookie header (DevTools → Network → first request), and replace the value in `config.json`.

## Reset times missing (`kein fester Reset (Sliding-Window)`)

Shown when only the **API** source is active — `/api/usage` has no reset timestamps by design. Add the session cookie (see README section 2) and the reset countdowns appear automatically after the next usage refresh.

## "pricing table not found on page - Ollama may have changed the HTML structure"

The pricing scraper could not find the expected table — Ollama restructured `ollama.com/pricing`. Check whether the page still shows a plain model/price table; if yes, the parser needs updating (please open an issue with the date). Model list data is unaffected.

## Port 8765 already in use

Another dashboard instance (e.g. started via `start.bat`) is still running. Use `stop.bat` or kill the process, then start again.

## Prices look wrong / old

Pricing caches for 10 min — press **Jetzt aktualisieren** to bypass the cache. Ollama's peak/off-peak distinction means a "high" price during European evenings is usually correct (peak = 12:00–18:00 UTC).

## Fonts/symbols look off (`–` vs `-`)

Cosmetic only; the dashboard uses German number/date formatting in the UI. All times shown are your local timezone; window definitions are UTC as Ollama defines them.

## Nothing loads at all

- Check `_server.err.log` for tracebacks
- Confirm `uv sync` has been run (missing deps fail at import)
- Ensure nothing proxies/blocks `https://ollama.com` from your machine

## Still stuck?

Open a [GitHub issue](https://github.com/leckminartor/ollama-cloud-dashboard/issues) with the error text and the timestamp shown under "Modelle aktualisiert".