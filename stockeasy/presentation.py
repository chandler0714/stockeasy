from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from stockeasy.models import MARKETS


def beijing_day():
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def pct(value):
    return "—" if value is None else f"{value:+.2%}"


def quote_status(quote, error="", pending=False, demo=False):
    if demo:
        return "合成演示"
    if error or (quote and quote.stale):
        status = "缓存 / 更新失败" if quote else "更新失败"
        return status + (" · 重试中" if pending else " · 等待重试")
    if quote:
        status = "已公布净值" if getattr(quote, "kind", "") == "nav" else "报价快照"
        return status + (" · 更新中" if pending else "")
    return "更新中" if pending else "暂不可用"


def time_label(value):
    if not value:
        return "成交时间未提供"
    if len(value) == 10:
        return value
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%m-%d %H:%M 北京") if parsed.tzinfo else value
    except ValueError:
        return value


def sparkline(prices, width=280, height=58):
    if len(prices) < 2:
        return ""
    bottom, top = min(prices), max(prices)
    span = top - bottom or max(abs(top) * .01, 1)
    points = " ".join(f"{4 + i * (width - 8) / (len(prices) - 1):.1f},{height - 6 - (value - bottom) / span * (height - 12):.1f}" for i, value in enumerate(prices))
    color = "#ff8797" if prices[-1] >= prices[0] else "#55d6b2"
    return f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="近{len(prices)}个数据点的价格走势"><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def idea_html(idea, category):
    colors = {"趋势延续": "", "量能变化": "tag-volume", "回撤修复": "tag-recovery", "低波动": "tag-low"}
    item = idea.instrument
    price_label = "单位净值" if item.market == "FUND" else "日线价格"
    direction = "rise" if idea.momentum20 >= 0 else "fall"
    reason = idea.reasons[idea.categories.index(category)] if category in idea.categories else idea.reasons[0]
    explanations = {
        "趋势延续": "最近一段时间整体上涨，价格仍在上行均线上方。可以点开更长区间，查看这段上涨伴随多大回撤。",
        "回撤修复": "从近期高点回落后，最近几日出现回升。可以查看离高点还有多远，以及回升能否持续。",
        "低波动": "近期价格起伏相对较小，可与同类产品比较历史波动和回撤；价格仍可能下跌。",
    }
    if category == "量能变化":
        latest = idea.prices[-1] / idea.prices[-2] - 1
        move = f"上涨 {latest:.2%}" if latest > 0 else f"下跌 {abs(latest):.2%}" if latest < 0 else "持平"
        meaning = f"交易更活跃，最近一个交易日{move}。请结合完整走势，观察放量发生在上涨还是下跌过程中。"
    else:
        meaning = explanations.get(category, "观察到价格或交易量变化，可点开走势核对触发依据和数据日期。")
    return f'''<div class="idea-card">
<div class="idea-top"><span class="tag {colors[category]}">{category}</span><span class="tiny">{escape(MARKETS[item.market])}</span></div>
<div class="asset-name">{escape(item.name)}</div><div class="asset-symbol">{escape(item.symbol)} · {item.currency}</div>
<div class="tiny">{price_label} / 近20日变化</div>
<div class="idea-numbers"><span class="idea-price">{idea.prices[-1]:,.3f}</span><span class="{direction}" style="font-size:12px">{idea.momentum20:+.1%}</span></div>
{sparkline(idea.prices)}<div class="reason"><span class="reason-label">触发依据</span>{escape(reason)}</div>
<div class="signal-meaning"><div class="meaning-label">这条信息说明什么</div>{escape(meaning)}</div>
<div class="tiny">截至 {idea.as_of} · {escape(idea.source)} · {'单位净值' if item.market == 'FUND' else '复权日线'}</div>
<div class="risk-note">观察风险：{escape(idea.risk)}</div></div>'''
