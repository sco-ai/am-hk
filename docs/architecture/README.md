# AM-HK v3.0 系统方案归档

## 归档清单

### 系统架构文档

| 文档 | 说明 |
|------|------|
| [system-overview.md](./system-overview.md) | 系统核心架构总览 |
| [agent-specs.md](./agent-specs.md) | 6 Agent 详细规格 |
| [ai-capabilities.md](./ai-capabilities.md) | 四大AI能力融合 |
| [trading-logic.md](./trading-logic.md) | 多市场联动交易逻辑 |
| [workflow.md](./workflow.md) | 完整工作流程 |
| [feishu-integration.md](./feishu-integration.md) | 飞书生态融合 |
| [deployment.md](./deployment.md) | 部署架构 |

## 核心原则

- ✅ 全部 Agent 不使用本地模型（RTX4090仅用于计算/缓存/数据）
- ✅ 全部采用 线上大模型 / API（可商用、可扩展）
- ✅ 多模型融合：时间序列 + 强化学习 + GNN + NLP
- ✅ 多市场联动：BTC + 美股 + 港股

## 系统定位

🎯 **私募量化基金级别**（中高频AI交易系统）

---
*归档时间: 2025-03-31*
*版本: AM-HK v3.0（全在线模型 · 机构级生产版）*
