import plotly.graph_objects as go
from plotly.subplots import make_subplots

BLUE = "#3564eb"


def price_chart(frame, candle=False, currency="CNY"):
    has_volume = frame.volume.notna().any()
    fig = make_subplots(rows=2 if has_volume else 1, cols=1, shared_xaxes=True,
                        row_heights=[.8, .2] if has_volume else [1], vertical_spacing=.04 if has_volume else 0)
    if candle and frame[["open", "high", "low"]].notna().all().all():
        fig.add_trace(go.Candlestick(x=frame.date, open=frame.open, high=frame.high, low=frame.low, close=frame.close,
                                    increasing_line_color="#e65f65", decreasing_line_color="#13a38b", name="日 K"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=frame.date, y=frame.close, mode="lines", name="价格", line={"color": BLUE, "width": 2.5},
                                 fill="tozeroy", fillcolor="rgba(53,100,235,.06)",
                                 hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f} " + currency + "<extra></extra>"), row=1, col=1)
    if has_volume:
        colors = ["rgba(230,95,101,.38)" if change >= 0 else "rgba(19,163,139,.38)" for change in frame.close.diff().fillna(0)]
        fig.add_trace(go.Bar(x=frame.date, y=frame.volume, marker_color=colors, name="成交量", hovertemplate="%{y:,.0f}<extra>成交量</extra>"), row=2, col=1)
    fig.update_layout(height=390, margin={"l": 8, "r": 15, "t": 15, "b": 0}, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font={"family": "Arial, sans-serif", "color": "#718096", "size": 11},
                      showlegend=False, hovermode="x unified", xaxis_rangeslider_visible=False)
    fig.update_xaxes(showgrid=False, linecolor="#e9edf5", tickformat="%m/%d", rangeslider_visible=False)
    fig.update_yaxes(gridcolor="#edf0f6", zeroline=False, side="right", title_text=currency, row=1, col=1, rangemode="normal")
    bottom = float(frame.low.min()) if candle and frame.low.notna().any() else float(frame.close.min())
    top = float(frame.high.max()) if candle and frame.high.notna().any() else float(frame.close.max())
    padding = max((top - bottom) * .12, top * .005)
    fig.update_yaxes(range=[bottom - padding, top + padding], row=1, col=1)
    if has_volume:
        fig.update_yaxes(showgrid=False, side="right", nticks=3, row=2, col=1)
    return fig


def performance_chart(frame):
    close = frame.close
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame.date, y=(close / close.iloc[0] - 1) * 100, name="区间涨跌幅", line={"color": BLUE, "width": 2}))
    fig.add_trace(go.Scatter(x=frame.date, y=(close / close.cummax() - 1) * 100, name="回撤", fill="tozeroy",
                             line={"color": "#ed9b4c", "width": 1.5}, fillcolor="rgba(237,155,76,.10)"))
    fig.update_layout(height=280, margin={"l": 8, "r": 12, "t": 15, "b": 0}, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified", legend={"orientation": "h", "y": 1.15},
                      font={"color": "#718096", "size": 11})
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#edf0f6", ticksuffix="%", side="right", zerolinecolor="#e4e8f0")
    return fig
