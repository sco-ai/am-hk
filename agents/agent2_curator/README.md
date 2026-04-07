# Agent 2: DataCurator (数据策展师)

## 核心职责

1. **数据清洗**
   - 去除异常值（价格跳变 >10%，Z-score >3σ）
   - 处理缺失值（前向填充）
   - 时间戳对齐（毫秒级）

2. **30+机构级因子计算**
   - **量价因子(10)**：动量、波动率、流动性、加速度
   - **技术指标(8)**：MA、RSI、MACD、布林带
   - **盘口因子(6)**：买卖价差、深度不平衡、压力比
   - **资金流因子(6)**：主力/散户比、北向强度、净流入速度
   - **跨市场因子(5)**：Layer1信号、Layer2确认、传导系数

3. **跨市场信号融合**
   - Layer1(Crypto) → Layer2(美股) → Layer3(港股)
   - 统一时间轴对齐
   - z-score归一化

4. **数据质量控制**
   - 延迟监控（Tick延迟 ≤ 50ms）
   - 完整性检查
   - 质量评分(0-1)

## 输入/输出

**输入Topic**: `am-hk-raw-market-data`
**输出Topic**: `am-hk-processed-data`

## 使用

```bash
cd am-hk
python -m agents.agent2_curator.main
```

## 因子列表

| 类别 | 数量 | 示例 |
|------|------|------|
| 量价因子 | 10 | price_momentum_5m, volatility_20 |
| 技术指标 | 8 | rsi_14, macd, bb_upper |
| 盘口因子 | 6 | orderbook_imbalance, depth_change_rate |
| 资金流因子 | 6 | main_force_ratio, northbound_strength |
| 跨市场因子 | 5 | layer1_signal, cross_market_momentum |

**总计**: 35个机构级因子
