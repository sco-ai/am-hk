# AM-HK 跨市场信号引擎 - 完整逻辑文档

## 一、系统定位

**核心目标**: 用 Crypto → 美股 → 港股 的信息传导，自动生成每日港股短线交易池（Top10/Top20）

**系统性质**: 跨市场联动量化交易系统（机构级）

---

## 二、三层信号体系架构

### 2.1 信号流向

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Crypto 先行信号 (Lead Signal)                         │
│  ├─ BTCUSDT (比特币) → 风险总开关                               │
│  ├─ ETHUSDT (以太坊) → 科技/生态偏好                            │
│  └─ DOGEUSDT (狗狗币) → 散户情绪                                │
│                        ↓                                        │
│  输出: crypto_trend_score, crypto_momentum, crypto_sentiment    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                              │ (传导滞后: ~60秒)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: 美股确认信号 (Confirmation)                           │
│  ├─ COIN (Coinbase) → 加密链确认                                │
│  ├─ MARA (Marathon Digital) → 挖矿确认                          │
│  ├─ NVDA (NVIDIA) → 科技核心                                    │
│  ├─ TSLA (Tesla) → 科技/情绪                                    │
│  ├─ QQQ (纳指ETF) → 大盘方向                                    │
│  └─ SPY (标普ETF) → 整体市场                                    │
│                        ↓                                        │
│  输出: us_trend_score, sector_strength, risk_on_off             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                              │ (传导滞后: ~5分钟)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: 港股执行信号 (Execution)                              │
│  ├─ 00700 (腾讯) ← NVDA/QQQ                                     │
│  ├─ 09988 (阿里) ← QQQ/中概情绪                                 │
│  ├─ 03690 (美团) ← TSLA/本地生活                                │
│  ├─ 00863 (OSL) ← BTC/COIN (加密映射)                           │
│  └─ ... (50只流动性池)                                          │
│                        ↓                                        │
│  输出: 交易池 Top10/Top20 + 方向 + 强度                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、信号计算逻辑

### 3.1 Layer 1 - Crypto 先行信号

**输入数据**:
- BTCUSDT 5m/15m/1h K线
- ETHUSDT 5m/15m/1h K线  
- DOGEUSDT 5m/15m/1h K线
- 资金费率、持仓量、多空比

**计算指标**:

```python
# 趋势分数 (-1.0 ~ 1.0)
crypto_trend_score = (
    0.5 * btc_trend_5m +
    0.3 * btc_trend_15m +
    0.2 * btc_trend_1h
)

# 动量分数 (基于5分钟涨跌幅)
crypto_momentum = btc_change_5m * 100  # 百分比

# 情绪分数 (综合多空比、资金费率)
crypto_sentiment = (
    0.4 * long_short_ratio_score +
    0.3 * funding_rate_score +
    0.3 * volume_surge_score
)
```

**判定逻辑**:

| 条件 | 信号强度 | 风险偏好 |
|------|----------|----------|
| BTC 5m 动量 > +1% | 强 | 高 |
| BTC 5m 动量 0~1% | 中 | 中 |
| BTC 5m 动量 < 0% | 弱/空 | 低 |
| ETH > BTC 涨幅 | 科技偏好↑ | - |
| DOGE 暴涨 (>5%) | 散户情绪极强 | 警惕 |

---

### 3.2 Layer 2 - 美股确认信号

**输入数据**:
- COIN/MARA 盘前/盘中数据
- NVDA/TSLA 实时行情
- QQQ/SPY ETF 资金流
- 期权数据 (Put/Call Ratio)

**计算指标**:

```python
# 美股趋势分数
us_trend_score = (
    0.3 * coin_momentum +
    0.2 * mara_momentum +
    0.3 * nvda_momentum +
    0.2 * qqq_momentum
)

# 板块强度
sector_strength = {
    "crypto": (coin_momentum + mara_momentum) / 2,
    "tech": (nvda_momentum + tsla_momentum) / 2,
    "market": qqq_momentum
}

# 风险开关 (Risk On/Off)
risk_on_off = 1.0 if (crypto_trend_score > 0.3 and us_trend_score > 0.2) else -1.0
```

**确认逻辑**:

| Layer1 | Layer2 | 确认结果 | 操作建议 |
|--------|--------|----------|----------|
| BTC ↑ | COIN ↑ + QQQ ↑ | ✅ 强确认 | 可重仓 |
| BTC ↑ | COIN ↑ + QQQ → | ⚠️ 部分确认 | 中等仓位 |
| BTC ↑ | COIN → + QQQ → | ❌ 无确认 | 降低仓位/观望 |
| BTC ↓ | COIN ↓ + QQQ ↓ | ✅ 强确认空 | 清仓/做空 |

---

### 3.3 Layer 3 - 港股映射与执行

**映射规则**:

#### 规则1: Crypto → 港股

| Crypto 信号 | 港股标的 | 映射逻辑 |
|-------------|----------|----------|
| BTC ↑↑ | OSL(0863) | 加密资产标的 |
| BTC ↑ | 联想(02211) | 矿机/硬件 |
| ETH ↑ | Web3概念股 | 生态相关 |

#### 规则2: 美股科技 → 港股科技

| 美股 | 港股 | 映射系数 |
|------|------|----------|
| NVDA ↑ | 腾讯(00700) | 0.35 |
| QQQ ↑ | 阿里(09988) | 0.40 |
| TSLA ↑ | 美团(03690) | 0.30 |
| COIN ↑ | OSL(0863) | 0.42 |

#### 规则3: 风险情绪 → Beta选择

| 风险情绪 | 选股策略 |
|----------|----------|
| 风险偏好 ↑ | 中小盘科技股、高Beta |
| 风险偏好 ↓ | 大盘股、防御性板块 |
| 风险关闭 | 清仓或持仓现金 |

---

## 四、跨市场信号融合模型

### 4.1 最终评分公式

```python
Final Score = (
    0.4 × crypto_signal +          # Layer1 权重
    0.4 × us_signal +              # Layer2 权重
    0.2 × hk_local_signal          # Layer3 本地因子
)

其中:
- crypto_signal = layer1_signal (来自BTC/ETH)
- us_signal = layer2_confirm (来自COIN/NVDA/QQQ)
- hk_local_signal = 北水强度 + 主力资金 + 个股技术形态
```

### 4.2 输出结构

```python
{
    "symbol": "00700",
    "direction": "BUY",           # BUY / SELL / HOLD
    "confidence": 0.78,            # 0~1 置信度
    "strength": "强",              # 强/中/弱
    "layer1_contrib": 0.32,        # Layer1贡献 (0.4 × 0.8)
    "layer2_contrib": 0.28,        # Layer2贡献 (0.4 × 0.7)
    "layer3_contrib": 0.18,        # Layer3贡献 (0.2 × 0.9)
    "risk_level": "中",            # 高/中/低
    "position_size": 0.15,         # 建议仓位 (15%)
}
```

---

## 五、港股池生成逻辑

### 5.1 基础股票池 (50只)

**分类**:

| 类别 | 标的 | 数量 |
|------|------|------|
| 科技巨头 | 腾讯、阿里、美团、京东、百度、快手、哔哩、小米 | 8 |
| 新能源/汽车 | 比亚迪、小鹏、理想 | 3 |
| 金融地产 | 中国平安、中国银行、友邦、华润 | 4 |
| 医药 | 石药、药明 | 2 |
| Web3/Crypto | OSL、联想 | 2 |
| 消费/其他 | 安踏、海尔、中芯等 | 31 |

### 5.2 动态打分流程

```
Step1: 基础池 (50只)
         ↓
Step2: 跨市场打分 (每只股票)
         ├─ 0.4 × Crypto相关性得分
         ├─ 0.4 × 美股映射得分
         └─ 0.2 × 本地因子得分
         ↓
Step3: 排序筛选
         ├─ Top 5  → 核心重仓池
         ├─ Top 6~10 → 交易池
         └─ Top 11~20 → 观察池
         ↓
Step4: 风控过滤
         ├─ 剔除风险信号
         └─ 调整仓位建议
         ↓
Step5: 输出交易池
```

### 5.3 分层结构

```
【Top5 核心重仓】(集中度 60%)
├── 腾讯(00700): 0.78 → BUY → 15%
├── 阿里(9988): 0.74 → BUY → 12%
├── OSL(0863): 0.72 → BUY → 12%
├── 美团(3690): 0.71 → BUY → 11%
└── 小米(1810): 0.68 → BUY → 10%

【Top6~10 机会仓】(集中度 30%)
├── 京东(9618): 0.65 → BUY → 8%
├── 比亚迪(1211): 0.63 → BUY → 7%
├── 百度(9888): 0.61 → BUY → 6%
├── 快手(1024): 0.59 → BUY → 5%
└── 中芯(0981): 0.58 → BUY → 4%

【Top11~20 观察池】(集中度 10%)
└── (仅观察，不交易)
```

---

## 六、市场状态识别 + 动态策略切换

### 6.1 市场状态判定

```python
def detect_market_state(crypto_signal, us_signal, hk_volatility):
    """
    判定当前市场状态
    """
    if crypto_signal > 0.5 and us_signal > 0.4:
        return "BULL"        # 牛市
    elif crypto_signal < -0.3 and us_signal < -0.2:
        return "BEAR"        # 熊市
    elif abs(crypto_signal) < 0.2 and abs(us_signal) < 0.2:
        return "RANGE"       # 震荡市
    else:
        return "UNCERTAIN"   # 不确定
```

### 6.2 动态策略切换

| 市场状态 | 策略模式 | 仓位上限 | 持仓周期 | 止损宽度 |
|----------|----------|----------|----------|----------|
| 牛市 (BULL) | 激进追击 | 90% | 1-3天 | 5% |
| 熊市 (BEAR) | 防守/做空 | 30% | 日内 | 3% |
| 震荡 (RANGE) | 高频套利 | 50% | 日内 | 2% |
| 不确定 | 空仓观望 | 0% | - | - |

### 6.3 策略参数动态调整

```python
strategy_params = {
    "BULL": {
        "position_limit": 0.90,      # 仓位上限
        "holding_period": "1-3d",    # 持仓周期
        "stop_loss": 0.05,           # 止损 5%
        "take_profit": 0.15,         # 止盈 15%
        "leverage": 1.0,             # 无杠杆
        "rebalance_freq": "daily",   # 每日调仓
    },
    "BEAR": {
        "position_limit": 0.30,
        "holding_period": "intraday",
        "stop_loss": 0.03,
        "take_profit": 0.08,
        "leverage": 0.5,             # 降低风险
        "rebalance_freq": "intraday",
    },
    "RANGE": {
        "position_limit": 0.50,
        "holding_period": "intraday",
        "stop_loss": 0.02,
        "take_profit": 0.05,
        "leverage": 1.0,
        "rebalance_freq": "intraday",
    }
}
```

---

## 七、典型实战场景推演

### 场景1: BTC暴涨 + 美股确认

```
信号:
├── BTC 5m: +2.1% (动量强)
├── ETH 5m: +1.8%
├── COIN: +3.5%
├── NVDA: +1.2%
└── QQQ: +0.8%

Layer1 信号: +0.85 (强)
Layer2 确认: +0.72 (强)
市场状态: BULL

输出交易池:
├── 腾讯(00700): BUY → 0.82 → 18%
├── OSL(0863): BUY → 0.79 → 15%
├── 阿里(9988): BUY → 0.76 → 15%
├── 美团(3690): BUY → 0.74 → 12%
└── 小米(1810): BUY → 0.71 → 12%

总仓位: 72%
策略: 激进追击，持仓1-3天
```

### 场景2: BTC涨但美股不确认

```
信号:
├── BTC 5m: +1.2%
├── ETH 5m: +0.8%
├── COIN: +0.3%
├── NVDA: -0.2%
└── QQQ: -0.1%

Layer1 信号: +0.55 (中)
Layer2 确认: +0.15 (弱)
市场状态: UNCERTAIN

输出:
├── 降低仓位至30%
├── 仅轻仓试单
├── 缩短持仓周期至日内
└── 严格止损2%

操作: 观望为主，等待美股确认
```

### 场景3: BTC暴跌 + 美股同步下跌

```
信号:
├── BTC 5m: -3.5%
├── ETH 5m: -4.2%
├── COIN: -5.1%
├── NVDA: -2.3%
└── QQQ: -1.5%

Layer1 信号: -0.88 (极强空)
Layer2 确认: -0.72 (强空)
市场状态: BEAR

输出:
├── 全部清仓
├── 或反向做空 (如有工具)
├── 现金比例: 100%
└── 停止开新仓

操作: 风险关闭，保护本金
```

---

## 八、当前代码实现状态

### 8.1 已实现 ✅

| 模块 | 状态 | 文件 |
|------|------|------|
| Agent1 数据采集 | ✅ | `agents/agent1_harvester/main.py` |
| Layer1/2/3 因子计算 | ✅ | `agents/agent2_curator/main.py` |
| 跨市场融合引擎 | ✅ | `CrossMarketFusionEngine` |
| Agent3 机会筛选 | ✅ | `agents/agent3_scanner/main.py` |
| Agent4 双轨决策 | ✅ | `agents/agent4_oracle/main.py` |
| Agent5 风控 | ✅ | `agents/agent5_guardian/main.py` |
| 新闻因子增强 | ✅ | `core/news_analyzer.py` |

### 8.2 待增强 📝

| 功能 | 状态 | 说明 |
|------|------|------|
| 市场状态识别 | 📝 | 需添加到 Agent2 |
| 动态策略切换 | 📝 | 需添加到 Agent6 |
| Brave 新闻 | 📝 | 网络待修复 |

---

## 九、下一步行动

### 立即执行 (P0)

1. **添加市场状态识别模块** → Agent2
2. **添加动态策略切换** → Agent6
3. **配置 API 凭证** → 启动真实盘测试

### 后续优化 (P1)

1. 修复 Brave 新闻网络问题
2. 添加更多标的映射
3. 优化融合权重参数

---

*文档生成时间: 2026-04-08*
*版本: v1.0*
