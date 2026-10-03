# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-03

First public release.

### Added
- Model table with all current Ollama Cloud models and input/cached/output pricing (peak & off-peak, per 1 M tokens)
- Peak/off-peak toggle plus live phase badge with local-time countdown (weekend boundaries handled correctly)
- Peak window hint displayed in the viewer's local timezone (DST-aware)
- Session (5 h) and weekly (7 days) usage cards with progress bars and color thresholds
- Usage sources with automatic fallback: undocumented `/api/usage` API → settings-page session-cookie scrape
- Reset timestamps from the settings page shown as countdown + absolute local time; `data-time` parsing handles Unix seconds, epoch milliseconds, and ISO strings
- Honest "no fixed reset (sliding window)" hint when the active source has no reset data
- Cost sorting for variant families (e.g. `gpt-oss` sorts by its cheapest variant; variant sub-rows follow the active sort)
- Sorting on all columns with direction toggle; peak/off-peak price switch re-sorts live
- Manual refresh + auto-refresh (usage 60 s, models 10 min)
- Config via `config.json` or environment variables (`OLLAMA_API_KEY`, `OLLAMA_SESSION_COOKIE`)

[1.0.0]: https://github.com/leckminartor/ollama-cloud-dashboard/releases/tag/v1.0.0