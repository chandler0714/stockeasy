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
    direction = "rise" if idea.momentum20 >= 0 else "fall"
    reason = idea.reasons[idea.categories.index(category)] if category in idea.categories else idea.reasons[0]
    return f'''<div class="idea-card">
<div class="idea-top"><span class="tag {colors[category]}">{category}</span><span class="tiny">{escape(MARKETS[item.market])}</span></div>
<div class="asset-name">{escape(item.name)}</div><div class="asset-symbol">{escape(item.symbol)} · {item.currency}</div>
<div class="idea-numbers"><span class="idea-price">{idea.prices[-1]:,.3f}</span><span class="{direction}" style="font-size:12px">{idea.momentum20:+.1%}</span><span class="tiny">20 日</span></div>
{sparkline(idea.prices)}<div class="reason">{escape(reason)}</div>
<div class="tiny">截至 {idea.as_of} · {escape(idea.source)} · {'单位净值' if item.market == 'FUND' else '复权日线'}</div>
<div class="risk-note">观察风险：{escape(idea.risk)}</div></div>'''
