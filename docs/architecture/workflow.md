# 完整工作流程（实盘）

## 每分钟循环

```
1. Agent1 → 采集 BTC / 美股 / 港股 / 新闻
2. Agent2 → 因子计算（30+）
3. Agent3 → 筛选 Top3机会
4. Agent4 →
   - 时间序列预测
   - RL决策
   - GPT生成交易指令
5. Agent5 → 风控审批
6. 执行交易（老虎证券 / Binance）
7. Agent6 → 记录并学习
```

## 流程说明

| 步骤 | Agent | 动作 | 输出 |
|------|-------|------|------|
| 1 | MarketHarvester | 数据采集 | 原始数据流 |
| 2 | DataCurator | 因子计算 | 30+ 因子 |
| 3 | AlphaScanner | 机会筛选 | Top3 机会 |
| 4 | TrendOracle | 决策生成 | 交易指令 |
| 5 | RiskGuardian | 风控审批 | 通过/拒绝 |
| 6 | Execution | 执行交易 | 成交回报 |
| 7 | LearningFeedback | 记录学习 | 策略优化 |

---
*归档时间: 2025-03-31*
