# AM-HK 实施路线图 - Agent1 与跨市场信号引擎

**更新日期**: 2026-04-08  
**版本**: 3.0.0  
**状态**: 规划中

---

## 当前系统状态

### ✅ 已完成

| 组件 | 状态 | 备注 |
|------|------|------|
| PostgreSQL | ✅ 运行中 | 端口 5452 |
| Redis | ✅ 运行中 | 端口 6399, Kafka降级 |
| Agent1 框架 | ✅ 就绪 | 币安API配置完成 |
| MessageBus | ✅ 降级模式 | Redis Pub/Sub |
| Dashboard | ✅ 已创建 | 端口 5020 |

### ⚠️ 进行中/阻塞

| 组件 | 状态 | 阻塞原因 | 解决方案 |
|------|------|----------|----------|
| 币安 WebSocket | ⚠️ 404错误 | 测试网限制 | 改用REST轮询/主网 |
| NewsAPI | ⚠️ 网络不通 | 代理未启动 | Clash重启后恢复 |
| 港股数据源 | ❌ 未接入 | 需老虎证券API | 申请开通 |
| 美股数据源 | ❌ 未接入 | 需数据源 | 等待接入 |

---

## 实施阶段规划

### Phase 1: Crypto 基础设施 (本周)
**目标**: BTC数据稳定采集 + Dashboard可视化

- [x] 币安API配置
- [ ] 修复WebSocket连接（或改用REST轮询）
- [ ] 启动Dashboard展示实时数据
- [ ] 数据存入PostgreSQL
- [ ] 基础数据质量检查

**关键产出**:
- 实时BTC价格/成交/订单簿展示
- 1分钟K线数据积累

---

### Phase 2: 跨市场信号 - Layer1 Crypto (第2周)
**目标**: Crypto先行信号计算

- [ ] BTC/ETH/DOGE实时指标计算
  - Trend Score (趋势)
  - Momentum (动量)
  - Sentiment (情绪)
- [ ] 信号标准化输出
- [ ] 历史回测数据准备

**关键产出**:
```json
{
  "crypto_trend_score": 0.75,
  "crypto_momentum": 0.82,
  "crypto_sentiment": 0.65,
  "risk_appetite": "high"
}
```

---

### Phase 3: 跨市场信号 - Layer2 美股 (第3-4周)
**目标**: 美股确认信号接入

- [ ] 美股数据源接入
  - 选项A: Yahoo Finance API
  - 选项B: Alpha Vantage
  - 选项C: 其他数据提供商
- [ ] 核心标的映射
  - COIN → BTC信号
  - NVDA → 科技板块
  - QQQ → 整体风险情绪
- [ ] 美股信号计算

**关键产出**:
```json
{
  "us_trend_score": 0.68,
  "sector_strength": {
    "tech": 0.75,
    "crypto": 0.82
  },
  "risk_on_off": "on"
}
```

---

### Phase 4: 跨市场信号 - Layer3 港股 (第5-6周)
**目标**: 港股执行层 + 交易池生成

- [ ] 老虎证券API接入
- [ ] 港股核心数据采集
  - 北水资金流 ⭐
  - Level2盘口
  - 分时数据
- [ ] 映射规则实现
  - BTC↑ → OSL Group
  - NVDA↑ → Tencent
  - QQQ↑ → Alibaba
- [ ] 交易池生成算法

**关键产出**:
```json
{
  "trading_pool": [
    {"symbol": "0700.HK", "direction": "BUY", "confidence": 0.78},
    {"symbol": "9988.HK", "direction": "BUY", "confidence": 0.74},
    {"symbol": "0863.HK", "direction": "BUY", "confidence": 0.69}
  ]
}
```

---

### Phase 5: 信号融合与风控 (第7-8周)
**目标**: 完整跨市场信号 + 自动交易

- [ ] 三层信号融合模型
  ```
  Final Score = 0.4×Crypto + 0.4×US + 0.2×HK
  ```
- [ ] 市场状态识别
  - 牛市/熊市/震荡判定
- [ ] Agent5 RiskGuardian完善
  - 仓位管理
  - 止损止盈
- [ ] 模拟盘交易测试

---

### Phase 6: 生产部署 (第9-10周)
**目标**: 稳定运行 + 性能优化

- [ ] Kafka集群部署（网络恢复后）
- [ ] 监控告警系统
- [ ] 数据备份策略
- [ ] 回测框架完善
- [ ] 文档完善

---

## 技术债务清单

| 优先级 | 问题 | 影响 | 计划解决时间 |
|--------|------|------|--------------|
| P0 | 币安WebSocket 404 | 无法实时数据 | Phase 1 |
| P1 | 无Kafka | 消息总线降级 | Phase 6 |
| P1 | Clash代理未启动 | 外部API受限 | Phase 1 |
| P2 | Pydantic v2 弃用警告 | 未来兼容性 | Phase 6 |
| P2 | 缺少港股数据源 | 核心功能缺失 | Phase 4 |

---

## 本周行动计划 (2026-04-08 ~ 04-13)

### Day 1 (今天)
- [x] 保存Agent1设计文档
- [ ] 修复币安数据采集（REST轮询模式）
- [ ] 启动Dashboard
- [ ] 测试数据流

### Day 2-3
- [ ] 实现BTC基础指标计算
- [ ] 数据质量检查
- [ ] 存入PostgreSQL

### Day 4-5
- [ ] 修复/重启Clash代理
- [ ] 测试NewsAPI连接
- [ ] 新闻数据采集

### Day 6-7
- [ ] 周报生成
- [ ] 系统稳定性测试
- [ ] 下周计划调整

---

## 关键里程碑

| 日期 | 里程碑 | 验收标准 |
|------|--------|----------|
| 2026-04-13 | Phase 1 完成 | Dashboard显示实时BTC数据 |
| 2026-04-20 | Phase 2 完成 | Crypto信号可计算并输出 |
| 2026-05-04 | Phase 3 完成 | 美股信号接入并运行 |
| 2026-05-18 | Phase 4 完成 | 港股交易池自动生成 |
| 2026-06-01 | Phase 5 完成 | 模拟盘交易测试通过 |
| 2026-06-15 | Phase 6 完成 | 生产环境稳定运行 |

---

## 资源需求

### 数据源
- [x] 币安 Testnet API
- [ ] 币安 Mainnet API (用于生产)
- [ ] 老虎证券 OpenAPI
- [ ] Yahoo Finance / Alpha Vantage
- [x] NewsAPI

### 基础设施
- [ ] Kafka 集群 (网络恢复后)
- [ ] Grafana 监控
- [ ] 备份存储

### 人力
- 当前: AlphaMind (AI Agent)
- 需要: 数据源对接支持

---

**下一步**: 修复币安数据采集并启动Dashboard展示
