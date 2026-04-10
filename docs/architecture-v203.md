# AM-HK v2.03 系统架构流程图

```mermaid
graph TB
    subgraph Layer0["Layer0: 基础设施"]
        K[Kafka<br/>消息总线]
        R[Redis<br/>缓存/状态]
        P[(PostgreSQL<br/>历史数据)]
    end

    subgraph Layer1["Layer1: 数据采集"]
        A1[Agent1 Harvester<br/>币安API]
        A1_1[BTC/ETH/SOL<br/>XRP/DOGE]
        A1_2[K线/订单簿<br/>资金费率/持仓]
        News[NewsAPI<br/>新闻采集]
    end

    subgraph Layer2["Layer2: 因子计算 ⭐新增"]
        A2[Agent2 Curator]
        F1[trend_factors<br/>MA/MACD/动量]
        F2[volatility_factors<br/>ATR/布林带]
        F3[liquidity_factors<br/>订单簿深度]
        F4[crypto_factors ⭐<br/>持仓量/多空比<br/>资金费率趋势]
    end

    subgraph Layer3["Layer3: 决策层 ⭐增强"]
        A3[Agent3 Scanner]
        MS[Market State<br/>Bull/Bear/Range]
        VR[Volatility Regime<br/>5档波动率]
        
        subgraph Models["多模型竞争池 ⭐"]
            M1[LightGBM<br/>主力模型]
            M2[XGBoost<br/>备选模型]
            M3[PPO RL<br/>仓位控制]
            M4[Rule-Based<br/>趋势跟踪]
        end
        
        EN[Ensemble<br/>自适应权重融合]
    end

    subgraph Layer4["Layer4: 风控与组合 ⭐新增"]
        A4[Agent4 Oracle]
        RM[Risk Manager<br/>VaR/回撤/敞口]
        PS[Position Sizer<br/>凯利公式+风控]
        SL[Stop Loss<br/>固定/跟踪/ATR]
        PM[Portfolio Manager<br/>Top5 50%/Top6-10 30%]
    end

    subgraph Layer5["Layer5: 执行层"]
        A5[Agent5 Guardian<br/>模拟执行]
        Paper[Paper Trading<br/>验证策略]
    end

    subgraph Layer6["Layer6: 学习进化 ⭐"]
        A6[Agent6 Learning]
        AW[Adaptive Weights<br/>模型表现驱动]
        FE[Factor Evolution<br/>因子有效性]
    end

    subgraph Layer7["Layer7: 监控运营"]
        Dash[Dashboard<br/>WebSocket实时]
        Feishu[飞书通知<br/>交易/异常]
        Log[日志系统<br/>决策追踪]
    end

    %% 数据流
    A1 -->|raw-data| K
    A1_1 --> A1
    A1_2 --> A1
    News --> A1
    
    K -->|消费| A2
    A2 -->|调用| F1
    A2 -->|调用| F2
    A2 -->|调用| F3
    A2 -->|调用| F4
    F1 -->|factors| P
    F2 -->|factors| P
    F3 -->|factors| P
    F4 -->|factors| P
    A2 -->|processed-data| K
    
    K -->|消费| A3
    A3 -->|检测| MS
    A3 -->|检测| VR
    MS -->|状态| EN
    VR -->|状态| EN
    
    M1 -->|预测| EN
    M2 -->|预测| EN
    M3 -->|仓位| EN
    M4 -->|信号| EN
    
    EN -->|综合评分| K
    K -->|trading-opportunities| A4
    
    A4 -->|风控检查| RM
    A4 -->|仓位计算| PS
    A4 -->|止损设置| SL
    A4 -->|组合优化| PM
    RM -->|通过| A5
    PS -->|通过| A5
    SL -->|通过| A5
    
    A5 -->|模拟成交| Paper
    A5 -->|trading-decisions| K
    
    K -->|消费| A6
    A6 -->|权重调整| AW
    A6 -->|因子筛选| FE
    AW -->|更新| M1
    AW -->|更新| M2
    FE -->|反馈| F4
    
    K -->|实时推送| Dash
    K -->|告警| Feishu
    A4 -->|记录| Log
    A5 -->|记录| Log
    
    R -.->|缓存模型状态| A3
    R -.->|缓存市场状态| MS
    P -.->|历史训练| M1
    P -.->|历史训练| M2

    style Layer2 fill:#e1f5fe
    style Layer3 fill:#fff3e0
    style Layer4 fill:#e8f5e9
    style Layer6 fill:#fce4ec
    style F4 fill:#ffccbc
    style Models fill:#ffe0b2
    style EN fill:#ffcc80
```

## 核心数据流

```
币安API → Agent1 → raw-data(Kafka) → Agent2 → processed-data(Kafka) 
                                                              ↓
[因子库: 趋势/波动/流动性/Crypto特有] → PostgreSQL (历史存储)
                                                              ↓
Agent3 ← Market State + Volatility Regime (市场状态检测)
                                                              ↓
[多模型池: LGBM/XGB/RL/规则] → Ensemble (自适应权重融合)
                                                              ↓
trading-opportunities(Kafka) → Agent4 (风控检查)
                                                              ↓
[Risk Manager + Position Sizer + Stop Loss + Portfolio Manager]
                                                              ↓
通过 → Agent5 (模拟执行/Paper Trading)
                                                              ↓
trading-decisions(Kafka) → Agent6 (学习进化/权重调整)
                                                              ↓
反馈 → 模型权重更新 + 因子有效性评估
```

## 关键决策点

| 阶段 | 决策内容 | 模块 |
|------|---------|------|
| 数据采集 | 币种选择、周期配置 | Agent1 |
| 因子计算 | 30+ 技术指标实时计算 | Agent2 Factors |
| 市场状态 | Bull/Bear/Range 判断 | Market State Engine |
| 模型预测 | 4模型并行预测 | Model Pool |
| 权重融合 | 动态权重 = f(市场状态, 历史表现) | Ensemble |
| 风控检查 | VaR、回撤、敞口限制 | Risk Manager |
| 仓位计算 | 凯利公式 + 风险调整 | Position Sizer |
| 止损管理 | 固定/跟踪/ATR/时间 | Stop Loss |
| 组合优化 | Top5 50% + Top6-10 30% | Portfolio Manager |
| 学习进化 | 权重自适应调整 | Agent6 Learning |

## 新增/增强模块 (v2.03)

### 🆕 新增
- `crypto_factors.py` - Crypto特有因子（持仓量、多空比、爆仓风险）
- `rl_model.py` - PPO强化学习仓位控制
- `ensemble.py` - 多模型自适应权重融合
- `market_state.py` - 市场状态检测引擎
- `volatility_regime.py` - 5档波动率状态
- `adaptive_weights.py` - 自适应权重调整
- `position_sizer.py` - 凯利公式仓位管理
- `stop_loss.py` - 多类型止损管理
- `risk_manager.py` - 组合级风控系统

### ⭐ 增强
- Agent2: 30+ 因子（原基础 → 趋势/波动/流动性/Crypto）
- Agent3: 单模型 → 4模型竞争池 + 自适应融合
- Agent4: 新增完整风控链路
- Agent6: 新增学习进化能力

## 技术栈

```
数据采集: 币安 REST API
消息队列: Kafka (14 topics)
缓存系统: Redis
数据存储: PostgreSQL + TimescaleDB
机器学习: LightGBM, XGBoost, RLlib (PPO)
实时推理: 本地模型，<10ms延迟
风控引擎: 自定义实现 (VaR, CVaR)
监控系统: 飞书通知 + WebSocket Dashboard
```
