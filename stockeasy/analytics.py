import numpy as np
import pandas as pd


def summarize(frame: pd.DataFrame) -> dict:
    close = pd.to_numeric(frame.get("close", pd.Series(dtype=float)), errors="coerce")
    close = close[np.isfinite(close) & (close > 0)]
    result = {"return": None, "max_drawdown": None, "volatility": None, "observations": len(close)}
    if len(close) < 2:
        return result
    returns = close.pct_change().dropna()
    result.update({
        "return": float(close.iloc[-1] / close.iloc[0] - 1),
        "max_drawdown": float((close / close.cummax() - 1).min()),
        "volatility": float(returns.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 else None,
    })
    return result
