"""Bounded subprocess entry point for public data providers."""
from datetime import date
import json
import sys

from stockeasy.models import Instrument
from stockeasy.providers import QuoteUnavailable, fetch_history, fetch_quote, safe_provider_error


def main():
    request = json.load(sys.stdin)
    instrument = Instrument(**request["instrument"])
    try:
        if request["operation"] == "history":
            frame = fetch_history(instrument, date.fromisoformat(request["start"]), date.fromisoformat(request["end"]), request["adjust"])
            result = {"frame": frame.to_json(orient="table", date_format="iso", index=False)}
        else:
            result = fetch_quote(instrument)
    except Exception as exc:
        # Do not echo server response bodies, proxy credentials or request URLs to the UI.
        result = {"error": str(exc) if isinstance(exc, QuoteUnavailable) else f"上游数据暂不可用：{safe_provider_error(exc)}；可稍后重试"}
    print("STOCKEASY_RESULT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
