# ↗ Stockeasy

一个在本机运行的中文股票与基金观察看板。用 AKShare 和 yfinance 获取行情与历史数据，支持自选管理、价格走势、日 K 线、区间涨跌幅、回撤分析和 CSV 导出。

## 快速开始

推荐 Python 3.12（最低 3.11）。在项目目录运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Windows 激活命令为 `.venv\Scripts\activate`。

打开 <http://127.0.0.1:8501>。默认连接真实数据；首次加载需要等待上游响应。无需 API 密钥。

**先看界面效果：** 打开 <http://127.0.0.1:8501/?demo=1>，或开启左侧「演示模式」。演示价格和图表是合成数据，不能用作市场判断；关闭开关恢复真实数据。

## 首版功能

- A 股、境内 ETF、港股、美股及海外 ETF、境内场外基金的自选列表，最多 20 个标的。
- 行情快照与市场筛选，手动刷新或每 60 / 120 / 300 秒刷新。
- 历史日线、价格曲线、成交量、K 线和自定义日期。
- 区间涨跌幅、最大回撤、年化波动率，以及收益/回撤曲线。
- 原始价格、A 股/ETF 前后复权、Yahoo 复权；基金使用单位净值。
- CSV 包含市场、币种、价格口径、数据来源和获取时间。
- SQLite 本地缓存和自选持久化；失败回退缓存并标注原获取时间。

## 数据覆盖与限制

| 范围 | 接入 | 说明 |
| --- | --- | --- |
| A 股 | AKShare → 东方财富 | 最新报价快照、历史日线。报价接口未提供成交时间时只显示获取时间，不能据此判断零延迟 |
| 境内 ETF | AKShare 历史 + 东方财富单证券报价 | 报价直接调用 AKShare 同一上游的单证券公开接口，正确区分沪深市场，避免每次下载全部 ETF |
| 港股 / 美股 / 海外 ETF | yfinance → Yahoo Finance | 行情取最近一分钟记录，可能延迟；历史取日线。Yahoo 可能限流，当前网络也可能无法访问 |
| 场外基金 | AKShare → 天天基金 | 已公布单位净值、净值日期；没有盘中官方实时净值 |

免费来源没有稳定性、时延或永久可用保证。yfinance 是非官方工具，面向个人研究，实际数据使用须遵循 [Yahoo 条款及项目说明](https://ranaroussi.github.io/yfinance/)。AKShare 文档：[股票](https://akshare.akfamily.xyz/data/stock/stock_quote.html)、[基金](https://akshare.akfamily.xyz/data/fund/fund_public.html)。

**分析口径：** 区间涨跌幅为末价格 / 首价格 − 1；回撤相对于区间内历史最高价；波动率按日收益标准差 × √252 估算。原始价格、基金单位净值未计分红再投，不能直接等同投资总收益。短区间、不同市场交易日历和停牌会影响解读。成交量单位：境内股票/ETF 为手，Yahoo 为股。

## 缓存与隐私

- `data/market.sqlite` 保存真实自选和行情；`data/demo.sqlite` 保存演示自选。演示价格不写入真实缓存。
- `STOCKEASY_DATA_DIR` 可指定本地数据目录，`STOCKEASY_DEMO=1` 可用于离线演示启动。
- 行情缓存 60 秒、历史缓存 1 小时；「刷新」可主动更新。原始历史更新最近 7 天，向前扩展时下载更早区间；复权序列更新时重载整个已缓存范围，避免拼接不同时点口径。
- 上游请求在独立进程运行，25 秒强制截止。失败不会伪造行情或自动切换到演示。
- 本地数据库、虚拟环境、密钥和下载数据均被 `.gitignore` 排除。服务默认只监听本机 `127.0.0.1`。
- 没有交易接口，也不读取券商账户。

如果遇到连接失败，先检查本机网络和代理配置，稍后再试。演示模式可离线体验所有主要界面。

## 验证

```sh
python -m unittest discover -s tests -v
```

测试覆盖数据标准化、缓存隔离与回退、收益/回撤计算、自选持久化，以及 Streamlit 界面流程。上游库在测试中替换为固定响应，不需要连接真实行情。

当前接入验证与已知限制见 [docs/verification.md](docs/verification.md)。

自动测试配置模板见 [docs/ci-tests.yml](docs/ci-tests.yml)。当前推送凭据不含 GitHub workflow 权限，因此未启用云端自动测试；之后可自行复制到 `.github/workflows/tests.yml`。

## 项目结构

```text
app.py                  Streamlit 界面
stockeasy/models.py     市场与数据模型
stockeasy/providers.py  AKShare / Yahoo 数据适配与标准化
stockeasy/worker.py     有超时上限的数据请求进程
stockeasy/service.py    缓存与刷新策略
stockeasy/storage.py    SQLite 持久化
stockeasy/analytics.py  收益与风险指标
stockeasy/charts.py     Plotly 图表
stockeasy/demo.py       合成演示数据
tests/                  离线测试
```
