# 数据源对比与选择建议

## 1. 目标

针对量化回测框架的数据获取模块，当前优先考虑三类能力：

1. **开发/测试稳定性**：不依赖外部网络即可跑通回测
2. **本地研究效率**：支持 CSV 等本地文件快速回放
3. **在线扩展能力**：后续可切换到 A 股线上数据源

---

## 2. 当前对比的几类数据源

| 数据源 | 适用场景 | 优点 | 缺点 | 当前实现建议 |
| --- | --- | --- | --- | --- |
| `MockDataSource` | 单元测试、示例、策略验证 | 稳定、无外部依赖、速度快 | 不是真实数据 | **必须保留** |
| `CsvDataSource` | 本地研究、历史回测 | 易管理、易缓存、可复现 | 需要自行准备数据文件 | **优先落地** |
| `AShareDailyDataSource` | 轻量 A 股在线拉取 | 接入简单、适合快速验证 | 依赖公开接口稳定性 | **作为在线扩展** |
| `TushareDailyDataSource` | 更规范的 A 股研究流 | 数据字段体系较标准 | 需要 token，接口依赖外部服务 | **作为正式接入候选** |
| `FallbackDataSource` | 本地缓存 + 在线补齐 | 优先命中本地，缺失时再降级 | 需要组合配置 | **建议用于生产前过渡** |

---

## 3. 当前选择策略

当前仓库采用下面这套组合：

### 第一优先级：`MockDataSource`

用于：

- 单元测试
- 示例脚本
- 策略开发初期验证

原因：

- 最稳定
- 不受网络影响
- 能保证 CI 可重复

### 第二优先级：`CsvDataSource`

用于：

- 本地历史回测
- 多次重复实验
- 回测结果复现

原因：

- 比在线接口更适合研究环境
- 数据可缓存、可清洗、可版本化
- 与回测框架耦合最小

### 第三优先级：在线数据源

当前先实现：

- `AShareDailyDataSource`
- `TushareDailyDataSource`

原因：

- 给后续真实接入预留路径
- 方便从 mock / csv 过渡到线上数据

---

## 4. 已落地能力

当前数据模块已经支持：

- `MockDataSource`
- `CsvDataSource`
- `AShareDailyDataSource`
- `TushareDailyDataSource`
- `FallbackDataSource`
- `DataSourceFactory`

这意味着现在可以通过统一接口切换数据来源，而不需要改策略层和回测层代码。

---

## 5. 下一步建议

1. 为 `CsvDataSource` 增加字段映射配置
2. 增加本地缓存与下载同步命令
3. 给 `TushareDailyDataSource` 增加更多接口（如复权、指数、日历）
4. 增加多数据源 fallback / merge 能力


## 6. 联调建议

建议优先验证下面两类联调路径：

1. `CsvDataSource -> DataRepository -> Strategy -> BacktestEngine`
2. `TushareDailyDataSource (mock response) -> DataRepository -> Strategy -> BacktestEngine`

这样可以同时验证：数据解析、仓位生成、执行落地、结果沉淀是否按预期执行。
