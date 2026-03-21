# Python 量化回测框架（最小可演进版本）

这是一个面向研究和演进的 **Python 量化回测框架最小实现**。

它的目标不是一开始做成“大而全平台”，而是先把下面四件事做扎实：

1. **数据访问**：对上层统一暴露标准化行情对象。
2. **策略表达**：把信号、仓位、风控拆成可组合模块。
3. **执行仿真**：订单、成交、账户、持仓解耦建模。
4. **回测编排**：把数据、策略、执行串成可运行闭环。

当前仓库已经提供：

- 基础量化框架代码 `quant/`
- 一套“**放量上涨 -> 缩量回踩 -> 启动买入**”示例策略
- 一个可直接运行的 mock 回测示例
- SVG/HTML 可视化报告输出
- 基于 `pytest` 的自动化测试

---

## 1. 项目结构

```text
.
├── docs/
│   └── architecture.md          # 架构设计说明
├── examples/
│   └── run_volume_pullback_backtest.py
├── quant/
│   ├── backtest/
│   ├── common/
│   ├── data/
│   ├── execution/
│   └── strategy/
├── tests/
│   └── test_quant_framework.py
├── pyproject.toml
└── README.md
```

---

## 2. 核心模块说明

### 2.1 数据层 `quant.data`

负责提供统一标准化的行情数据接口：

- `DataSource`：数据源抽象接口
- `MockDataSource` / `InMemoryDataSource`：用于测试与示例
- `AShareDailyDataSource`：A 股日线数据源实现
- `DataRepository`：统一数据访问门面
- `Bar`：标准 K 线结构

> 当前建议在开发和测试阶段优先使用 `MockDataSource`，将网络和外部依赖隔离出去。

### 2.2 策略层 `quant.strategy`

负责生成交易意图，而不是直接改账户：

- `SignalModel`：信号模型抽象
- `MovingAverageCrossSignalModel`：均线信号示例
- `VolumePullbackBreakoutSignalModel`：放量上涨-缩量回踩-启动买入策略
- `FixedSizePositionSizer`：固定数量仓位模型
- `RiskRuleChain`：风控规则链
- `Strategy`：策略聚合门面

### 2.3 执行层 `quant.execution`

负责把“交易意图”落到账户：

- `OrderRequest` / `Order` / `Fill`
- `Position` / `Account`
- `SimulatedBroker`
- `CommissionModel` / `SlippageModel` / `ExecutionPolicy`

### 2.4 回测层 `quant.backtest`

负责编排主流程并产出结果：

- `Scheduler`
- `BacktestEngine`
- `BacktestResult`
- `Analyzer`
- `BacktestVisualizer`

---

## 3. 当前支持的回测链路

当前已经可以跑通下面这条主链路：

```text
MockDataSource -> DataRepository -> Strategy -> Broker -> BacktestEngine -> Analyzer -> Visualizer
```

也就是：

```text
数据 -> 信号 -> 仓位 -> 风控 -> 执行 -> 账户更新 -> 结果分析 -> 可视化报告
```

---

## 4. 快速开始

### 4.1 安装依赖

本项目目前依赖非常轻，直接使用本地 Python 环境即可：

```bash
python -m pip install -U pip pytest
```

### 4.2 运行测试

```bash
pytest -q
```

### 4.3 运行示例回测

```bash
python examples/run_volume_pullback_backtest.py
```

运行后会输出：

- 回测分析指标 `analysis`
- 成交结果 `fills`
- HTML 报告路径
- SVG 净值图路径

默认生成目录：

```text
artifacts/
├── volume_pullback_report.html
└── volume_pullback_report_equity.svg
```

---

## 5. 示例策略说明

内置示例策略是：

### **放量上涨 -> 缩量回踩 -> 启动买入**

大致逻辑：

1. 先识别一个 **放量上涨 breakout bar**
2. 随后出现 **缩量回踩 pullback 段**
3. 当价格重新向上突破且量能恢复时，给出 `LONG`
4. 若持仓后跌破容忍阈值，可给出 `EXIT`

该策略目前主要用于：

- 验证策略层抽象是否可运行
- 验证回测引擎、执行引擎、可视化是否闭环
- 给后续替换成真实策略提供模板

---

## 6. 可视化能力

当前已经实现两类结果展示：

### 6.1 SVG 图片

`BacktestVisualizer.render_equity_svg(...)`

输出净值曲线 SVG，可用于：

- 文档嵌入
- 报告生成
- CI 产物保存

### 6.2 HTML 报告

`BacktestVisualizer.save_report(...)`

输出一个自包含 HTML 报告，内容包括：

- 指标卡片（收益、回撤、交易次数等）
- 净值曲线
- 成交表格

这适合本地查看，也适合后续扩展成更完整的交互式回测界面。

---

## 7. 测试覆盖范围

当前测试主要覆盖：

- mock 数据源与数据仓库
- A 股数据源解析（使用 mock 响应）
- 均线信号模型
- 放量回踩策略信号模型
- 仓位模型和风控链
- Broker / Account / Position / Fill
- 回测引擎端到端流程
- 可视化报告输出
- 示例脚本 `run_demo()`

---

## 8. 当前限制

这个仓库目前是 **MVP 版本**，还没有做下面这些增强：

- 多标的统一组合管理
- 更复杂的成交规则（如 next open / VWAP / 成交量约束）
- 更完整的绩效分析（Sharpe、Calmar、胜率、换手率等）
- 参数搜索 / 批量回测
- Web UI
- 实盘接入

另外，A 股在线数据抓取逻辑虽然已经实现，但在测试中仍建议通过 mock 来保证稳定性。

---

## 9. 后续建议演进方向

如果你准备把这个框架继续往前推进，建议优先做：

1. **本地缓存层**：CSV / Parquet
2. **更完整的 Analyzer**：收益风险指标体系
3. **策略参数化**：统一配置输入
4. **组合回测**：多标的、多策略
5. **结果展示升级**：更强的交互式页面或 notebook 组件

---

## 10. 一句话总结

这套框架现在适合做的事情是：

> 用最少但清晰的模块，把“数据、策略、执行、回测、可视化”先跑通，然后再逐步演进。
