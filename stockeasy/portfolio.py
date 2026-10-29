"""Train-only PyPortfolioOpt weights and chronological holdout observation."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, expected_returns, risk_models

from stockeasy.research import finite


@dataclass
class PortfolioResult:
    weights: pd.Series
    estimated: dict
    curves: pd.DataFrame
    correlation: pd.DataFrame
    train_end: str
    test_start: str
    observations: int


def optimize_portfolio(prices, method="最小波动", max_weight=.8, rf=0):
    if not 2 <= prices.shape[1] <= 8 or len(set(prices.columns)) != prices.shape[1]:
        raise ValueError("请选择 2～8 个不同产品")
    if len(prices) < 100 or not isinstance(prices.index, pd.DatetimeIndex) or prices.index.has_duplicates:
        raise ValueError("组合分析至少需要 100 个共同有效价格点，日期不能重复")
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError("价格包含缺失、无穷或非正值；不能填补后冒充真实数据")
    if not np.isfinite(max_weight) or not 0 < max_weight <= 1 or prices.shape[1] * max_weight < 1 - 1e-9:
        raise ValueError("权重上限不可行：产品数 × 单项上限必须至少为 100%")
    if method not in {"最小波动", "最大夏普"} or not np.isfinite(rf) or not -1 < rf < 1:
        raise ValueError("优化方法或年化无风险利率无效")
    prices = prices.sort_index().astype(float)
    cut = int(len(prices) * .8)
    train, holdout = prices.iloc[:cut], prices.iloc[cut - 1:]
    mu = expected_returns.mean_historical_return(train, frequency=252)
    cov = risk_models.CovarianceShrinkage(train, frequency=252).ledoit_wolf()
    optimizer = EfficientFrontier(mu, cov, weight_bounds=(0, max_weight))
    if method == "最小波动":
        optimizer.min_volatility()
    else:
        if float(mu.max()) <= rf:
            raise ValueError("训练期没有产品的估计年化收益高于无风险利率，无法求最大夏普；请更换方法或区间")
        optimizer.max_sharpe(risk_free_rate=rf)
    weights = pd.Series(np.maximum(optimizer.weights, 0), index=prices.columns)
    weights /= weights.sum()
    if weights.max() > max_weight + 1e-6:
        raise ValueError("求解结果超出权重上限，请调整参数")
    annual_return = float(mu @ weights)
    annual_vol = float(np.sqrt(weights @ cov @ weights))
    estimated = {"return": finite(annual_return), "volatility": finite(annual_vol),
                 "sharpe": finite((annual_return - rf) / annual_vol) if annual_vol > 0 else None}
    # Fixed initial shares: no implicit daily rebalancing or holdout fitting.
    relative = holdout / holdout.iloc[0]
    curves = pd.DataFrame({"配置组合": relative @ weights * 100, "等权对照": relative.mean(axis=1) * 100})
    return PortfolioResult(weights, estimated, curves, train.pct_change(fill_method=None).dropna().corr(),
                           train.index[-1].strftime("%Y-%m-%d"), prices.index[cut].strftime("%Y-%m-%d"), len(prices))
