"""Background quotes for responsive dashboard fragments."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
import time


class QuoteFeed:
    def __init__(self, service, workers=6):
        self.service = service
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="stockeasy-quotes")
        self.tasks, self.quotes, self.errors = {}, {}, {}
        self.lock = RLock()

    def _collect(self):
        for key, (future, _) in self.tasks.items():
            if future.done():
                try:
                    self.quotes[key] = future.result()
                    self.errors.pop(key, None)
                except Exception as exc:
                    self.errors[key] = str(exc)

    def refresh(self, instruments, interval=15, force=False, paused=False):
        with self.lock:
            self._collect()
            active = {item.key for item in instruments}
            for key in set(self.tasks) - active:
                self.tasks[key][0].cancel()
                del self.tasks[key]
                self.quotes.pop(key, None)
                self.errors.pop(key, None)
            for item in instruments:
                prior = self.tasks.get(item.key)
                if prior and paused and not force:
                    continue
                if prior and (not prior[0].done() or (not force and time.monotonic() - prior[1] < interval)):
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
