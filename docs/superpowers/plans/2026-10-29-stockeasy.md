# Stockeasy Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task. User authorized direct execution of the recommended dashboard.

**Goal:** Deliver a local Chinese market dashboard backed by AKShare and yfinance and sync source to stockeasy.
**Architecture:** Provider adapters normalize market data; SQLite stores historical data, quotes, and watchlist. Streamlit renders an interactive Plotly dashboard with explicit live/cache/demo provenance.
**Tech Stack:** Python >=3.11, Streamlit, pandas, Plotly, AKShare, yfinance; unittest for core tests.
**Spec:** docs/superpowers/specs/2026-10-29-stockeasy-design.md

## Global Constraints
- Local single-user app; no trading, account access, or public deployment.
- Keep cache/user files out of public repository. Never pass demo data off as market data.
- Label source, currency, time and adjustment; free quotes carry no guaranteed delay.

## Review Focus
- Empty or malformed upstream responses must not appear as fresh quotes.
- Yahoo multi-index/timezone data and Chinese column names normalize consistently.
- Failed refresh returns only the same instrument/adjustment's cache with stale status.
- Short/zero/NaN price series must not generate misleading performance metrics.
- Offline/demo use remains functional and never contaminates real data storage.

### Task 1: Data and analytics
Files: stockeasy/models.py, providers.py, storage.py, service.py, analytics.py; tests/test_core.py.
Interfaces: Instrument(key, symbol, name, market, currency); MarketService.history(instrument,start,end,adjust,force=False)->DataResult; MarketService.quote(instrument,force=False)->QuoteResult.
- [x] Write failing tests for normalization, return/drawdown, cache fallback, date/adjustment separation and watchlist persistence; run unittest and observe missing implementation.
- [x] Implement providers and bounded requests, SQLite persistence, cached retrieval, validated symbols and calculations.
- [x] Run core suite and record results.

### Task 2: Dashboard
Files: app.py, stockeasy/demo.py, stockeasy/charts.py, .streamlit/config.toml, requirements.txt, tests/test_app.py.
- [x] Add failing Streamlit smoke tests for demo rendering and invalid symbol validation.
- [x] Implement sidebar settings, watchlist editor, quote cards, filtered watchlist, historical analysis, exports, refresh and explicit demo mode.
- [x] Verify with Streamlit AppTest and actual browser interactions/screenshots.

### Task 3: Delivery
Files: README.md, .gitignore, docs/ci-tests.yml, docs/verification.md.
- [x] Probe both upstream providers and document current connectivity without promising availability.
- [x] Run full test suite, review independently, inspect public file set for generated/private data.
- [x] Sync source to authorized public repository and verify remote file/commit; open local dashboard.

Delivery note: GitHub rejected workflow writes under current OAuth scope. Kept the configuration as docs/ci-tests.yml instead of requesting broader permissions. Source push to main succeeded and app.py was read back through the GitHub connector.
