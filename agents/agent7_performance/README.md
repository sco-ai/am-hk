# Agent 7: PerformanceAnalyzer - 绩效分析器

## 概述

Agent 7是AM-HK系统的绩效分析模块，负责交易结果分析、绩效报告生成和策略归因分析。它将分析结果通过Kafka广播给所有Agent，为Agent6的学习优化提供反馈数据。

## 职责

- **交易结果分析**: 接收并分析每笔交易的执行结果
- **绩效指标计算**: 计算收益率、夏普比率、最大回撤等核心指标
- **策略归因分析**: 分析各策略贡献度、因子暴露度、时间维度表现
- **风险分析**: 计算VaR、CVaR、波动率、尾部风险等
- **报告生成**: 自动生成日报/周报/月报
- **飞书推送**: 通过飞书卡片推送绩效报告

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 7: PerformanceAnalyzer              │
├─────────────────────────────────────────────────────────────┤
│  Input: am-hk-trade-results (交易执行结果)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Metrics    │  │ Attribution  │  │    Risk      │      │
│  │  Calculator  │  │  Analyzer    │  │  Analyzer    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐                        │
│  │   Report     │  │   Feishu     │                        │
│  │  Generator   │  │  Publisher   │                        │
│  └──────────────┘  └──────────────┘                        │
├─────────────────────────────────────────────────────────────┤
│  Output: am-hk-performance-reports (广播给所有Agent)        │
└─────────────────────────────────────────────────────────────┘
```

## 模块说明

### 1. MetricsCalculator - 绩效指标计算

计算以下核心指标：

| 指标 | 说明 | 公式 |
|------|------|------|
| 总收益率 | 整体收益表现 | 总收益 / 初始资金 |
| 夏普比率 | 风险调整后收益 | (收益率 - 无风险利率) / 波动率 |
| 最大回撤 | 最大跌幅 | 峰值到谷底的最大跌幅 |
| 胜率 | 盈利交易占比 | 盈利交易数 / 总交易数 |
| 盈亏比 | 平均盈亏比 | 平均盈利 / 平均亏损 |
| 索提诺比率 | 下行风险调整收益 | (收益率 - 无风险利率) / 下行标准差 |
| 卡尔马比率 | 回撤调整收益 | 年化收益 / 最大回撤 |

### 2. AttributionAnalyzer - 策略归因分析

分析维度：
- **策略贡献度**: 动量/价值/情绪/跨市场各策略的收益贡献
- **因子暴露度**: 各因子的收益相关性分析
- **时间维度**: 日/周/月表现，最佳/最差交易时段
- **市场环境**: 不同市场环境下的策略适应性

### 3. RiskAnalyzer - 风险分析

风险指标：
- **VaR (Value at Risk)**: 95%/99%置信水平下的最大预期损失
- **CVaR/ES**: 超过VaR阈值时的平均损失
- **波动率**: 年化标准差
- **尾部风险**: 偏度、峰度分析
- **集中度风险**: 赫芬达尔指数(HHI)
- **回撤分析**: 回撤期统计、恢复状态

### 4. ReportGenerator - 报告生成器

支持格式：
- JSON格式（Kafka消息）
- HTML格式（可视化展示）
- 文本格式（日志输出）

报告类型：
- 日报: 每日20:00自动生成
- 周报: 每周五20:00自动生成
- 月报: 每月1日20:00自动生成

### 5. FeishuPublisher - 飞书推送

功能：
- 交互式卡片消息
- 核心指标展示
- 策略归因表格
- 风险指标警示
- 优化建议列表

## 输入数据格式

### Kafka Topic: `am-hk-trade-results`

```json
{
  "msg_id": "uuid",
  "msg_type": "trade_result",
  "source_agent": "agent5_guardian",
  "timestamp": "2024-01-01T00:00:00Z",
  "payload": {
    "symbol": "BTC",
    "action": "buy",
    "strategy": "momentum",
    "entry_price": 50000,
    "exit_price": 51000,
    "quantity": 0.1,
    "pnl": 100,
    "pnl_pct": 0.02,
    "holding_time": 3600,
    "slippage": 0.001,
    "transaction_cost": 5,
    "factors": {
      "rsi": 65,
      "macd": 2.5
    },
    "market_condition": {
      "volatility": "medium",
      "trend": "up"
    }
  }
}
```

## 输出数据格式

### Kafka Topic: `am-hk-performance-reports`

```json
{
  "report_type": "daily",
  "timestamp": 1744082400000,
  "summary": {
    "total_return": 0.085,
    "sharpe_ratio": 1.42,
    "max_drawdown": -0.12,
    "win_rate": 0.62,
    "profit_loss_ratio": 1.8
  },
  "strategy_attribution": {
    "momentum": {"contribution": 0.035, "win_rate": 0.68},
    "value": {"contribution": 0.018, "win_rate": 0.55},
    "sentiment": {"contribution": 0.022, "win_rate": 0.60},
    "cross_market": {"contribution": 0.010, "win_rate": 0.58}
  },
  "risk_metrics": {
    "var_95": -0.025,
    "cvar_95": -0.035,
    "volatility": 0.18
  },
  "recommendations": [
    "增加动量策略权重(当前贡献最高)",
    "优化跨市场传导信号阈值"
  ]
}
```

## 配置参数

```python
# 初始资金配置
INITIAL_CAPITAL = 1_000_000  # 100万

# 无风险利率
RISK_FREE_RATE = 0.02  # 2%

# 报告生成时间
DAILY_REPORT_TIME = "20:00"      # 每日20:00
WEEKLY_REPORT_DAY = 5            # 周五
MONTHLY_REPORT_DAY = 1           # 每月1号

# 最小分析样本数
MIN_SAMPLES_FOR_ANALYSIS = 10

# 历史数据缓存
MAX_TRADE_HISTORY = 100_000
```

## 启动方式

### 单独启动

```bash
# 使用Python模块方式启动
python -m agents.agent7_performance.main

# 或使用示例脚本
python agents/agent7_performance/example.py
```

### 通过主程序启动

```bash
# 启动所有Agent（包括Agent7）
python main.py
```

## 测试

```bash
# 运行单元测试
python -m pytest agents/agent7_performance/test_agent7.py -v

# 运行特定测试
python -m pytest agents/agent7_performance/test_agent7.py::TestMetricsCalculator -v
```

## 接口说明

### PerformanceAnalyzer类

```python
class PerformanceAnalyzer:
    async def start(self)  # 启动分析器
    async def stop(self)   # 停止分析器
    
    # 内部方法
    def _on_trade_result(key, value, headers)  # 处理交易结果
    def _on_report_request(key, value, headers)  # 处理报告请求
    async def _generate_and_publish_report(report_type)  # 生成并发布报告
```

### 各分析模块接口

```python
# MetricsCalculator
metrics = calculator.calculate(trades, initial_capital, risk_free_rate)

# AttributionAnalyzer
attribution = analyzer.analyze(trades)

# RiskAnalyzer
risk_metrics = analyzer.analyze(trades)

# ReportGenerator
report = generator.generate(report_type, timestamp, metrics, attribution, risk_metrics, recommendations, trade_count)

# FeishuPublisher
await publisher.publish(report, chat_id)
```

## 与其他Agent的交互

```
Agent5 (RiskGuardian) → 交易结果 → Agent7 (PerformanceAnalyzer)
                                    ↓
                              绩效报告广播
                                    ↓
    ┌─────────────────┬─────────────────┬─────────────────┐
    ↓                 ↓                 ↓                 ↓
Agent1            Agent2            Agent3            Agent4
(Harvester)      (Curator)        (Scanner)         (Oracle)
    ↑                 ↑                 ↑                 ↑
    └─────────────────┴─────────────────┴─────────────────┘
                              ↓
                        Agent6 (LearningFeedback)
                        (使用绩效数据优化模型)
```

## 开发计划

- [x] 绩效指标计算模块
- [x] 策略归因分析模块
- [x] 风险分析模块 (VaR/CVaR)
- [x] 报告生成器 (日报/周报/月报)
- [x] 飞书卡片推送集成
- [ ] 可视化图表生成 (Matplotlib/Plotly)
- [ ] 数据库存储历史绩效
- [ ] 实时风险预警功能

## 文件结构

```
agents/agent7_performance/
├── __init__.py
├── main.py                      # 主入口
├── example.py                   # 使用示例
├── test_agent7.py               # 单元测试
└── modules/
    ├── __init__.py
    ├── metrics_calculator.py    # 绩效指标计算
    ├── attribution_analyzer.py  # 策略归因分析
    ├── risk_analyzer.py         # 风险分析
    ├── report_generator.py      # 报告生成器
    └── feishu_publisher.py      # 飞书推送
```

## 依赖

```
numpy>=1.24.0
scipy>=1.10.0
```

## 注意事项

1. **数据精度**: 所有百分比数据使用4位小数，比率使用2位小数
2. **性能优化**: 交易历史使用deque限制最大长度(10万条)
3. **错误处理**: 各模块对空数据有完善的降级处理
4. **时区处理**: 所有时间戳统一使用UTC时间
5. **内存管理**: 定期清理过期数据，防止内存泄漏

## License

Proprietary - AlphaMind HK
