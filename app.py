from datetime import datetime, timedelta
from html import escape
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from stockeasy.demo import demo_history, demo_quote
from stockeasy.desktop_style import CSS
from stockeasy.discovery import BENCHMARKS, CATALOG, CATEGORIES, HistoryScanner, available_candidates, build_report, universe
from stockeasy.feeds import QuoteFeed
from stockeasy.history_panel import render_history
from stockeasy.models import Instrument, MARKETS
from stockeasy.presentation import beijing_day, idea_html, pct, quote_status, time_label
from stockeasy.service import MarketService
from stockeasy.storage import Store

st.set_page_config(page_title="Stockeasy · PC 市场工作台", page_icon="↗", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)
TODAY = beijing_day()
DATA_DIR = Path(os.environ.get("STOCKEASY_DATA_DIR", Path(__file__).parent / "data"))


@st.cache_resource
def real_runtime(path):
    service = MarketService(Store(Path(path)))
    return service, HistoryScanner(service), QuoteFeed(service)


@st.cache_data(ttl=3600, show_spinner=False)
def demo_results(items, today):
    return {item.key: (item, demo_history(item, today - timedelta(days=160), today)) for item in items}


def action(kind, key):
    st.session_state.pending_action = (kind, key)
    st.rerun(scope="app")


with st.sidebar:
    st.markdown('<div class="brand">↗ stock<span>easy</span></div><div class="brand-sub">YOUR MARKET WORKSPACE</div>', unsafe_allow_html=True)
    demo = st.toggle("演示模式", value=os.environ.get("STOCKEASY_DEMO") == "1" or st.query_params.get("demo") == "1", key="demo_mode")
    st.caption("合成数据 / 仅供界面体验" if demo else "腾讯报价 · AKShare / yfinance 历史")

store = Store(DATA_DIR / ("demo.sqlite" if demo else "market.sqlite"))
watchlist = store.watchlist()
pending = st.session_state.pop("pending_action", None)
if pending:
    kind, key = pending
    by_catalog = {item.key: item for item in universe(watchlist)}
    if kind == "add" and key in by_catalog:
        if key not in {item.key for item in watchlist} and len(watchlist) < 20:
            watchlist.append(by_catalog[key])
            store.save_watchlist(watchlist)
    elif kind == "remove":
        watchlist = [item for item in watchlist if item.key != key]
        store.save_watchlist(watchlist)
        if st.session_state.get("inspection_key") == key:
            st.session_state.pop("inspection_key", None)
        if st.session_state.get("selected_key") == key:
            st.session_state.pop("selected_key", None)
    elif kind == "inspect" and key in by_catalog:
        st.session_state.inspection_key = key
        st.session_state.selected_key = key
        st.session_state.workspace = "深度分析"

with st.sidebar:
    st.markdown("### 工作空间")
    workspace = st.radio("导航", ["今日工作台", "深度分析", "量化研究", "数据说明"], key="workspace", label_visibility="collapsed")
    st.divider()
    st.markdown("### 数据设置")
    refresh_label = st.selectbox("行情自动刷新", ["暂停（手动刷新）", "每 5 秒", "每 15 秒", "每 30 秒", "每 60 秒", "每 120 秒", "每 300 秒"], index=1, key="refresh_interval_v3")
    st.caption("报价默认每 5 秒轮询，上游响应慢时顺延；基金净值缓存至少 5 分钟，推荐依据日线筛选。")
    st.divider()
    st.caption("个人观察工作台\n\n本机存储 · 无交易接口\n\nPC 宽屏布局 / 建议 1440px+")

interval = None if refresh_label.startswith("暂停") else int(refresh_label.split()[1])
quote_poll_interval = 2  # Collect finished background results without rescheduling paused feeds.
service = MarketService(store)
if not demo:
    service, scanner, feed = real_runtime(str(store.path))
    scanner.start(universe(watchlist), TODAY)
quote_items = list({item.key: item for item in watchlist + BENCHMARKS}.values())


def get_quotes(force=False):
    if demo:
        return {item.key: demo_quote(item, TODAY) for item in quote_items}, {}, set()
    feed.refresh(quote_items, interval=interval or 60, force=force, paused=interval is None)
    return feed.snapshot()


def scan_snapshot(force=False):
    if demo:
        return demo_results(tuple(universe(watchlist)), TODAY), {}, 0
    scanner.start(universe(watchlist), TODAY, force=force)
    return scanner.snapshot()


header, date_box = st.columns([5, 1.5], vertical_alignment="center")
with header:
    st.markdown('<div class="eyebrow">MARKET DESK / 每日市场观察</div>', unsafe_allow_html=True)
    st.title("今日市场工作台")
    st.markdown('<div class="hero-sub">用可解释的信号筛选产品，让价格、理由和风险出现在同一屏。</div>', unsafe_allow_html=True)
with date_box:
    st.markdown(f'<div class="date-chip">{TODAY:%Y.%m.%d}　 /　PC 工作台</div>', unsafe_allow_html=True)
if demo:
    st.warning("演示模式 · 以下价格、推荐信号与图表均为合成数据。关闭左侧开关后接入真实数据。")
else:
    st.caption("免费来源可能延迟或不可用；当日推荐是观察池内的规则筛选，依据最近可用日线，不是全市场排名或收益预测。")

main_column, rail_column = st.columns([3.35, 1.15], gap="large")


@st.fragment(run_every=quote_poll_interval)
def overview():
    if beijing_day() != TODAY:
        st.rerun(scope="app")
    title, refresh = st.columns([4, 1])
    title.markdown("### 核心资产方向")
    force = refresh.button("↻ 更新行情", key="refresh_quotes", width="stretch")
    quotes, errors, waiting = get_quotes(force)
    for column, item in zip(st.columns(4), BENCHMARKS):
        quote = quotes.get(item.key)
        with column:
            st.metric(item.name, f"{quote.price:,.3f}" if quote else "—", pct(quote.change_pct) if quote and quote.change_pct is not None else None, delta_color="inverse")
            status = quote_status(quote, errors.get(item.key, ""), pending=item.key in waiting, demo=demo)
            st.caption(f"{item.currency} · {status}")
            if quote and not demo:
                st.caption(f"{quote.source.split(' · ')[0]} · 源时间 {time_label(quote.market_time)}")
    checked = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
    status = f"自动刷新中 · 每 {interval} 秒" if interval else "自动刷新已暂停"
    st.caption(f"{status}　·　界面更新 {checked}（北京时间）　·　ETF 代理行情，非指数点位")
    if not demo:
        with st.expander("行情来源与刷新状态"):
            st.caption("免费快照可能延时；非交易时段显示最近可用报价。源时间与本机获取时间分别列出，不能把刷新成功理解为价格正在变动。失败后至少等待 30 秒再自动重试，点击更新可主动重试。")
            for item in quote_items:
                quote = quotes.get(item.key)
                reason = errors.get(item.key) or (quote.error if quote and quote.stale else "")
                label = quote_status(quote, reason, pending=item.key in waiting)
                detail = f"{quote.source} · 源时间 {time_label(quote.market_time)} · 获取 {time_label(quote.fetched_at)}" if quote else "尚无可用报价"
                st.caption(f"{item.name}（{item.symbol}）· {label} · {detail}" + (f"\n\n失败原因：{reason}" if reason else ""))
    valid = [q for key, q in quotes.items() if key in {item.key for item in watchlist} and key not in errors and not q.stale and q.change_pct is not None]
    up, down = sum(q.change_pct > 0 for q in valid), sum(q.change_pct < 0 for q in valid)
    st.markdown(f'<div class="coverage"><span>自选样本上涨 <b>{up}</b></span><span>下跌 <b>{down}</b></span><span>有效报价 <b>{len(valid)}/{len(watchlist)}</b></span></div>', unsafe_allow_html=True)


@st.fragment(run_every=15)
def recommendations():
    if beijing_day() != TODAY:
        st.rerun(scope="app")
    title, refresh = st.columns([4, 1])
    title.markdown("### 当日推荐")
    force = refresh.button("重新筛选", key="rescan", width="stretch")
    results, errors, pending_count = scan_snapshot(force)
    report = build_report(results, TODAY)
    total = len(universe(watchlist))
    st.caption(f"观察池 {total} 个 · 可评估 {report.eligible} 个 · 后台加载 {pending_count} 个　/　日线筛选，不构成收益预测")
    if pending_count:
        st.progress((total - pending_count) / total, text="正在后台获取日线，已完成的产品先展示")
    category = st.segmented_control("推荐理由", ["全部"] + list(CATEGORIES), default="全部", key="idea_category", label_visibility="collapsed") or "全部"
    ideas = [idea for idea in report.ideas if category == "全部" or category in idea.categories]
    if not ideas and pending_count:
        st.info("正在后台筛选，符合条件的产品会自动出现；其他区域可以继续操作。")
    elif not ideas:
        st.info("当前没有符合条件的产品。数据不足、过期或更新失败的记录不会强行推荐。")
    shown_categories = set()
    for offset in range(0, min(len(ideas), 6), 2):
        for column, idea in zip(st.columns(2), ideas[offset:offset + 2]):
            with column:
                label = category if category != "全部" else next((name for name in idea.categories if name not in shown_categories), idea.categories[0])
                shown_categories.add(label)
                st.markdown(idea_html(idea, label), unsafe_allow_html=True)
                inspect, add = st.columns([1.2, 1])
                if inspect.button("查看走势 ↗", key=f"idea_inspect_{idea.instrument.key}", width="stretch"):
                    action("inspect", idea.instrument.key)
                selected = idea.instrument.key in {item.key for item in watchlist}
                if add.button("✓ 已在自选" if selected else "＋ 加入自选", key=f"idea_add_{idea.instrument.key}", disabled=selected or len(watchlist) >= 20, width="stretch"):
                    action("add", idea.instrument.key)
    st.markdown("### 风险观察")
    st.caption("同一观察池的日线风险信号；不是实时预警。")
    if report.risks:
        for alert in report.risks[:4]:
            st.markdown(f'<div class="risk-row"><b>{escape(alert.instrument.name)}</b>　{escape(alert.reason)} <span class="tiny">/ 截至 {alert.as_of}</span></div>', unsafe_allow_html=True)
    elif report.eligible:
        st.info("当前已评估样本未触发回撤 ≥15% 或年化波动 ≥35% 的观察阈值；未加载数据不代表没有风险。")
    else:
        st.info("暂无可评估的日线，暂不判断风险。等待加载完成，或查看下方数据覆盖说明。")
    excluded = len(results) - report.eligible
    if errors or excluded:
        with st.expander(f"数据覆盖说明 · {len(errors)} 个连接失败 / {excluded} 个暂不评估"):
            for key, reason in errors.items():
                st.caption(f"{key}：{reason}")
            if excluded:
                st.caption("暂不评估包括少于 30 个有效日线数据点、价格日期超过 7 个自然日、未来日期或缓存刷新失败。")
    with st.expander("这些产品为什么入选？"):
        st.markdown("**趋势延续：** 20 日涨幅 >2%，价格高于向上的 20 日均线。**量能变化：** 最新成交量 ≥ 前 20 日均量的 1.5 倍。**回撤修复：** 距近 60 日高点仍跌 ≥5%，近 5 日回升 ≥1.5%。**低波动：** 近 60 日年化波动 <18%、当前回撤 <8%。")
        st.caption("筛选使用前复权 / Yahoo 复权日线，场外基金使用单位净值；少于 60 日时使用可用记录。规则仅帮助观察，放量不等于上涨，低波动不等于低风险。价格截止日可能早于今天。")


@st.fragment(run_every=quote_poll_interval)
def watch_quote(item):
    if demo:
        quote, errors, waiting = demo_quote(item, TODAY), {}, set()
    else:
        quotes, errors, waiting = get_quotes()
        quote = quotes.get(item.key)
    status = quote_status(quote, errors.get(item.key, ""), pending=item.key in waiting, demo=demo)
    stamp = time_label(quote.market_time or quote.fetched_at) if quote else ""
    color = "rise" if quote and quote.change_pct is not None and quote.change_pct >= 0 else "fall"
    value = f"{quote.price:,.3f}" if quote else "—"
    change = pct(quote.change_pct) if quote and quote.change_pct is not None else ""
    detail = status + (f" · {stamp}" if stamp else "")
    st.markdown(f'<div class="watch-quote"><div class="watch-price">{value}</div><div class="watch-change {color}">{change}</div><div class="watch-detail">{escape(detail)}</div></div>', unsafe_allow_html=True)


def watch_rail():
    if beijing_day() != TODAY:
        st.rerun(scope="app")
    with st.container(key="watch_rail"):
        st.markdown("### 我的自选")
        st.caption("关注变化，或发现下一个观察对象")
        candidates = available_candidates(watchlist)
        selected_tab, discover_tab = st.tabs([f"已选 {len(watchlist):02d}", f"发现 {len(candidates):02d}"])
        with selected_tab:
            if not watchlist:
                st.info("暂无自选，请在发现列表或下方添加产品。")
            with st.container(height=430, border=False):
                for item in watchlist:
                    row_key = f"watch_row_{item.market}_{item.symbol.replace('-', '_')}"
                    with st.container(key=row_key):
                        name, price, remove = st.columns([2, 1.5, .65], vertical_alignment="top", gap="small")
                        with name:
                            if st.button(item.name, key=f"watch_inspect_{item.key}", type="tertiary", width="stretch"):
                                action("inspect", item.key)
                            st.caption(f"{item.symbol} · {item.currency}")
                        with price:
                            watch_quote(item)
                        if remove.button("−", key=f"watch_remove_{item.key}", help=f"移除 {item.name}", width="stretch"):
                            action("remove", item.key)
            with st.expander("批量管理"):
                if watchlist:
                    st.selectbox("移除标的", [item.key for item in watchlist], key="remove_key")
                    if st.button("移除自选", key="remove_watch"):
                        action("remove", st.session_state.remove_key)
        with discover_tab:
            query = st.text_input("搜索可添加产品", placeholder="名称或代码", key="discover_query").strip().lower()
            for item in candidates:
                if query and query not in (item.name + item.symbol).lower():
                    continue
                name, add = st.columns([3, 1])
                name.markdown(f'<div class="watch-item"><div class="watch-name">{escape(item.name)}</div><div class="watch-code">{item.symbol} · {MARKETS[item.market]}</div></div>', unsafe_allow_html=True)
                if add.button("＋", key=f"discover_add_{item.key}", help=f"添加 {item.name}", disabled=len(watchlist) >= 20):
                    action("add", item.key)
            if not candidates:
                st.info("基础观察池已全部加入自选，仍可添加其他代码。")
        with st.expander("添加其他代码"):
            with st.form("add_form"):
                st.selectbox("市场", list(MARKETS), format_func=lambda key: MARKETS[key], key="new_market")
                st.text_input("证券代码", placeholder="600519 / 00700 / AAPL", key="new_symbol", max_chars=20)
                st.text_input("显示名称（可选）", key="new_name", max_chars=40)
                submitted = st.form_submit_button("＋ 添加自选", key="add_watch", width="stretch")
            if submitted:
                try:
                    item = Instrument.create(st.session_state.new_market, st.session_state.new_symbol, st.session_state.new_name)
                    if item.key in {value.key for value in watchlist}:
                        st.info("该产品已在自选中")
                    elif len(watchlist) >= 20:
                        st.error("最多支持 20 个自选，请先移除不需要的产品")
                    else:
                        store.save_watchlist(watchlist + [item])
                        st.rerun(scope="app")
                except ValueError as exc:
                    st.error(str(exc))
        st.caption("自选保存在本机。发现列表为固定观察池，不代表已获推荐。")


selected_items = {item.key: item for item in watchlist}
inspection = st.session_state.get("inspection_key")
if inspection:
    selected_items.update({item.key: item for item in universe(watchlist) if item.key == inspection})
active_item = None
if selected_items:
    if st.session_state.get("selected_key") not in selected_items:
        st.session_state.selected_key = next(iter(selected_items))
    with st.sidebar.expander("图表联动标的", expanded=workspace == "深度分析"):
        active_key = st.selectbox("联动分析标的", list(selected_items), key="selected_key")
        active_item = selected_items[active_key]

with main_column:
    overview()
    if workspace == "今日工作台":
        recommendations()
    elif workspace == "深度分析":
        if active_item:
            render_history(active_item, service, demo, TODAY)
        else:
            st.info("请从右侧添加一个产品，再查看历史分析。")
    elif workspace == "量化研究":
        from stockeasy.research_panel import render_research
        render_research(watchlist, active_item, service, demo, TODAY)
    else:
        st.markdown("### 数据与筛选方法")
        st.markdown("股票/ETF 报价优先使用腾讯财经单证券快照，失败后尝试原东方财富 / Yahoo 通道；境内历史使用 AKShare，港美股历史使用 yfinance，场外基金使用已公布单位净值。报价可能延迟，源时间与获取时间不同，非交易时段保留最近可用报价。")
        st.markdown("**观察池范围：** 基础观察池 12 个产品，加当前自选。核心方向使用 ETF 作为市场代理；上涨/下跌数仅统计有效自选样本，不代表全市场。")
        st.markdown("**推荐口径：** 依据最近可用复权日线；信号价格显示截至日期。少于 30 个数据点、超过 7 个自然日未更新或请求失败回退的历史不入选。没有符合条件的产品时保持空缺。")
        st.markdown("**刷新与缓存：** 股票/ETF 报价默认每 5 秒后台轮询，慢请求顺延，失败后至少等待 30 秒；场外基金净值至少缓存 5 分钟，可手动更新。行情失败保留原时间并标注。历史扫描独立后台进行，默认小时缓存，点击重新筛选主动更新。暂停行情不暂停历史任务进度。")
        st.markdown("**本地数据：** 真实数据与合成演示数据隔离。自选和缓存位于本机 data/ 目录，不随源码上传；无交易或券商账户接口。")

with rail_column:
    watch_rail()

st.markdown('<div class="footer">STOCKEASY / PC 市场工作台　　可解释信号 · 本地存储 <span style="float:right">AKShare + yfinance</span></div>', unsafe_allow_html=True)
