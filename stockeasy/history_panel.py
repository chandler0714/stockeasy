from datetime import timedelta

import streamlit as st

from stockeasy.analytics import summarize
from stockeasy.charts import performance_chart, price_chart
from stockeasy.demo import demo_history
from stockeasy.presentation import pct, time_label


def render_history(item, service, demo, today):
    analysis_tab, data_tab = st.tabs(["价格与风险", "历史数据 / 导出"])
    with analysis_tab:
        range_column, adjust_column, style_column = st.columns([1.5, 1.2, 1.2])
        period = range_column.selectbox("时间范围", ["近 1 个月", "近 3 个月", "近 6 个月", "近 1 年", "近 3 年", "自定义"], index=3, key="history_period")
        adjustments = {"原始价格": "raw", "前复权": "qfq", "后复权": "hfq"} if item.market in {"CN", "ETF"} else {"原始价格": "raw", "Yahoo 复权": "qfq"} if item.market in {"HK", "US"} else {"单位净值": "raw"}
        adjustment = adjust_column.selectbox("价格口径", list(adjustments), key=f"adjust_{item.market}")
        adjust = adjustments[adjustment]
        chart_style = style_column.selectbox("图表样式", ["价格走势", "日 K 线"] if item.market != "FUND" else ["净值走势"], key="chart_style")
        if period == "自定义":
            start_col, end_col = st.columns(2)
            start = start_col.date_input("开始日期", today - timedelta(days=365), max_value=today)
            end = end_col.date_input("结束日期", today, max_value=today)
        else:
            days = {"近 1 个月": 30, "近 3 个月": 90, "近 6 个月": 180, "近 1 年": 365, "近 3 年": 1095}[period]
            start, end = today - timedelta(days=days), today
        refresh = st.button("更新历史数据", key="refresh_history")
        result = None
        if start > end:
            st.error("开始日期不能晚于结束日期，请调整日期。")
        else:
            with st.spinner("正在读取历史数据…"):
                try:
                    result = demo_history(item, start, end) if demo else service.history(item, start, end, adjust, force=refresh)
                except Exception as exc:
                    st.info(f"暂时无法加载 {item.name} 的历史数据：{exc}")
        if result is not None and not result.frame.empty:
            frame = result.frame
            if result.stale:
                st.warning(f"更新失败，展示本地缓存。{result.error}")
            st.markdown(f"### {item.name} · {item.symbol}")
            st.caption(f"{frame.date.min():%Y.%m.%d} — {frame.date.max():%Y.%m.%d}　/　{adjustment}")
            with st.container(border=True):
                st.plotly_chart(price_chart(frame, chart_style == "日 K 线", item.currency), width="stretch", config={"displayModeBar": False})
            metrics = summarize(frame)
            values = [("区间涨跌幅", pct(metrics["return"])), ("最大回撤", pct(metrics["max_drawdown"])),
                      ("年化波动率", "—" if metrics["volatility"] is None else f"{metrics['volatility']:.2%}"), ("数据点", str(metrics["observations"]))]
            for column, (label, value) in zip(st.columns(4), values):
                column.metric(label, value)
            st.caption("原始价格、基金单位净值未计分红再投。波动率按日收益标准差 × √252；跨市场交易日不同。")
            with st.expander("区间涨跌幅与回撤曲线"):
                st.plotly_chart(performance_chart(frame), width="stretch", config={"displayModeBar": False})
            st.caption(f"来源：{result.source}　·　获取：{time_label(result.fetched_at)}　·　成交量单位：{'手' if item.market in {'CN', 'ETF'} else '股' if item.market in {'US', 'HK'} else '无'}")
        elif result is not None:
            st.info("所选区间没有交易或净值数据，请扩大时间范围。")
    with data_tab:
        if result is not None and not result.frame.empty:
            export = result.frame.copy()
            export["date"] = export.date.dt.strftime("%Y-%m-%d")
            for column, value in {"symbol": item.symbol, "market": item.market, "currency": item.currency,
                                  "adjustment": "synthetic" if demo else adjust, "source": result.source, "fetched_at": result.fetched_at}.items():
                export[column] = value
            st.download_button("↓ 导出 CSV", export.to_csv(index=False).encode("utf-8-sig"), file_name=f"{'DEMO_' if demo else ''}{item.market}_{item.symbol}_{adjust}_{start}_{end}.csv", mime="text/csv")
            st.dataframe(export.sort_values("date", ascending=False), hide_index=True, width="stretch")
        else:
            st.info("加载历史数据后，可以在这里查看和导出。")
