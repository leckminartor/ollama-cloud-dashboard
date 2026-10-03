# Contributing

Thanks for considering a contribution! This project is intentionally small and dependency-light — when in doubt, prefer the simplest change that works.

## Development setup

```powershell
git clone https://github.com/leckminartor/ollama-cloud-dashboard.git
cd ollama-cloud-dashboard
uv sync                 # creates .venv and installs all deps
uv run python dashboard.py
```

Open <http://localhost:8765>. No credentials are needed for the model/pricing table; see the main README's *Configuration* section if you want to work on the usage panel.

## Project layout

```
dashboard.py          # single-file backend: fetching, parsing, caching, Flask app
templates/index.html  # page skeleton
static/app.js         # frontend logic (sorting, usage cards, peak/off-peak badge)
static/style.css      # styling
tests/                # (optional) pytest tests
```

## Conventions

- **Python**: 3.12+, 120-char lines, `ruff` for lint (`uv run ruff check .` / `uv run ruff format .`)
- **No new dependencies** without discussion; httpx + BeautifulSoup + Flask cover the scope
- **Parsing resilience**: scrapers must fail with clear error messages (`ValueError`) when the upstream HTML changes, never silently render wrong data
- **Secrets**: never commit `config.json` or real cookies/keys; use `config.example.json` placeholders in docs

## Commits

Use plain, descriptive commit messages (`fix: weekly usage reset ignored`, `feat: off-peak badge`). No strict convention enforced.

## Pull requests

1. Fork/branch from `main`
2. Keep the change surgical — one concern per PR
3. Run `uv run ruff check .` and a quick manual smoke test (`uv run python dashboard.py`, then click through)
4. Describe what changed and why; link the issue if there is one

## Reporting bugs

Open an issue with: what you did, what you expected, what happened (include the dashboard's error box text). For parsing breakages, note the date — Ollama occasionally changes their HTML.