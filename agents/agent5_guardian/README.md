# Agent 5: RiskGuardian (风控守卫者)

## 概述

RiskGuardian是AlphaMind HK系统的三层风控审批中心，负责对所有交易决策进行全面的风险评估和审批。

## 架构设计

### 三层风控体系

```
┌─────────────────────────────────────────────────────────────────┐
│                     RiskGuardian (Agent 5)                       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Hard Rules (硬规则层)                                  │
│  ├── 单日最大亏损 ≤ 账户2%                                       │
│  ├── 单笔最大亏损 ≤ 账户0.5%                                     │
│  ├── 最大持仓数 ≤ 10只                                           │
│  ├── 杠杆上限: 2x                                                │
│  └── 财报前30分钟禁止交易                                        │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Dynamic Rules (动态规则层)                             │
│  ├── 高波动环境: 仓位限制50%, 止损收紧20%                        │
│  ├── 强趋势环境: 仓位限制100%, 止损放宽10%                       │
│  └── 震荡环境: 仓位限制30%, 止损收紧30%                          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Anomaly Detection (异常检测层)                         │
│  ├── 模型: Isolation Forest                                      │
│  ├── 检测: 价格异常跳变、成交量异常、因子异常                     │
│  └── 特征: 8维特征向量 (价格变化率、成交量激增等)                │
└─────────────────────────────────────────────────────────────────┘
```

## 输入/输出

### 输入 Topic
- `am-hk-trading-decisions`: 从Agent 4 (TrendOracle) 接收交易决策

### 输出 Topic
- `am-hk-risk-approved-trades`: 审批通过的交易
- `am-hk-feedback`: 拒绝的交易（发送到Agent 6学习反馈）

## 输出格式

```json
{
  "symbol": "00700.HK",
  "original_decision": "BUY",
  "risk_status": "APPROVED",
  "risk_score": 0.92,
  "approved_position": 0.10,
  "adjusted_sl": 64200,
  "adjusted_tp": 66500,
  "risk_checks": {
    "hard_rules": "PASS",
    "dynamic_rules": "PASS",
    "anomaly_detection": "PASS"
  },
  "warnings": [],
  "details": {
    "hard_rules": [...],
    "dynamic_rules": [...],
    "anomaly_score": 0.15
  }
}
```

## 审批逻辑

### 1. 硬规则层 (Layer 1)

硬规则是绝对限制，**任何一条未通过直接拒绝交易**。

| 规则 | 限制值 | 说明 |
|------|--------|------|
| 单日最大亏损 | ≤ 2% | 累计当日亏损 |
| 单笔最大亏损 | ≤ 0.5% | 仓位 × 止损幅度 |
| 最大持仓数 | ≤ 10 | 同时持仓数量 |
| 杠杆上限 | ≤ 2x | 仓位比例 |
| 财报黑名单 | 30分钟 | 财报发布前禁止 |

### 2. 动态规则层 (Layer 2)

根据市场环境自适应调整参数。

| 市场环境 | 判定条件 | 仓位限制 | 止损调整 | 止盈调整 |
|----------|----------|----------|----------|----------|
| 高波动 | vol_ratio > 1.5 | 50% | 收紧20% | 收紧10% |
| 强趋势 | ADX > 40 | 100% | 放宽10% | 放宽10% |
| 震荡 | ADX < 20 | 30% | 收紧30% | 收紧20% |
| 正常 | 其他 | 100% | 不变 | 不变 |

### 3. 异常检测层 (Layer 3)

使用 Isolation Forest 检测异常交易模式。

**特征向量 (8维):**
1. `price_change_rate` - 价格变化率
2. `volume_surge` - 成交量激增
3. `volatility_spike` - 波动率跳升
4. `rsi_deviation` - RSI偏离
5. `macd_anomaly` - MACD异常
6. `spread_anomaly` - 价差异常
7. `momentum_divergence` - 动量背离
8. `factor_zscore` - 因子Z分数

## 风险评分计算

```
risk_score = hard_score × 0.4 + anomaly_score × 0.4 + confidence × 0.2
```

- 风险评分范围: 0.0 - 1.0
- 越高表示风险越低
- 建议阈值: risk_score > 0.7 视为低风险

## 运行方式

```bash
# 独立运行
cd am-hk
python -m agents.agent5_guardian.main

# 作为系统一部分运行
python main.py
```

## 测试

```bash
# 运行单元测试
python tests/test_agent5.py
```

## 配置参数

可通过环境变量或配置文件调整:

```python
# 硬规则参数
MAX_DAILY_LOSS_PCT = 0.02
MAX_SINGLE_LOSS_PCT = 0.005
MAX_POSITIONS = 10
MAX_LEVERAGE = 2.0

# 异常检测参数
ANOMALY_CONTAMINATION = 0.05  # 预期异常比例
ISOLATION_FOREST_ESTIMATORS = 100
```

## 监控指标

- `total_reviewed`: 总审查数量
- `approved`: 通过数量
- `rejected`: 拒绝数量
- `modified`: 参数调整数量
- 各Layer的检查通过率

## 注意事项

1. **硬规则不可逾越** - 任何硬规则未通过直接拒绝
2. **动态规则允许调整** - 不直接拒绝，而是调整参数
3. **异常检测冷启动** - 需要100条历史数据才能训练Isolation Forest
4. **财报日历管理** - 需要外部输入财报时间数据

## 依赖

```
sklearn>=1.3.2
numpy>=1.26.2
pandas>=2.1.4
```
