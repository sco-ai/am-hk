# Agent 4: TrendOracle (决策层)

## 概述

TrendOracle是AM-HK交易系统的核心决策层，采用**双轨AI决策架构**：

- **Track A (80%权重)**: 时间序列预测模型 (Informer/Autoformer + N-HiTS)
- **Track B (20%权重)**: 大模型推理 (Qwen2.5 + Kimi备选)
- **NLP情绪分析**: FinBERT并行输入 (Twitter/新闻)

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent 4: TrendOracle                      │
├─────────────────────────────────────────────────────────────┤
│  Input: am-hk-trading-opportunities (from Agent3)           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │    Track A (80%)    │    │    Track B (20%)    │        │
│  │  时间序列预测        │    │   大模型推理        │        │
│  ├─────────────────────┤    ├─────────────────────┤        │
│  │ • Informer/Auto     │    │ • Qwen2.5 (主)      │        │
│  │ • N-HiTS (辅)       │    │ • Kimi (备选)       │        │
│  └──────────┬──────────┘    └──────────┬──────────┘        │
│             │                          │                   │
│             └──────────┬───────────────┘                   │
│                        ▼                                    │
│            ┌─────────────────────┐                         │
│            │    双轨融合决策      │                         │
│            │  0.8×A + 0.2×B      │                         │
│            └──────────┬──────────┘                         │
│                       ▼                                     │
│            ┌─────────────────────┐                         │
│            │   FinBERT情绪分析    │                         │
│            │   (并行输入)         │                         │
│            └──────────┬──────────┘                         │
│                       ▼                                     │
│            ┌─────────────────────┐                         │
│            │   风险计算模块       │                         │
│            │ • 止盈止损计算       │                         │
│            │ • Kelly仓位建议      │                         │
│            └──────────┬──────────┘                         │
│                       ▼                                     │
│  Output: am-hk-trading-decisions                            │
└─────────────────────────────────────────────────────────────┘
```

## 输出格式

```json
{
  "action": "BUY",
  "confidence": 0.82,
  "entry": {
    "price": 65800,
    "time": 1744082400000
  },
  "tp": 66200,
  "sl": 64500,
  "position_size": 0.15,
  "reasoning": "Informer预测上涨+3.2%, Qwen确认趋势",
  "track_a_score": 0.85,
  "track_b_score": 0.75,
  "sentiment_score": 0.68
}
```

## 核心组件

### 1. InformerAutoformerClient
时间序列预测主模型封装
- API调用Informer/Autoformer
- Fallback: 基于动量的简单预测

### 2. NHITSClient
N-HiTS趋势分解模型
- 趋势分解和波动分析
- Fallback: 线性趋势拟合

### 3. QwenClient
Qwen2.5大模型客户端 (Track B主模型)
- 交易分析和决策推理
- JSON格式输出解析

### 4. KimiClient
Kimi大模型客户端 (Qwen备选)
- 当Qwen置信度低时自动切换

### 5. FinBERTClient
情绪分析客户端
- Twitter/新闻情绪分析
- 5分钟缓存机制

### 6. RiskCalculator
风险计算模块
- **止盈止损**: 基于ATR或波动率，盈亏比2:1
- **仓位计算**: Kelly公式 + 风险调整

## 双轨融合逻辑

```python
# 加权融合 (0.8*TrackA + 0.2*TrackB)
fused_confidence = track_a_conf * 0.8 + track_b_conf * 0.2

# 情绪调整
sentiment_boost = sentiment_score * 0.1

# 低置信度过滤
if fused_confidence < 0.5:
    action = HOLD
```

## 配置

在`.env`文件中添加：

```bash
# Qwen2.5 API
QWEN_API_KEY=your_qwen_api_key
QWEN_API_URL=https://api.openai.com/v1  # 兼容格式

# Kimi API (备选)
KIMI_API_KEY=your_kimi_api_key
KIMI_API_URL=https://api.moonshot.cn/v1

# Informer/Autoformer API
INFORMER_API_URL=https://api.informer.example.com
INFORMER_API_KEY=your_key

# N-HiTS API
NHITS_API_URL=https://api.nhits.example.com
NHITS_API_KEY=your_key

# FinBERT API
FINBERT_API_URL=https://api.finbert.example.com
FINBERT_API_KEY=your_key
```

## Kafka Topics

- **Input**: `am-hk-trading-opportunities` (来自Agent3)
- **Output**: `am-hk-trading-decisions` (发送给Agent5风控)

## 运行测试

```bash
cd /home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk
python3 -m pytest tests/test_agent4_oracle.py -v
```

## 依赖

- httpx: HTTP客户端
- numpy: 数值计算
- pydantic: 数据验证

## 日志

日志标识: `agent4_oracle`

关键日志：
- `📊 Processing opportunity`: 开始处理交易机会
- `✅ Decision`: 决策生成成功
- `❌ Error`: 处理错误
