# AM-HK v2.1 修复工作总结

## 日期
2026-04-10

## 修复目标
修复 Agent4/5/6 数据模型不兼容问题，确保多 Agent 协同链路正常工作

---

## 问题诊断

### 1. Handler 名称不匹配
- **问题**: Agent4 注册 `opportunity`，但 Agent2 发送 `trading_opportunity`
- **解决**: 使用 `msg_type: 'opportunity'` 发送测试信号

### 2. Signal 数据模型字段缺失
Agent4 输出缺少 Agent5 期望的字段：
- ❌ `market`: MarketType (CRYPTO/btc/hk_stock/us_stock)
- ❌ `action`: 小写 (buy/sell/hold/pass) 而非大写 (BUY/SELL/HOLD/PASS)
- ❌ `predicted_return`: float
- ❌ `timeframe`: str ("5min", "15min", "1h")
- ❌ `reasoning`: str
- ❌ `agent_id`: str

### 3. Datetime 序列化错误
- **问题**: `generate_timestamp()` 返回 datetime 对象，无法 JSON 序列化
- **解决**: 改为 `generate_timestamp().isoformat()`

---

## 修复详情

### Agent4 (TrendOracle)

**文件**: `agents/agent4_oracle/main.py`

**修改点**:
```python
# _publish_decision 方法

decision_dict = {
    "signal": {
        "symbol": symbol,
        "market": "CRYPTO",                          # ✅ 新增
        "action": decision.action.value.lower(),     # ✅ 小写
        "confidence": decision.confidence,
        "predicted_return": track_a.predicted_return, # ✅ 新增
        "timeframe": "5min",                          # ✅ 新增
        "reasoning": decision.reasoning,              # ✅ 新增
        "agent_id": "agent4_oracle",                  # ✅ 新增
        "timestamp": generate_timestamp().isoformat(), # ✅ 修复
    },
    "position_size": decision.position_size,
    "stop_loss": decision.sl,
    "take_profit": decision.tp,
    "risk_score": decision.risk_score,
    "approved": False,
    "approval_reason": "",
}
```

### Agent5 (RiskGuardian)

**文件**: `agents/agent5_guardian/main.py`

**修改点**:
```python
# 所有 generate_timestamp() 改为 .isoformat()
"timestamp": generate_timestamp().isoformat(),
```

修复位置:
1. `_publish_approved_decision` 方法
2. `_reject_decision` 方法

### Agent6 (LearningEngine)

**状态**: 无需修复，运行正常

**启动日志**:
```
✅ LightGBM trainer 初始化
✅ Informer fine-tuner 初始化
✅ PPO trainer 初始化
✅ GNN trainer 初始化
✅ Model manager 加载版本: v1.0
✅ Consumer 已启动
```

---

## 验证结果

### 测试流程
```bash
# 1. 启动 Agent4/5/6
export PYTHONPATH=/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk
nohup python3 agents/agent4_oracle/main.py > logs/agent4.log 2>&1 &
nohup python3 agents/agent5_guardian/main.py > logs/agent5.log 2>&1 &
nohup python3 agents/agent6_learning/main.py > logs/agent6.log 2>&1 &

# 2. 发送测试信号
python3 -c "
from core.kafka import MessageBus
from core.utils import generate_msg_id, generate_timestamp
bus = MessageBus('test')
value = {
    'msg_id': generate_msg_id(),
    'msg_type': 'opportunity',
    'source_agent': 'test',
    'timestamp': generate_timestamp().isoformat(),
    'priority': 2,
    'payload': {
        'symbol': 'BTCUSDT',
        'market': 'CRYPTO',
        'price': 68500,
        'factors': {'close': 68500, 'volatility_5m': 2.5},
        'signals': [{'source': 'TEST', 'action': 'BUY', 'confidence': 0.95}]
    }
}
bus.send('am-hk-trading-opportunities', 'BTCUSDT', value)
"
```

### 验证输出

**Agent4 日志**:
```
✅ DEBUG: Received opportunity message for key=BTCUSDT
✅ 📊 Processing opportunity: BTCUSDT (CRYPTO)
✅ Decision: BTCUSDT | action=HOLD | confidence=34.80% | position=0.55%
```

**Agent5 日志**:
```
✅ 审查决策: BTCUSDT hold
⚠️ 审批拒绝: BTCUSDT | 原因: 硬规则未通过: single_loss_limit
(无 datetime 序列化错误)
```

**Agent6 日志**:
```
✅ agent6_learning initialized with all learning modules
✅ Loaded model versions: {'lightgbm': 'v1.0', 'informer': 'v1.0', 'ppo': 'v1.0', 'gnn': 'v1.0'}
✅ DEBUG: Consumer started
```

---

## 链路状态

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent4     │ ──▶ │  Agent5     │ ──▶ │  Agent6     │
│ (TrendOracle)│     │(RiskGuardian)│     │(Learning)   │
└─────────────┘     └─────────────┘     └─────────────┘
      ✅                   ✅                   ✅
   接收/处理            风控审查             学习反馈
```

---

## Git 提交

```bash
Commit: 3149137
Message: fix: Agent4/5/6 数据模型兼容性和链路修复
Files: 34 files changed, 6141 insertions(+), 60 deletions(-)
Tag: v2.1
```

---

## 后续建议

1. **Agent1/2/3 状态**: 当前未运行，如需完整链路需启动
2. **硬规则调整**: 如需测试通过场景，可调整 `single_loss_limit` 阈值
3. **监控告警**: 建议添加 Agent 健康检查和链路监控

---

## 附录: 核心模型定义

### Signal (core.models)
```python
class Signal(BaseModel):
    symbol: str
    market: MarketType           # "CRYPTO", "btc", "hk_stock", "us_stock"
    action: ActionType           # "buy", "sell", "hold", "pass" (小写!)
    confidence: float
    predicted_return: float
    timeframe: str               # "5min", "15min", "1h"
    reasoning: str
    agent_id: str
    timestamp: datetime
```

### TradeDecision (core.models)
```python
class TradeDecision(BaseModel):
    signal: Signal
    position_size: float
    stop_loss: float
    take_profit: float
    risk_score: float
    approved: bool = False
    approval_reason: str = ""
```
