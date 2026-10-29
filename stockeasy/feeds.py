"""Background quotes for responsive dashboard fragments."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
import time


class QuoteFeed:
    def __init__(self, service, workers=6):
        self.service = service
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="stockeasy-quotes")
        self.tasks, self.quotes, self.errors = {}, {}, {}
        self.collected, self.completed_at = {}, {}
        self.lock = RLock()

    def _collect(self):
        for key, (future, _) in self.tasks.items():
            if future.done() and self.collected.get(key) is not future:
                try:
                    self.quotes[key] = future.result()
                    quote = self.quotes[key]
                    if getattr(quote, "stale", False):
                        self.errors[key] = quote.error or "刷新失败，保留原缓存"
                    else:
                        self.errors.pop(key, None)
                except Exception as exc:
                    self.errors[key] = str(exc)
                self.collected[key] = future
                self.completed_at[key] = time.monotonic()

    def refresh(self, instruments, interval=15, force=False, paused=False):
        with self.lock:
            self._collect()
            active = {item.key for item in instruments}
            for key in set(self.tasks) - active:
                self.tasks[key][0].cancel()
                del self.tasks[key]
                self.quotes.pop(key, None)
                self.errors.pop(key, None)
                self.collected.pop(key, None)
                self.completed_at.pop(key, None)
            for item in instruments:
                prior = self.tasks.get(item.key)
                if prior and paused and not force:
                    continue
                # A future may finish after _collect checked it. Preserve it
                # until the next collection instead of overwriting its result.
                if prior and self.collected.get(item.key) is not prior[0]:
                    continue
                delay = max(interval, 30) if item.key in self.errors else interval
                if prior and (not prior[0].done() or (not force and time.monotonic() - self.completed_at.get(item.key, prior[1]) < delay)):
                    continue
                task = self.pool.submit(self.service.quote, item, force=force, max_age_seconds=interval)
                self.tasks[item.key] = (task, time.monotonic())

    def snapshot(self):
        with self.lock:
            self._collect()
            pending = {key for key, (task, _) in self.tasks.items() if not task.done()}
            return dict(self.quotes), dict(self.errors), pending

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
