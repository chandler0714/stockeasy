# Stockeasy delivery record

- User approved the recommended dashboard and asked for direct implementation and public source sync.
- Design and implementation plan recorded; using inline execution, core behavior tests before implementation.
- Initial core test run: expected failure, package not yet implemented.
- Network: inherited local proxy unavailable; retry dependency install without those proxy settings.
- Worktree: directory and repository empty; creating the initial branch locally, no existing work to isolate or overwrite.
- Task 1 complete: core tests passed; ETF quote switched to the same Eastmoney single-security source with explicit exchange after confirmed full-market timeout.
- Task 2 complete: Streamlit interaction tests passed, demo rendered in browser, K-line toggle checked. Demo uses synthetic prices, clearly labeled and isolated from live cache.
- Independent final reviewer found incomplete adjusted reload could delete old history; qfq/hfq regression failed first, then fixed and full suite passed (18 tests).
- Live probes: domestic stock/ETF daily data, domestic stock/ETF quotes, fund daily NAV successful. Yahoo query1/query2 returned 429; HK/US live availability is not claimed.
- Delivery: README, local macOS launcher and GitHub Actions test template included. Public sync is explicitly authorized by the user.
- Publishing credentials lack workflow scope; source will include docs/ci-tests.yml as a template rather than modifying access permissions. Local tests remain available.
- Source successfully pushed to public main and app.py read back with the GitHub connector. Local preview is running at 127.0.0.1:8501; demo tab preserved for user inspection.
- Follow-up: user requested automatic live viewing. Default now 15-second fragment refresh, with 5/30/60/120/300-second options and pause; quote cache lifetime follows the chosen interval. History analysis stays outside the auto-refresh fragment. Added regression tests for the default/pause controls and cache interval.
