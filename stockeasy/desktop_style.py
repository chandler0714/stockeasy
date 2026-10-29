CSS = """
<style>
:root{color-scheme:dark}
html,body,.stApp{font-family:Inter,-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif}
.stApp{background:#0b1220;color:#e4ecf7}
.block-container{padding:1rem 2rem 2rem;max-width:1920px}
[data-testid="stHeader"]{background:transparent;height:2rem}
[data-testid="stSidebar"]{background:#0e1727;min-width:185px;max-width:185px}
[data-testid="stSidebar"] *{color:#c3d0e4}
[data-testid="stSidebar"] h3{font-size:11px;color:#94a8c6;letter-spacing:1px}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#192b45;color:#e4ecf7}
[data-testid="stSidebar"] button{background:#1b304d;border-color:#354f73}
[data-testid="stSidebar"] hr{border-color:#2b3d57}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:10px 0}
.brand{font-size:25px;font-weight:750;letter-spacing:-1px;color:#e4ecf7!important;margin:4px 0}
.brand span{color:#809fff!important}.brand-sub{font-size:9px;color:#95a9c7!important;letter-spacing:1.5px;margin-bottom:28px}
h1{font-size:28px!important;letter-spacing:-.8px;font-weight:700!important;padding-top:2px!important}
h2{font-size:19px!important;letter-spacing:-.4px}h3{font-size:16px!important}
.eyebrow{font-size:10px;letter-spacing:2px;color:#98abc8;font-weight:650}
.hero-sub{color:#a3b4ce;font-size:13px;line-height:1.6}.date-chip{display:inline-block;color:#b6c6df;background:#152238;border:1px solid #2c3e59;padding:8px 12px;border-radius:8px;font-size:12px}
[data-testid="stMetric"]{background:#121e30;border:1px solid #2a3b55;padding:11px 16px;border-radius:11px}
[data-testid="stMetricLabel"]{color:#a9b9cf;font-size:11px}[data-testid="stMetricValue"]{font-size:25px;font-weight:650;letter-spacing:-.8px}
button{border-radius:7px!important;font-size:12px!important}
[data-testid="stAlert"]{border-radius:8px;font-size:12px}
[data-testid="stCaptionContainer"]{font-size:12px;line-height:1.6}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:12px;border-color:#2a3b55!important}
[data-testid="stTabs"] button{font-size:12px;padding:9px 12px}
.idea-card{background:#121e30;border:1px solid #2a3b55;border-radius:12px;padding:18px 19px 12px;min-height:290px;margin-bottom:6px}
.idea-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:13px}
.tag{font-size:10px;font-weight:600;padding:4px 8px;border-radius:5px;background:#25385b;color:#adc4ff}
.tag-volume{background:#3a2d24;color:#edc08e}.tag-recovery{background:#163a35;color:#7bd4c3}.tag-low{background:#302b49;color:#c7b6f0}
.asset-name{font-size:17px;font-weight:650;color:#e4ecf7;line-height:1.5}.asset-symbol{font-size:11px;color:#a1b2cb;letter-spacing:.4px;line-height:1.6}
.idea-numbers{display:flex;align-items:baseline;gap:10px;margin:5px 0 1px}.idea-price{font-size:25px;font-weight:650;letter-spacing:-.7px}.rise{color:#ff8797}.fall{color:#55d6b2}
.tiny{font-size:11px;color:#a1b2cb;line-height:1.6}.reason{font-size:13px;line-height:1.8;color:#bac8db;margin-top:7px;min-height:43px}
.reason-label{display:block;color:#95abc9;font-size:11px;margin-bottom:2px}
.signal-meaning{background:#182a43;border-left:2px solid #7fa8ff;border-radius:6px;padding:10px 12px;margin:9px 0 12px;color:#c9d8eb;font-size:12px;line-height:1.8}
.meaning-label{color:#a9c4ff;font-size:12px;font-weight:650;margin-bottom:3px}
.risk-note{border-top:1px solid #2a3b55;padding-top:8px;margin-top:8px;color:#d5bb97;font-size:11px;line-height:1.6}
.watch-item{padding:7px 0;border-bottom:1px solid #2a3b55;line-height:1.6}.watch-name{font-size:12px;font-weight:600;color:#d9e4f4}.watch-code{font-size:10px;color:#a1b2cb}.watch-price{font-size:14px;font-weight:600;text-align:right}.watch-status{font-size:9px;color:#a1b2cb}
.coverage{display:flex;gap:20px;background:#121e30;border:1px solid #2a3b55;border-radius:9px;padding:12px 15px;font-size:11px;color:#a9b9cf;margin:5px 0 12px}.coverage b{color:#d9e4f4;font-size:16px;margin-right:3px}
.risk-row{padding:11px 13px;border-left:3px solid #e4b474;background:#2b261f;border-radius:5px;margin-bottom:8px;font-size:12px;color:#e1c29b}
.footer{font-size:10px;color:#9caeca;border-top:1px solid #2a3b55;margin-top:25px;padding-top:15px}
.st-key-watch_rail{background:#121e30;border:1px solid #2a3b55;border-radius:13px;padding:18px!important;box-sizing:border-box;min-width:0}
.st-key-watch_rail [data-testid="stBaseButton-tertiary"]{justify-content:flex-start;text-align:left;font-weight:600}
.st-key-watch_rail [class*="st-key-watch_row_"]{border-bottom:1px solid #2a3b55;padding-bottom:12px}
.watch-quote{min-height:64px;line-height:1.5;text-align:right;padding-top:3px}
.watch-quote .watch-price{font-size:15px;white-space:nowrap}
.watch-change{font-size:12px;line-height:1.6;min-height:19px}
.watch-detail{font-size:11px;color:#a7b8d2;line-height:1.6;overflow-wrap:anywhere}
[data-testid="stSidebar"] [role="combobox"], [data-testid="stSidebar"] [role="combobox"] *{color:#e4ecf7!important}
.coverage{flex-wrap:wrap;row-gap:8px}
@media(min-width:1100px){.st-key-watch_rail{position:sticky;top:30px}}
@media(max-width:850px){.block-container{padding:1.2rem 1rem}.idea-card{min-height:260px}}
</style>
"""
