from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from html import escape
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from stockeasy.analytics import summarize
from stockeasy.charts import performance_chart, price_chart
from stockeasy.demo import demo_history, demo_quote
from stockeasy.models import Instrument, MARKETS
from stockeasy.service import MarketService
from stockeasy.storage import Store

st.set_page_config(page_title="Stockeasy · 看见市场，读懂趋势", page_icon="↗", layout="wide")

st.markdown("""<style>
html, body, [class*="css"], .stApp {font-family:'DM Sans',-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;}
.block-container {padding-top:2.1rem;padding-bottom:2rem;max-width:1540px;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {background:#101e36;min-width:270px;max-width:270px;}
[data-testid="stSidebar"] * {color:#d5ddeb;}
[data-testid="stSidebar"] h3 {font-size:13px;letter-spacing:.07em;color:#8395b3;}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] input {background:#1b2c48;color:#eff3ff;}
[data-testid="stSidebar"] [data-testid="stForm"] {border-color:#2b3d59;}
[data-testid="stSidebar"] button {background:#1c3051;border-color:#304766;}
[data-testid="stSidebar"] button[kind="primaryFormSubmit"] {background:#3564eb;border-color:#3564eb;}
[data-testid="stSidebar"] hr {border-color:#2b3d59;}
[data-testid="stMetric"] {background:#fff;border:1px solid #e7ecf4;border-radius:12px;padding:18px 20px;}
[data-testid="stMetricLabel"] {color:#768399;font-size:12px;}
[data-testid="stMetricValue"] {font-size:27px;font-weight:600;letter-spacing:-.04em;}
div[data-testid="stVerticalBlockBorderWrapper"] > div {border-radius:12px;border-color:#e7ecf4!important;}
h1 {font-size:29px!important;font-weight:650!important;letter-spacing:-.045em;padding-top:4px!important;}
h2 {font-size:19px!important;letter-spacing:-.02em;}
h3 {font-size:16px!important;}
[data-testid="stTabs"] button {font-size:14px;padding:12px 18px;}
[data-testid="stDataFrame"] {border-radius:9px;overflow:hidden;}
.eyebrow {font-size:10px;letter-spacing:2.4px;color:#8d9ab0;font-weight:700;}
.brand {font-size:27px;letter-spacing:-1px;color:white!important;font-weight:700;margin:4px 0 3px;}
.brand span {color:#7da0ff!important;}
.brand-sub {font-size:10px;color:#8497b5!important;letter-spacing:2.5px;margin-bottom:32px;}
.source-label {font-size:11px;color:#8390a5;line-height:1.8;}
.pill {display:inline-block;background:#eaf0ff;color:#3564eb;border-radius:6px;padding:5px 10px;font-size:11px;}
.hero-note {color:#8390a5;font-size:13px;}
.footer {font-size:11px;color:#95a0b2;border-top:1px solid #e3e9f2;margin-top:20px;padding-top:16px;}
[data-testid="stAlert"] {border-radius:9px;}
</style>""", unsafe_allow_html=True)

DATA_DIR = Path(os.environ.get("STOCKEASY_DATA_DIR", Path(__file__).parent / "data"))
TODAY = datetime.now(ZoneInfo("Asia/Shanghai")).date()
demo_default = os.environ.get("STOCKEASY_DEMO") == "1" or st.query_params.get("demo") == "1"


def timestamp_label(value):
    if not value:
        return "数据源未提供成交时间"
    try:
        parsed = datetime.fromisoformat(value)
        if len(value) == 10:
            return value
        return parsed.strftime("%m-%d %H:%M %Z") + (f" UTC{parsed.strftime('%z')}" if parsed.tzinfo else "")
    except ValueError:
        return value


def percent(value):
    return "—" if value is None else f"{value:+.2%}"


with st.sidebar:
    st.markdown('<div class="brand">↗ stock<span>easy</span></div><div class="brand-sub">A LITTLE CLARITY. EVERY DAY.</div>', unsafe_allow_html=True)
    st.markdown("### 工作空间")
    st.markdown("**◉　市场观察**")
    st.caption("自选行情 · 历史分析 · 数据导出")
    st.divider()
    demo = st.toggle("演示模式", value=demo_default, key="demo_mode", help="使用合成数据预览界面，不代表真实行情。")
    st.caption("合成数据，仅用于预览" if demo else "AKShare + yfinance · 真实数据")

    # Separate files keep both data and watchlist state isolated across modes.
    store = Store(DATA_DIR / ("demo.sqlite" if demo else "market.sqlite"))
    watchlist = store.watchlist()

    st.markdown("### 自选管理")
    with st.form("add_form", clear_on_submit=False):
        st.selectbox("市场", list(MARKETS), format_func=lambda key: MARKETS[key], key="new_market")
        st.text_input("证券代码", placeholder="600519 / 00700 / AAPL", key="new_symbol", max_chars=20)
        st.text_input("显示名称（可选）", placeholder="给自选一个名字", key="new_name", max_chars=40)
        submitted = st.form_submit_button("＋ 添加自选", width="stretch", key="add_watch")
    if submitted:
        try:
            item = Instrument.create(st.session_state.new_market, st.session_state.new_symbol, st.session_state.new_name)
            if item.key in {instrument.key for instrument in watchlist}:
                st.info("该标的已在自选列表中")
            elif len(watchlist) >= 20:
                st.error("首版最多支持 20 个自选，请先移除不需要的标的")
            else:
                store.save_watchlist(watchlist + [item])
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if watchlist:
        with st.expander("管理已有自选"):
            st.selectbox("移除标的", [item.key for item in watchlist], key="remove_key")
            if st.button("移除自选", key="remove_watch", width="stretch"):
                store.save_watchlist([item for item in watchlist if item.key != st.session_state.remove_key])
                st.session_state.pop("selected_key", None)
                st.rerun()
    st.divider()
    refresh_label = st.selectbox("行情自动刷新", ["暂停（手动刷新）", "每 5 秒", "每 15 秒", "每 30 秒", "每 60 秒", "每 120 秒", "每 300 秒"], index=2, key="refresh_interval_v2")
    st.caption("默认自动刷新行情；上游响应慢时会顺延。数据可能延迟，基金净值按日公布。")
    st.markdown('<div class="source-label">数据保存在本机<br>无需密钥 · 不连接交易账户</div>', unsafe_allow_html=True)

head, badge = st.columns([5, 1.6], vertical_alignment="center")
with head:
    st.markdown('<div class="eyebrow">MARKET WORKSPACE / 市场观察</div>', unsafe_allow_html=True)
    st.title("自选行情与历史分析")
    st.markdown('<div class="hero-note">从当下价格，到长期趋势。把关注的市场放在一起。</div>', unsafe_allow_html=True)
with badge:
    st.markdown(f'<span class="pill">{TODAY:%Y.%m.%d}　·　{len(watchlist):02d} 个自选</span>', unsafe_allow_html=True)
if demo:
    st.warning("演示模式 · 当前价格与图表均为合成数据，仅供体验界面。关闭左侧「演示模式」后接入真实数据。")
else:
    st.caption("免费数据可能延迟或暂不可用；A 股为上游报价快照，港美股为最近一分钟数据，基金为已公布净值。")

if not watchlist:
    st.info("自选列表为空，请从左侧添加股票、ETF 或基金。")
    st.stop()

service = MarketService(store)
interval = None if refresh_label == "暂停（手动刷新）" else int(refresh_label.split()[1])


@st.fragment(run_every=interval)
def quote_panel():
    left, right = st.columns([6, 1])
    with left:
        st.markdown("### 自选快照")
    with right:
        force = st.button("↻ 刷新行情", key="refresh_quotes", width="stretch")
    quotes, errors = {}, {}

    def load(item):
        try:
            return item.key, demo_quote(item, TODAY) if demo else service.quote(item, force=force, max_age_seconds=interval or 60), None
        except Exception as exc:
            return item.key, None, str(exc)

    with st.spinner("正在获取行情，首次连接可能需要片刻…"):
        with ThreadPoolExecutor(max_workers=6) as pool:
            for key, quote, error in pool.map(load, watchlist):
                if quote is not None:
                    quotes[key] = quote
                else:
                    errors[key] = error
    checked_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
    refresh_status = f"自动刷新中 · 每 {interval} 秒" if interval else "自动刷新已暂停 · 可点击刷新行情"
    st.caption(f"{refresh_status}　·　最近检查 {checked_at}（北京时间）")
    cards = st.columns(min(4, len(watchlist)))
    for column, item in zip(cards, watchlist[:4]):
        quote = quotes.get(item.key)
        with column:
            st.metric(f"{item.name} · {item.symbol}", f"{quote.price:,.3f}" if quote else "—",
                      percent(quote.change_pct) if quote and quote.change_pct is not None else None, delta_color="inverse")
            st.caption(f"{item.currency} · " + ("缓存 · 刷新失败" if quote and quote.stale else "合成演示" if demo else "已公布净值" if item.market == "FUND" else "行情快照" if quote else "连接暂不可用"))
    filter_market = st.segmented_control("按市场筛选", ["全部"] + list(dict.fromkeys(MARKETS[item.market] for item in watchlist)),
                                         default="全部", key="market_filter", label_visibility="collapsed")
    rows = []
    for item in watchlist:
        if filter_market not in (None, "全部", MARKETS[item.market]):
            continue
        quote = quotes.get(item.key)
        kind = {"nav": "已公布净值", "minute": "分钟行情 · 可能延迟", "quote": "报价快照", "demo": "合成演示"}
        rows.append({"名称": item.name, "代码": item.symbol, "市场": MARKETS[item.market], "币种": item.currency,
                     "最新价格": quote.price if quote else None,
                     "涨跌幅 %": round(quote.change_pct * 100, 2) if quote and quote.change_pct is not None else None,
                     "状态": "缓存 · 刷新失败" if quote and quote.stale else kind[quote.kind] if quote else "暂不可用",
                     "行情时间": timestamp_label(quote.market_time) if quote else "—",
                     "获取时间（北京）": datetime.fromisoformat(quote.fetched_at).astimezone(ZoneInfo("Asia/Shanghai")).strftime("%m-%d %H:%M:%S") if quote else "—"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"最新价格": st.column_config.NumberColumn(format="%.3f"), "涨跌幅 %": st.column_config.NumberColumn(format="%+.2f%%")}, height="auto")
    if errors or any(quote.stale for quote in quotes.values()):
        with st.expander("部分行情获取失败 · 查看详情", expanded=not quotes):
            for item in watchlist:
                error = errors.get(item.key) or (quotes[item.key].error if item.key in quotes and quotes[item.key].stale else "")
                if error:
                    st.caption(f"{item.name}（{item.symbol}）：{error}")
            st.info("可以稍后刷新，或打开左侧演示模式预览完整界面。缓存会保留原始获取时间。")


quote_panel()
st.markdown("")
analysis_tab, data_tab, about_tab = st.tabs(["走势与分析", "历史数据", "数据说明"])

with analysis_tab:
    selection, range_column, adjust_column = st.columns([2.2, 1.6, 1.4])
    by_key = {item.key: item for item in watchlist}
    if st.session_state.get("selected_key") not in by_key:
        st.session_state.selected_key = watchlist[0].key
    with selection:
        selected = st.selectbox("分析标的", list(by_key), key="selected_key")
        item = by_key[selected]
        st.caption(f"{item.name} · {MARKETS[item.market]} · {item.currency}")
    with range_column:
        period = st.selectbox("时间范围", ["近 1 个月", "近 3 个月", "近 6 个月", "近 1 年", "近 3 年", "自定义"], index=3, key="history_period")
    with adjust_column:
        adjustments = {"原始价格": "raw", "前复权": "qfq", "后复权": "hfq"} if item.market in {"CN", "ETF"} else {"原始价格": "raw", "Yahoo 复权": "qfq"} if item.market in {"HK", "US"} else {"单位净值": "raw"}
        adjustment = st.selectbox("价格口径", list(adjustments), key=f"adjust_{item.market}")
        adjust = adjustments[adjustment]
    if period == "自定义":
        start_col, end_col = st.columns(2)
        start = start_col.date_input("开始日期", TODAY - timedelta(days=365), max_value=TODAY)
        end = end_col.date_input("结束日期", TODAY, max_value=TODAY)
    else:
        days = {"近 1 个月": 30, "近 3 个月": 90, "近 6 个月": 180, "近 1 年": 365, "近 3 年": 1095}[period]
        start, end = TODAY - timedelta(days=days), TODAY
    refresh_history = st.button("更新历史数据", key="refresh_history", help="重新连接上游，补齐最近交易日的数据。")
    result = None
    if start > end:
        st.error("开始日期不能晚于结束日期，请调整日期。")
    else:
        with st.spinner("正在读取历史数据…"):
            try:
                result = demo_history(item, start, end) if demo else service.history(item, start, end, adjust, force=refresh_history)
            except Exception as exc:
                st.info(f"暂时无法加载 {item.name} 的历史数据：{exc}")
    if result is not None and not result.frame.empty:
        frame = result.frame
        if result.stale:
            st.warning(f"历史数据更新失败，现展示本地缓存。实际覆盖 {frame.date.min():%Y-%m-%d} ～ {frame.date.max():%Y-%m-%d}。{result.error}")
        chart_title, chart_type = st.columns([4, 1.2])
        with chart_title:
            st.markdown(f"### {escape(item.name)}　<span style='font-size:12px;font-weight:400;color:#8390a5'>{escape(item.symbol)}</span>", unsafe_allow_html=True)
            st.caption(f"{frame.date.min():%Y.%m.%d} — {frame.date.max():%Y.%m.%d}　/　{adjustment}")
        with chart_type:
            chart_style = st.segmented_control("图表类型", ["走势", "K 线"], default="走势", label_visibility="collapsed") if item.market != "FUND" else "走势"
        with st.container(border=True):
            st.plotly_chart(price_chart(frame, chart_style == "K 线", item.currency), width="stretch", config={"displayModeBar": False})
        metrics = summarize(frame)
        columns = st.columns(4)
        labels = [("区间涨跌幅", percent(metrics["return"])), ("最大回撤", percent(metrics["max_drawdown"])),
                  ("年化波动率", "—" if metrics["volatility"] is None else f"{metrics['volatility']:.2%}"), ("数据点", str(metrics["observations"]))]
        for column, (label, value) in zip(columns, labels):
            column.metric(label, value)
        st.caption("区间涨跌幅按首末价格计算；年化波动率按日收益标准差 × √252 估算。原始价格与基金单位净值未计分红再投，不等于投资总收益。")
        with st.expander("查看区间涨跌幅与回撤曲线"):
            st.plotly_chart(performance_chart(frame), width="stretch", config={"displayModeBar": False})
        st.caption(f"来源：{result.source}　·　历史获取时间：{timestamp_label(result.fetched_at)}　·　成交量单位：{'手' if item.market in {'CN', 'ETF'} else '股' if item.market in {'US', 'HK'} else '无'}")
    elif result is not None:
        st.info("所选区间没有交易或净值数据，请扩大时间范围。")

with data_tab:
    st.markdown("### 历史数据明细")
    if result is not None and not result.frame.empty:
        export = result.frame.copy()
        export["date"] = export.date.dt.strftime("%Y-%m-%d")
        export["symbol"] = item.symbol
        export["market"] = item.market
        export["currency"] = item.currency
        export["adjustment"] = "synthetic" if demo else adjust
        export["source"] = result.source
        export["fetched_at"] = result.fetched_at
        st.download_button("↓ 导出 CSV", export.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{'DEMO_' if demo else ''}{item.market}_{item.symbol}_{adjust}_{start}_{end}.csv", mime="text/csv")
        st.dataframe(export.sort_values("date", ascending=False), hide_index=True, width="stretch")
        st.caption("导出包含来源、币种、价格口径和获取时间，方便在 Excel 或 Python 中继续分析。")
    else:
        st.info("加载历史数据后，可以在这里查看和导出。")

with about_tab:
    st.markdown("### 先了解数据，再做判断")
    st.markdown("""
| 数据 | 获取方式 | 需要留意 |
| :--- | :--- | :--- |
| A 股 / 境内 ETF | AKShare 历史 + 东方财富报价 | 上游报价快照；未提供成交时间时会明确标注，获取时间不等于成交时间 |
| 港股 / 美股 / 海外 ETF | yfinance → Yahoo Finance | 最近一分钟行情，可能延迟；覆盖范围取决于 Yahoo，适合个人研究 |
| 场外基金 | AKShare → 天天基金 | 已公布单位净值，按净值日期展示；无盘中真实净值 |
| 历史价格 | 同上，本地 SQLite 缓存 | 默认日线；交易日历不同，跨市场日期不直接等价 |
| 演示模式 | 固定种子的合成序列 | 仅用于预览；数据库与真实行情隔离，CSV 标注 DEMO |
""")
    st.markdown("**缓存与刷新：** 默认每 15 秒自动检查行情，可选 5 / 30 / 60 / 120 / 300 秒或暂停；行情缓存随所选间隔到期，数据源响应慢时刷新会顺延。历史缓存 1 小时；刷新失败保留原时间并标注。原始价格后续更新最近 7 天，向前扩展区间时补齐更早历史。复权价格刷新时重载整个已缓存区间，保持口径一致。")
    st.markdown("**价格口径：** 前/后复权及 Yahoo 复权用于比较历史价格；不同来源的调整规则可能不同。复权价格与未复权价格分别缓存，避免混用。")
    st.markdown("**网络与使用：** 两个来源均不保证持续可用或固定延迟。数据使用遵循上游条款；本工具用于个人观察和研究。所有自选、缓存保存在本机 `data/`，不会随代码上传。")

st.markdown('<div class="footer">STOCKEASY　/　个人市场观察工作台 <span style="float:right">AKShare + yfinance　·　本地存储</span></div>', unsafe_allow_html=True)
