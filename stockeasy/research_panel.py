"""Explicit-run research UI; quote fragments never recompute these results."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from hashlib import sha256
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from stockeasy.backtests import STRATEGIES, run_backtest
from stockeasy.demo import demo_history
from stockeasy.discovery import universe
from stockeasy.portfolio import optimize_portfolio
from stockeasy.presentation import pct, time_label
from stockeasy.research import performance_html, performance_report, price_panel, validate_currency


def signature(demo, params):
    return sha256(json.dumps({"demo": demo, **params}, sort_keys=True, default=str).encode()).hexdigest()


def load_data(items, start, end, service, demo):
    if start >= end:
        raise ValueError("开始日期必须早于结束日期")
    validate_currency(items)

    def load(item):
        try:
            adjustment = "raw" if item.market == "FUND" else "qfq"
            result = demo_history(item, start, end) if demo else service.history(item, start, end, adjustment)
            if result.frame.empty:
                raise ValueError("所选区间没有数据")
            return item, result, None
        except Exception as exc:
            return item, None, str(exc)

    frames, metadata, errors = {}, [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for item, result, error in pool.map(load, items):
            if error:
                errors.append(f"{item.name}（{item.symbol}）：{error}")
                continue
            frames[item.key] = result.frame
            metadata.append({"产品": item.name, "代码": item.symbol, "币种": item.currency,
                             "价格口径": "单位净值（不计分红再投）" if item.market == "FUND" else "合成演示" if demo else "前复权 / Yahoo 复权",
                             "起始": result.frame.date.min().strftime("%Y-%m-%d"), "截至": result.frame.date.max().strftime("%Y-%m-%d"),
                             "来源": result.source, "获取时间": time_label(result.fetched_at),
                             "状态": "缓存 / 更新失败" if result.stale else "演示" if demo else "已获取"})
    if errors:
        raise ValueError("所选产品中有数据不可用，未删掉产品继续计算。请更换产品或稍后重试：\n" + "\n".join(errors))
    return frames, metadata


def run_saved(key, fingerprint, builder):
    st.session_state.pop(key, None)
    try:
        with st.spinner("正在准备历史并计算，首次连接可能需要片刻…"):
            payload = builder()
        st.session_state[key] = {"signature": fingerprint, "created": datetime.now().astimezone().isoformat(), **payload}
    except Exception as exc:
        st.error(f"本次研究未完成：{exc}")


def saved_result(key, fingerprint):
    saved = st.session_state.get(key)
    if saved and saved["signature"] != fingerprint:
        st.info("参数已改变，请重新运行；旧结果不会套用到新产品或新参数上。")
        return None
    return saved


def curve_chart(frame):
    fig = go.Figure()
    for column, color in zip(frame.columns, ["#7fa8ff", "#edbf86", "#55d6b2"]):
        fig.add_trace(go.Scatter(x=frame.index, y=frame[column], name=str(column), line={"color": color, "width": 2}))
    fig.update_layout(height=330, margin={"l": 8, "r": 12, "t": 25, "b": 5}, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font={"color": "#a9bad2", "size": 11}, hovermode="x unified",
                      hoverlabel={"bgcolor": "#192941", "font_color": "#e4ecf7"}, legend={"orientation": "h", "y": 1.13})
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#2a3b55", side="right", title="起点 = 100")
    return fig


def source_details(saved):
    metadata = pd.DataFrame(saved["metadata"])
    if metadata["状态"].str.contains("失败").any():
        st.warning("部分历史使用更新失败后的缓存，请按下方实际日期解读；这不是最新实时数据。")
    with st.expander("数据来源与实际覆盖区间"):
        st.dataframe(metadata, hide_index=True, width="stretch")
        st.caption(f"计算于 {time_label(saved['created'])}；结果来自上次点击运行，行情刷新不会自动重算。")


def export_csv(frame, saved, demo, index=False):
    export = frame.reset_index() if index else frame.copy()
    export["research_mode"] = "synthetic_demo" if demo else "real_data"
    export["calculated_at"] = saved["created"]
    export["research_parameters"] = json.dumps(saved["params"], ensure_ascii=False, sort_keys=True, default=str)
    export["data_provenance"] = json.dumps(saved["metadata"], ensure_ascii=False, default=str)
    return export.to_csv(index=False).encode("utf-8-sig")


def metric_rows(values):
    for offset in range(0, len(values), 4):
        for column, (label, value) in zip(st.columns(4), values[offset:offset + 4]):
            column.metric(label, value)


def dates(prefix, today):
    left, right = st.columns(2)
    start = left.date_input("开始日期", today - timedelta(days=365), max_value=today, key=f"{prefix}_start")
    end = right.date_input("结束日期", today, max_value=today, key=f"{prefix}_end")
    return start, end


def risk_panel(items, active_item, service, demo, today):
    by_key = {item.key: item for item in items}
    preferred = active_item.key if active_item and active_item.key in by_key else items[0].key
    key = st.selectbox("体检产品", list(by_key), index=list(by_key).index(preferred), format_func=lambda value: f"{by_key[value].name} · {by_key[value].symbol}", key="risk_asset")
    item = by_key[key]
    references = [other for other in items if other.currency == item.currency and other.market != "FUND" and other.key != key]
    choices = [None] + [other.key for other in references]
    default_ref = next((other.key for other in references if other.symbol in {"510300", "SPY"}), choices[1] if references else None)
    with st.form("risk_form"):
        reference = st.selectbox("参考基准（可更改，并非基金合同基准）", choices, index=choices.index(default_ref), format_func=lambda value: "不设基准" if value is None else f"{by_key[value].name} · {by_key[value].symbol}", key=f"risk_benchmark_{item.currency}")
        start, end = dates("risk", today)
        rf = st.number_input("年化无风险利率（%）", min_value=-5., max_value=20., value=0., step=.25, key="risk_rf") / 100
        submitted = st.form_submit_button("运行收益体检", key="run_risk", width="stretch")
    if item.market == "FUND":
        st.warning("当前场外基金使用单位净值。分红可能使净值跳变，未计分红再投；下面是价格表现研究，不等于实际投资总收益。")
    params = {"asset": key, "benchmark": reference, "start": start, "end": end, "rf": rf}
    fingerprint = signature(demo, params)
    if submitted:
        def build():
            selected = [item] + ([by_key[reference]] if reference else [])
            frames, metadata = load_data(selected, start, end, service, demo)
            return {"result": performance_report(frames, key, reference, rf), "metadata": metadata, "params": params}
        run_saved("risk_result", fingerprint, build)
    saved = saved_result("risk_result", fingerprint)
    if not saved:
        st.caption("QuantStats · 点击运行后按共同有效日期计算，不补造缺失价格；短区间年化值可能不稳定。")
        return
    result = saved["result"]
    metrics = result.metrics
    metric_rows([("区间价格涨跌", pct(metrics["total_return"])), ("年化价格回报", pct(metrics["cagr"])),
                 ("最大回撤", pct(metrics["max_drawdown"])), ("年化波动率", pct(metrics["volatility"])),
                 ("夏普比率", "—" if metrics["sharpe"] is None else f"{metrics['sharpe']:.2f}"),
                 ("Sortino 比率", "—" if metrics["sortino"] is None else f"{metrics['sortino']:.2f}"),
                 ("基准区间涨跌", pct(metrics["benchmark_return"])), ("相对基准差值", pct(metrics["excess_return"]))])
    labels = {value: f"{by_key[value].name} · {by_key[value].symbol}" for value in result.wealth.columns}
    st.plotly_chart(curve_chart(result.wealth.rename(columns=labels)), width="stretch", config={"displayModeBar": False})
    st.caption(f"QuantStats · 共同区间 {result.wealth.index.min():%Y-%m-%d} ～ {result.wealth.index.max():%Y-%m-%d} · {len(result.wealth)} 个价格点 · 按 252 个观测期年化 · 未扣个人交易费用")
    with st.expander("月度价格回报（%）"):
        st.dataframe((result.monthly * 100).round(2), width="stretch")
        st.caption("EOY 为该年当前区间的累计值，首末月/年可能不完整。")
    export_metrics = pd.DataFrame({"metric": list(metrics), "value": list(metrics.values())})
    st.download_button("导出体检指标 CSV", export_csv(export_metrics, saved, demo), file_name=f"{'DEMO_' if demo else ''}{item.market}_{item.symbol}_risk_metrics.csv", mime="text/csv")
    if st.button("生成完整 HTML 报告", key="risk_html"):
        try:
            with st.spinner("正在生成 QuantStats 报告…"):
                content = performance_html(result, title=f"Stockeasy {item.symbol} price research", rf=rf)
                # Preserve the price basis and source warnings in the downloaded artifact.
                appendix = '<h2>Data provenance / price research</h2><p>Price changes only; fund unit NAV does not include dividend reinvestment. Personal trading costs are not deducted. Annualization uses 252 observations.</p>' + pd.DataFrame(saved["metadata"]).to_html(index=False, escape=True) + pd.DataFrame({"parameter": saved["params"].keys(), "value": [str(value) for value in saved["params"].values()]}).to_html(index=False, escape=True)
                saved["html"] = content.replace(b"</body>", appendix.encode("utf-8") + b"</body>")
        except Exception as exc:
            st.error(f"HTML 报告生成失败：{exc}")
    if "html" in saved:
        st.download_button("下载完整 HTML 报告", saved["html"], file_name=f"{'DEMO_' if demo else ''}Stockeasy_{item.symbol}_report.html", mime="text/html")
    source_details(saved)


def backtest_panel(items, active_item, service, demo, today):
    eligible = [item for item in items if item.market != "FUND"]
    by_key = {item.key: item for item in eligible}
    preferred = next((item.key for item in eligible if item.symbol == "510300"), eligible[0].key)
    key = st.selectbox("回测产品（股票 / ETF）", list(by_key), index=list(by_key).index(preferred), format_func=lambda value: f"{by_key[value].name} · {by_key[value].symbol}", key="bt_asset")
    item = by_key[key]
    strategy = st.selectbox("策略规则", STRATEGIES, key="bt_strategy")
    with st.form("backtest_form"):
        start, end = dates("bt", today)
        a, b, c = st.columns(3)
        cash = a.number_input(f"初始资金（{item.currency}）", min_value=1000., max_value=100000000., value=100000., step=10000., key="bt_cash")
        commission = b.number_input("每边手续费（%）", min_value=0., max_value=5., value=.05, step=.01, key="bt_commission") / 100
        spread = c.number_input("买卖价差假设（基点）", min_value=0., max_value=500., value=5., step=1., key="bt_spread") / 10000
        a, b, c, d = st.columns(4)
        fast = int(a.number_input("短均线周期", min_value=2, max_value=249, value=10, disabled=strategy != "均线交叉", key="bt_fast"))
        slow = int(b.number_input("长均线周期", min_value=3, max_value=250, value=30, disabled=strategy != "均线交叉", key="bt_slow"))
        lot = int(c.number_input("每手数量", min_value=1, max_value=10000, value=100 if item.market in {"CN", "ETF"} else 1, key=f"bt_lot_{item.market}"))
        allocation = d.number_input("资金使用比例（%）", min_value=5., max_value=95., value=90., step=5., key="bt_allocation") / 100
        submitted = st.form_submit_button("运行策略回测", key="run_backtest", width="stretch")
    st.caption("研究假设：只做多、下一根日线开盘成交、按每手数量下单；价差近似交易摩擦。每手数量需核对具体产品。未完整模拟停牌、涨跌停排队、税费和逐笔滑点。")
    with st.expander("三种规则和退出方式"):
        st.markdown("**均线交叉：** 短均线上穿长均线买入，下穿退出。**趋势延续：** 20 日涨幅 >2%、价格高于上行的 20 日均线时买入，跌破均线退出。**回撤修复：** 距 60 日高点仍跌 ≥5%、5 日回升 ≥1.5% 时买入，5 日回报 ≤−2% 或距高点不足 1% 时退出。所有信号只使用当日及以前数据。")
    params = {"asset": key, "start": start, "end": end, "strategy": strategy, "fast": fast, "slow": slow,
              "cash": cash, "commission": commission, "spread": spread, "lot_size": lot, "allocation": allocation}
    fingerprint = signature(demo, params)
    if submitted:
        def build():
            frames, metadata = load_data([item], start, end, service, demo)
            result = run_backtest(frames[key], **{name: value for name, value in params.items() if name not in {"asset", "start", "end"}})
            return {"result": result, "metadata": metadata, "params": params}
        run_saved("bt_result", fingerprint, build)
    saved = saved_result("bt_result", fingerprint)
    if not saved:
        st.caption("Backtesting.py · 选择规则后运行；场外基金没有完整 OHLC，不进入交易回测。")
        return
    result = saved["result"]
    metrics = result.metrics
    metric_rows([("策略区间回报（含设定费用）", pct(metrics["total_return"])), ("最大回撤", pct(metrics["max_drawdown"])),
                 ("已平仓交易", str(metrics["closed_trades"])), ("期末未平仓", str(result.open_trades))])
    st.plotly_chart(curve_chart(result.equity), width="stretch", config={"displayModeBar": False})
    st.caption(f"Backtesting.py · {strategy} · {item.symbol} / {item.currency} · 费用每边 {commission:.3%} · 价差 {spread * 10000:.1f} 基点 · {lot} 单位/手 · 不强制平掉末日持仓，期末按市值计入净值")
    st.caption("策略前若干日用于指标预热，可能保持现金；买入持有对照从区间起点开始且不扣费用。复权价格用于研究，不是历史真实成交复现。")
    if result.dropped_rows:
        st.warning(f"剔除了 {result.dropped_rows} 条不完整/无效 OHLC 或重复日期，请留意实际区间。")
    if result.trades.empty:
        st.info("没有已平仓交易：可能规则未触发、资金不足一手，或仍持仓。请结合期末未平仓数和净值查看。")
    else:
        st.dataframe(result.trades, hide_index=True, width="stretch")
    export = result.trades.copy()
    export["asset"] = key
    export["currency"] = item.currency
    export["strategy"] = strategy
    export["source"] = saved["metadata"][0]["来源"]
    st.download_button("导出交易记录 CSV", export_csv(export, saved, demo), file_name=f"{'DEMO_' if demo else ''}{item.symbol}_trades.csv", mime="text/csv")
    st.download_button("导出回测净值 CSV", export_csv(result.equity, saved, demo, index=True), file_name=f"{'DEMO_' if demo else ''}{item.symbol}_equity.csv", mime="text/csv")
    source_details(saved)


def portfolio_panel(items, watchlist, service, demo, today):
    eligible = [item for item in items if item.market != "FUND"]
    currency = st.selectbox("组合计价币种", sorted({item.currency for item in eligible}), key="portfolio_currency")
    by_key = {item.key: item for item in eligible if item.currency == currency}
    defaults = [item.key for item in watchlist if item.key in by_key][:4]
    if len(defaults) < 2:
        defaults = list(by_key)[:2]
    with st.form("portfolio_form"):
        selected = st.multiselect("组合产品（2～8 个，同币种）", list(by_key), default=defaults, format_func=lambda value: f"{by_key[value].name} · {by_key[value].symbol}", max_selections=8, key=f"portfolio_assets_{currency}")
        start, end = dates("portfolio", today)
        method = st.selectbox("配置目标", ["最小波动", "最大夏普"], key="portfolio_method")
        a, b, c = st.columns(3)
        cap = a.number_input("单项权重上限（%）", min_value=5., max_value=100., value=80., step=5., key="portfolio_cap") / 100
        rf = b.number_input("年化无风险利率（%）", min_value=-5., max_value=20., value=0., step=.25, key="portfolio_rf") / 100
        budget = c.number_input(f"理论配置金额（{currency}）", min_value=1000., max_value=100000000., value=100000., step=10000., key="portfolio_budget")
        submitted = st.form_submit_button("运行组合分析", key="run_portfolio", width="stretch")
    st.caption("前 80% 共同日期拟合，后 20% 留出观察；不做汇率拼接。股票/ETF 使用复权价格，场外基金需补齐分红再投净值后再纳入配置。理论金额不等于可成交订单。")
    params = {"assets": selected, "currency": currency, "start": start, "end": end, "method": method, "cap": cap, "rf": rf, "budget": budget}
    fingerprint = signature(demo, params)
    if submitted:
        def build():
            if not 2 <= len(selected) <= 8:
                raise ValueError("请选择 2～8 个同币种股票/ETF；可先从右侧添加产品")
            if len(selected) * cap < 1 - 1e-9:
                raise ValueError("产品数 × 单项权重上限不足 100%，请提高上限或增加产品")
            frames, metadata = load_data([by_key[value] for value in selected], start, end, service, demo)
            prices = price_panel(frames, minimum=100)
            return {"result": optimize_portfolio(prices, method=method, max_weight=cap, rf=rf), "metadata": metadata, "params": params}
        run_saved("portfolio_result", fingerprint, build)
    saved = saved_result("portfolio_result", fingerprint)
    if not saved:
        st.caption("PyPortfolioOpt · 选择产品后运行；缺数据会明确报错，不会自动删掉资产继续优化。")
        return
    result = saved["result"]
    estimate = result.estimated
    metric_rows([("训练期估计年化回报", pct(estimate["return"])), ("训练期估计年化波动", pct(estimate["volatility"])),
                 ("模型估计夏普", "—" if estimate["sharpe"] is None else f"{estimate['sharpe']:.2f}"),
                 ("留出区间价格涨跌", pct(result.curves.iloc[-1, 0] / result.curves.iloc[0, 0] - 1))])
    weights = pd.DataFrame({"代码": result.weights.index, "名称": [by_key[value].name for value in result.weights.index],
                            "权重 %": result.weights.values * 100, f"理论金额 {currency}": result.weights.values * budget})
    st.dataframe(weights.round(3), hide_index=True, width="stretch")
    st.plotly_chart(curve_chart(result.curves), width="stretch", config={"displayModeBar": False})
    st.caption(f"PyPortfolioOpt · {method} · 训练截至 {result.train_end}，留出从 {result.test_start} 开始 · 共 {result.observations} 个共同价格点 · 净值起点为留出前一观测日收盘")
    st.caption("训练期估计不是未来收益预测。留出期间按初始固定份额持有，不每日再平衡，未扣交易费用；等权仅是参考。历史检验也不保证未来有效。")
    with st.expander("训练期收益相关性"):
        st.dataframe(result.correlation.rename(index=lambda key: by_key[key].name, columns=lambda key: by_key[key].name).round(3), width="stretch")
    export = weights.copy()
    export["currency"] = currency
    export["train_end"] = result.train_end
    export["holdout_start"] = result.test_start
    export["method"] = method
    st.download_button("导出配置权重 CSV", export_csv(export, saved, demo), file_name=f"{'DEMO_' if demo else ''}Stockeasy_{currency}_weights.csv", mime="text/csv")
    source_details(saved)


def render_research(watchlist, active_item, service, demo, today):
    st.markdown("## 量化研究")
    st.caption("选择产品和参数后点击运行。价格研究、规则回测与组合估计均不连接交易账户。")
    items = universe(watchlist)
    report, backtest, portfolio = st.tabs(["收益体检", "策略回测", "组合配置"])
    with report:
        risk_panel(items, active_item, service, demo, today)
    with backtest:
        backtest_panel(items, active_item, service, demo, today)
    with portfolio:
        portfolio_panel(items, watchlist, service, demo, today)
    with st.expander("配合 WhaleQuant 练习"):
        st.markdown("建议按基础概念 → 数据整理 → 可解释规则 → 回测验证 → 组合与调仓 → 机器学习的顺序。每阶段只改一个假设，保留参数、数据日期和结果记录。[在线课程](https://datawhalechina.github.io/whale-quant/)")
        st.markdown("1. 第 1～2 章：用收益体检解释收益、回撤、波动与基准。\n2. 第 3 章：导出日线，检查复权与缺失，独立算出 20 日均线。\n3. 第 4 章：固定观察池，逐条解释今日观察信号。\n4. 第 5、7 章：回测均线规则，手工核对 3 笔次日成交及费用，再用未调参区间检验。\n5. 第 6 章：比较同币种 ETF 的配置与等权；本工具留出期间采用固定份额，尚未实现定期调仓。\n6. 第 8 章：理解基线后再学机器学习，按时间分训练/验证/测试；本工具暂未集成 ML 训练。")
        st.caption("课程 README 仍标注 Alpha 与 Python 3.9 依赖；课程示例请用独立环境复现，不要把旧 requirements 安装到当前工具环境。")
