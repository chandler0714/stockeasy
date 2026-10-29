"""Research calculations on supplied local histories; never download implicitly."""
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

# Keep report rendering headless and its font cache inside the ignored data folder.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / "data" / "matplotlib"))
import matplotlib
matplotlib.use("Agg")
import quantstats as qs

from stockeasy.providers import normalize_history


def finite(value):
    return float(value) if value is not None and np.isfinite(value) else None


def validate_currency(instruments):
    if not instruments:
        raise ValueError("请先选择产品")
    currencies = {item.currency for item in instruments}
    if len(currencies) != 1:
        raise ValueError("请选相同币种的产品；当前未做汇率换算，不能直接拼接跨币种价格")
    return next(iter(currencies))


def price_panel(histories, minimum=30):
    if not histories:
        raise ValueError("没有可用历史")
    series = []
    for key, raw in histories.items():
        frame = normalize_history(raw)
        series.append(frame.set_index("date").close.rename(key))
    prices = pd.concat(series, axis=1, join="inner").sort_index().dropna()
    if len(prices) < minimum:
        raise ValueError(f"至少需要 {minimum} 个共同有效价格点，当前只有 {len(prices)} 个；请扩大日期区间或更换产品")
    return prices


@dataclass
class PerformanceResult:
    metrics: dict
    returns: pd.Series
    benchmark_returns: pd.Series | None
    wealth: pd.DataFrame
    monthly: pd.DataFrame


def validate_report_returns(*series):
    for values in series:
        if values is None:
            continue
        if not np.isfinite(values.to_numpy()).all():
            raise ValueError("收益率出现非有限值，请核对价格和观测区间")
        # QuantStats infers prices vs returns in multiple internal paths,
        # including slices inside HTML charts. Fail explicitly instead of
        # letting a legitimate large return be percentage-changed again.
        if (values >= 1).any():
            raise ValueError("存在单个观测区间涨幅 ≥100%；当前 QuantStats 引擎可能混淆价格与收益率，已停止生成报告。请核对复权、日期缺口与价格，或改用其他区间；这不表示原始价格必然错误。")


def performance_report(histories, asset, benchmark=None, rf=0):
    if asset not in histories or (benchmark and benchmark not in histories):
        raise ValueError("缺少分析产品或基准的历史数据")
    if not np.isfinite(rf) or not -1 < rf < 1:
        raise ValueError("无风险利率必须为有效年化比例")
    selected = {asset: histories[asset]}
    if benchmark:
        selected[benchmark] = histories[benchmark]
    prices = price_panel(selected)
    returns = prices[asset].pct_change(fill_method=None).dropna().rename("Asset")
    reference = prices[benchmark].pct_change(fill_method=None).dropna().rename("Benchmark") if benchmark else None
    validate_report_returns(returns, reference)
    with np.errstate(divide="ignore", invalid="ignore"):
        metrics = {
            "total_return": finite(qs.stats.comp(returns)),
            "cagr": finite(qs.stats.cagr(returns, periods=252)),
            "volatility": finite(qs.stats.volatility(returns, periods=252)),
            "max_drawdown": finite(qs.stats.max_drawdown(returns)),
            "sharpe": finite(qs.stats.sharpe(returns, rf=rf, periods=252)),
            "sortino": finite(qs.stats.sortino(returns, rf=rf, periods=252)),
            "benchmark_return": finite(qs.stats.comp(reference)) if reference is not None else None,
        }
    metrics["excess_return"] = metrics["total_return"] - metrics["benchmark_return"] if reference is not None else None
    wealth = (prices / prices.iloc[0]) * 100
    monthly = qs.stats.monthly_returns(returns, eoy=True)
    return PerformanceResult(metrics, returns, reference, wealth, monthly)


def performance_html(result, title="Stockeasy performance report", rf=0):
    validate_report_returns(result.returns, result.benchmark_returns)
    with tempfile.TemporaryDirectory(prefix="stockeasy-report-") as folder:
        output = Path(folder) / "report.html"
        qs.reports.html(result.returns, benchmark=result.benchmark_returns, rf=rf, periods_per_year=252,
                        title=title, output=str(output), download_filename="stockeasy-report.html")
        return output.read_bytes()
