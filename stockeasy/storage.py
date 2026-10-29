from contextlib import closing
from dataclasses import asdict
import io
import json
from pathlib import Path
import sqlite3

import pandas as pd

from stockeasy.models import DataResult, DEFAULT_WATCHLIST, Instrument, QuoteResult


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def _get(self, key):
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload FROM cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self, key, value):
        with closing(self._connect()) as conn, conn:
            conn.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False, allow_nan=False)))

    def watchlist(self):
        values = self._get("watchlist")
        return [Instrument(**value) for value in values] if values is not None else list(DEFAULT_WATCHLIST)

    def save_watchlist(self, instruments):
        self._put("watchlist", [asdict(item) for item in instruments])

    def load_history(self, key, adjust):
        payload = self._get(f"history:{key}:{adjust}")
        if payload is None:
            return None
        frame = pd.read_json(io.StringIO(payload.pop("frame")), orient="table")
        return DataResult(frame=frame, **payload)

    def save_history(self, key, adjust, result):
        self._put(f"history:{key}:{adjust}", {
            "frame": result.frame.to_json(orient="table", date_format="iso", index=False),
            "source": result.source, "fetched_at": result.fetched_at,
            "range_start": result.range_start, "range_end": result.range_end,
        })

    def load_quote(self, key):
        payload = self._get(f"quote:{key}")
        return QuoteResult(**payload) if payload else None

    def save_quote(self, key, quote):
        self._put(f"quote:{key}", asdict(quote))
