CSS = """
<style>
html,body,.stApp{font-family:Inter,-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif}
.stApp{background:#f4f6fa;color:#192740}
.block-container{padding:1rem 2rem 2rem;max-width:1920px}
[data-testid="stVerticalBlock"]{gap:.65rem}
[data-testid="stHeader"]{background:transparent;height:2rem}
[data-testid="stSidebar"]{background:#111f36;min-width:185px;max-width:185px}
[data-testid="stSidebar"] *{color:#c3cfe3}
[data-testid="stSidebar"] h3{font-size:11px;color:#7890b3;letter-spacing:1px}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#1a2e4b;color:#fff}
[data-testid="stSidebar"] button{background:#1b3152;border-color:#304667}
[data-testid="stSidebar"] hr{border-color:#2a3c57}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:10px 0}
.brand{font-size:25px;font-weight:750;letter-spacing:-1px;color:white!important;margin:4px 0}
.brand span{color:#809fff!important}.brand-sub{font-size:9px;color:#758aab!important;letter-spacing:1.5px;margin-bottom:28px}
h1{font-size:28px!important;letter-spacing:-.8px;font-weight:700!important;padding-top:2px!important}
h2{font-size:19px!important;letter-spacing:-.4px}h3{font-size:16px!important}
.eyebrow{font-size:10px;letter-spacing:2px;color:#7d8ca3;font-weight:650}
.hero-sub{color:#7c8aa1;font-size:12px}.date-chip{display:inline-block;color:#5e7193;background:white;border:1px solid #e2e8f2;padding:8px 12px;border-radius:8px;font-size:12px}
[data-testid="stMetric"]{background:#fff;border:1px solid #e4eaf2;padding:11px 16px;border-radius:11px}
[data-testid="stMetricLabel"]{color:#7b89a0;font-size:11px}[data-testid="stMetricValue"]{font-size:25px;font-weight:650;letter-spacing:-.8px}
button{border-radius:7px!important;font-size:12px!important}
[data-testid="stAlert"]{border-radius:8px;font-size:12px}
[data-testid="stCaptionContainer"]{font-size:11px}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:12px;border-color:#e4eaf2!important}
[data-testid="stTabs"] button{font-size:12px;padding:9px 12px}
.idea-card{background:#fff;border:1px solid #e5eaf3;border-radius:12px;padding:18px 19px 12px;min-height:290px;margin-bottom:6px}
.idea-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:13px}
.tag{font-size:10px;font-weight:600;padding:4px 8px;border-radius:5px;background:#edf1ff;color:#4c69ce}
.tag-volume{background:#fff1e6;color:#b87c3b}.tag-recovery{background:#ebf6f4;color:#3e9487}.tag-low{background:#f1edfa;color:#8563b2}
.asset-name{font-size:17px;font-weight:650;color:#24334a;line-height:1.5}.asset-symbol{font-size:10px;color:#96a1b2;letter-spacing:.4px}
.idea-numbers{display:flex;align-items:baseline;gap:10px;margin:5px 0 1px}.idea-price{font-size:25px;font-weight:650;letter-spacing:-.7px}.rise{color:#d85c67}.fall{color:#199985}
.tiny{font-size:10px;color:#96a1b2}.reason{font-size:12px;line-height:1.8;color:#53627a;margin-top:7px;min-height:43px}
.risk-note{border-top:1px solid #edf0f5;padding-top:8px;margin-top:8px;color:#9d8b77;font-size:10px;line-height:1.6}
.watch-item{padding:7px 0;border-bottom:1px solid #eef1f6;line-height:1.6}.watch-name{font-size:12px;font-weight:600;color:#33445f}.watch-code{font-size:10px;color:#97a2b4}.watch-price{font-size:14px;font-weight:600;text-align:right}.watch-status{font-size:9px;color:#a2adbc}
.coverage{display:flex;gap:20px;background:#fff;border:1px solid #e5eaf2;border-radius:9px;padding:12px 15px;font-size:11px;color:#7d8da4;margin:5px 0 12px}.coverage b{color:#364961;font-size:16px;margin-right:3px}
.risk-row{padding:11px 13px;border-left:3px solid #e4b474;background:#fcfaf6;border-radius:5px;margin-bottom:8px;font-size:12px;color:#8d7555}
.footer{font-size:10px;color:#9ba6b7;border-top:1px solid #e0e6f0;margin-top:25px;padding-top:15px}
.st-key-watch_rail{background:#fff;border:1px solid #e3e9f2;border-radius:13px;padding:17px!important}
.st-key-watch_rail [data-testid="stVerticalBlock"]{gap:.15rem}
.st-key-watch_rail [data-testid="stButton"] button{min-height:26px;padding:2px 6px}
.st-key-watch_rail [data-testid="stCaptionContainer"] p{margin-bottom:0}
@media(min-width:1100px){.st-key-watch_rail{position:sticky;top:30px}}
@media(max-width:850px){.block-container{padding:1.2rem 1rem}.idea-card{min-height:260px}}
</style>
"""
