from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import math

import pandas as pd

from stockeasy.models import DataResult, QuoteResult
from stockeasy.providers import Providers, normalize_history, source_name


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def age_seconds(timestamp):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).total_seconds()


class MarketService:
    def __init__(self, store, provider=None):
        self.store = store
        self.provider = provider or Providers()

    def history(self, instrument, start, end, adjust="raw", force=False):
        if start > end:
            raise ValueError("开始日期不能晚于结束日期")
        if adjust not in {"raw", "qfq", "hfq"}:
            raise ValueError("不支持的复权方式")
        cached = self.store.load_history(instrument.key, adjust)
        covered = cached and cached.range_start <= start.isoformat() and cached.range_end >= end.isoformat()
        if covered and not force and age_seconds(cached.fetched_at) < 3600:
            return self._slice(cached, start, end)
        fetch_start, fetch_end = start, end
        if cached:
            old_start, old_end = date.fromisoformat(cached.range_start), date.fromisoformat(cached.range_end)
            fetch_start = min(start, old_start) if adjust != "raw" else start if start < old_start else min(end, old_end - timedelta(days=7))
            fetch_end = max(end, old_end)
        try:
            frame = normalize_history(self.provider.history(instrument, fetch_start, fetch_end, adjust))
            # Do not accept a source returning a wholly different requested period.
            frame = frame.loc[frame.date.between(pd.Timestamp(fetch_start), pd.Timestamp(fetch_end))]
            if frame.empty:
                raise ValueError("所选日期区间没有交易或净值数据")
            if cached and adjust != "raw":
                missing = set(cached.frame.date) - set(frame.date)
                if missing:
                    raise ValueError("上游返回的复权历史不完整，已保留原缓存，请稍后重试")
            if cached and adjust == "raw":
                frame = normalize_history(pd.concat([cached.frame, frame], ignore_index=True))
            result = DataResult(frame, source_name(instrument), utc_now(), range_start=min(start.isoformat(), cached.range_start) if cached else start.isoformat(),
                                range_end=max(end.isoformat(), cached.range_end) if cached else end.isoformat())
            self.store.save_history(instrument.key, adjust, result)
            return self._slice(result, start, end)
        except Exception as exc:
            if cached:
                fallback = self._slice(replace(cached, stale=True, error=str(exc)), start, end)
                if not fallback.frame.empty:
                    return fallback
            raise

    @staticmethod
    def _slice(result, start, end):
        return replace(result, frame=result.frame.loc[result.frame.date.between(pd.Timestamp(start), pd.Timestamp(end))].reset_index(drop=True))

    def quote(self, instrument, force=False, max_age_seconds=60):
        cached = self.store.load_quote(instrument.key)
        if cached and not force and age_seconds(cached.fetched_at) < max_age_seconds:
            return cached
        try:
            values = self.provider.quote(instrument)
            if not math.isfinite(float(values["price"])) or float(values["price"]) <= 0:
                raise ValueError("行情价格无效")
            previous = values.get("previous_close")
            if previous is not None and (not math.isfinite(float(previous)) or float(previous) <= 0):
                values["previous_close"] = None
            quote = QuoteResult(**values, source=source_name(instrument), fetched_at=utc_now())
            self.store.save_quote(instrument.key, quote)
            return quote
        except Exception as exc:
            if cached:
                return replace(cached, stale=True, error=str(exc))
            raise
