# Quant Research Implementation Plan

> **For agentic workers:** Inline execution with one final independent review.

**Goal:** Integrate QuantStats, Backtesting.py and PyPortfolioOpt into Stockeasy and provide a practical WhaleQuant learning path.
**Architecture:** Pure calculation/data-preparation functions behind a separate Streamlit research page; existing provider/cache data, explicit-run forms and parameter-bound results.
**Tech Stack:** Current Python 3.12 / Streamlit / pandas / Plotly, plus quantstats, backtesting, PyPortfolioOpt.
**Spec:** docs/superpowers/specs/2026-10-29-quant-research-design.md

## Global Constraints
- No trading access or order execution; same-currency analysis only.
- Do not fabricate data, OHLC, fund total returns or missing asset histories.
- Temporal train/holdout split and next-bar strategy execution; visible costs and provenance.
- Keep generated/private data out of public source; retain dark theme and stable controls.

## Review Focus
- NaN/zero/duplicate/date gaps and benchmark alignment must not create false returns.
- Backtest fees, order sizes, warmup and open positions must be faithfully labeled.
- Optimizer may not see holdout data or silently recover from infeasible constraints.
- Changing product/mode/parameters may not show an old result under new labels.
- Dependency versions/licenses and old course environment must be disclosed accurately.

### Task 1: Three engines
- [x] Add failing tests for return alignment, QuantStats metrics, next-bar/lot/cost behavior, train/holdout boundaries and constrained weights.
- [x] Implement stockeasy/research.py, stockeasy/backtests.py, stockeasy/portfolio.py against installed library APIs.
- [x] Run engine tests and inspect real outputs.

### Task 2: Research workspace
- [x] Add failing AppTest flows for three research tabs and explicit-run results/exports.
- [x] Implement stockeasy/research_panel.py and navigation, bounded data preparation and result fingerprinting.
- [x] Full regression and browser QA, including controls not recomputing on quote ticks.

### Task 3: Delivery
- [x] Independent review, important fixes and regression verification.
- [x] README/dependency notices, verification evidence and usable preview.
- [x] Public source sync and remote hash verification.
- [x] Prepare concise usage instructions plus WhaleQuant learning stages with source links.

Verification: 43 full-suite tests passed; pip check/compile/diff checks passed. Independent reviewer approved after the QuantStats extreme-return guard. Browser verified all three explicit-run flows and downloaded HTML; 1920px viewport has no horizontal overflow.

Source release 94782b3cddc5d0118e783d948b804d3c401a5cf4 was pushed to origin/main and matched the remote hash. Browser also verified the recommended 1440px PC breakpoint without horizontal overflow; local screenshot is ignored by Git.
