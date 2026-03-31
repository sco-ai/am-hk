# Agent 规格说明书

## Agent1: MarketHarvester（采集层）

**职责**: 多市场数据接入（BTC + 港股 + 美股 + 新闻）

**模型**: ❌ 不用AI模型，✅ 规则 + 数据校验

**技术栈**:
- Binance WS / OKX WS
- 老虎证券 API
- NewsAPI / Twitter API

---

## Agent2: DataCurator（因子层）

**职责**: 30+机构级因子计算，多市场特征融合

**模型（在线）**:
| 类型 | 主模型 | 备选 |
|------|--------|------|
| 数据标准化 | 统计模型 | 无 |
| 异常检测 | Z-score | IsolationForest(API版) |

---

## Agent3: AlphaScanner（机会筛选）

**职责**: 多策略扫描，Top机会筛选

**模型（在线）**:
| 类型 | 主模型 | 备选 |
|------|--------|------|
| 因子评分 | LightGBM（云训练） | XGBoost |
| 策略优化 | OpenAI GPT-4.1 | DeepSeek Reasoner |

**大模型用途**:
- 阈值动态优化
- 策略权重调整

---

## Agent4: TrendOracle（核心决策层）⭐

**整个系统最核心模块**

**模型组合（全部在线）**:
| 模型类型 | 主模型 | 备选 |
|----------|--------|------|
| 时序预测 | Informer API | Autoformer |
| 趋势分解 | N-HiTS API | N-BEATS |
| 强化学习 | PPO（云训练） | A3C |
| AI决策 | GPT-4.1 | Anthropic Claude Sonnet |
| 多模态推理 | GPT-4.1 | DeepSeek V3 |

**功能拆解**:
1. 价格预测（未来 5min / 15min / 1h）
2. 交易决策（BUY / SELL / HOLD）
3. 仓位计算（Kelly + RL策略）
4. 解释输出（给飞书）

---

## Agent5: RiskGuardian（风控）

**职责**: 审批所有交易

**模型（在线）**:
| 类型 | 主模型 | 备选 |
|------|--------|------|
| 风控规则 | 参数化规则 | - |
| 异常检测 | Isolation Forest API | One-Class SVM |
| AI风控 | GPT-4.1 | Claude |

---

## Agent6: LearningFeedback（核心进化）⭐

**机构级系统最关键模块**

**模型组合**:
| 类型 | 主模型 | 备选 |
|------|--------|------|
| 策略优化 | GPT-4.1 | DeepSeek |
| 因子训练 | LightGBM 云训练 | XGBoost |
| RL训练 | PPO（Ray RLlib） | A3C |
| GNN | Temporal GNN（云GPU） | GAT |
| 情绪分析 | FinBERT API | GPT情绪分析 |

---
*归档时间: 2025-03-31*
