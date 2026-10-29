# PC Dashboard Implementation Plan

> **For agentic workers:** Use inline execution and one final independent review.

**Goal:** Desktop market workspace with explainable daily ideas and a right-side watchlist/discovery rail.
**Architecture:** Separate rule engine and bounded background historical scanner from Streamlit presentation. Keep current providers/cache and daily history/export behavior.
**Tech Stack:** Existing Python, Streamlit, Plotly, pandas.
**Spec:** docs/superpowers/specs/2026-10-29-pc-dashboard-design.md

## Global Constraints
- Local-only; source sync to existing public stockeasy repository.
- No invented market signals; exclude failed/stale/old/short series from recommendations.
- Demo and real storage isolated; source/as-of/currency labels visible.
- Quote refresh remains 15 seconds by default; historical scanning must not block the page.

## Review Focus
- Split/dividend adjustment and missing volume must not yield misleading momentum/volume signals.
- Candidate products and selected products stay disjoint; removal/empty lists stay recoverable.
- Slow or failed upstream requests do not stall full page renders or repeatedly spawn work.
- No whole-market breadth claims from a limited observation pool.
- Selected analysis symbol must remain valid when entered through recommendation or discovery actions.

### Task 1: Discovery and scanner
- [x] Write failing rules/date/short/volume/pool tests and verify failure.
- [x] Implement stockeasy/discovery.py with candidate catalog, assess(frame), build_report(results,today), risks and bounded scanner.
- [x] Verify core tests and background scanner behavior with fixed local providers.

### Task 2: PC layout and interactions
- [x] Add failing AppTest cases for daily recommendations, right-rail discovery and one-click add/analysis.
- [x] Extract reusable history panel, add UI styles/cards, redesign app around central ideas and right rail; preserve data mode, auto-refresh and exports.
- [x] Run all tests and actual wide browser checks; repair observed issues.

### Task 3: Delivery
- [x] Independent review and regression fixes, documentation and screenshot.
- [ ] Full suite and source-file checks; sync to public main; leave current preview accessible.
