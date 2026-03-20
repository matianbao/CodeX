# A股日度交易情绪评估器

这是一个可按**天级定时**运行的 Python 脚本，用于对 A 股市场做情绪评估，输出类似“中性偏谨慎 / 偏暖 / 恐慌”的判断结果。

## 评估逻辑

脚本将情绪拆成 6 个维度并分别打分：

1. 成交额
2. 指数强弱
3. 市场宽度（上涨/下跌家数）
4. 赚钱效应（涨停/跌停）
5. 杠杆 / 增量资金（两融、北向）
6. 风格方向（防御 or 进攻）

最终输出 0-100 的综合情绪分数，并映射为：

- 80-100：亢奋
- 65-79：偏暖
- 45-64：中性偏谨慎
- 30-44：偏冷
- 0-29：恐慌

## 快速开始

### 1. 演示模式

```bash
python a_share_sentiment.py --demo
```

### 2. 读取 JSON 输入

```bash
python a_share_sentiment.py --input-json sample_snapshot.json --output reports/latest.json
```

JSON 输入格式示例：

```json
{
  "trade_date": "2026-03-19",
  "total_turnover_billion": 24680,
  "sh_index_pct": 0.38,
  "sz_index_pct": -0.12,
  "cyb_index_pct": -0.45,
  "up_count": 1980,
  "down_count": 3080,
  "flat_count": 120,
  "limit_up_count": 62,
  "limit_down_count": 9,
  "northbound_net_billion": 18.6,
  "margin_balance_billion": 25880,
  "margin_balance_change_billion": -12.4,
  "defensive_leadership": true,
  "notes": "高成交、宽度偏弱、防御风格占优"
}
```

### 2.1 读取 CSV 输入

```bash
python a_share_sentiment.py --input-csv sample_snapshot.csv
```

CSV 表头需与 `MarketSnapshot` 字段一致，脚本默认读取最后一行作为最新交易日数据。

### 3. 自动抓取模式（akshare）

如需自动抓取 A 股行情，可先安装：

```bash
pip install akshare pandas
```

然后运行：

```bash
python a_share_sentiment.py --auto-fetch --output reports/auto.json
```

> 说明：自动抓取模式当前优先覆盖指数、成交额、上涨/下跌家数、涨停/跌停、北向等数据。两融与风格数据预留为可扩展项，实际落地时可以再接入交易所、券商或第三方数据源。

## 每日定时执行

例如每天 **15:10** 自动评估一次：

```bash
python a_share_sentiment.py --auto-fetch --schedule-at 15:10 --output reports/daily.json
```

如果你希望长期后台运行，可以配合系统任务调度：

### Linux crontab

```cron
10 15 * * 1-5 cd /workspace/CodeX && /usr/bin/python3 a_share_sentiment.py --auto-fetch --output reports/daily.json >> reports/daily.log 2>&1
```

### systemd timer / 容器编排

也可以由外部调度系统按天触发，本脚本只负责单次计算与输出。

## 可扩展建议

若你希望让这个情绪系统更接近实盘，可继续补充：

- 两融余额日频变化
- 北向资金分钟级收盘净流入
- 行业涨跌分布
- 连板高度与断板率
- ETF 资金净申购
- 情绪时间序列存储与可视化

