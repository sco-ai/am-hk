# 依赖变更审计日志

## 格式规范

```
## YYYY-MM-DD - 变更类型

**操作人**: @username
**原因**: 简述变更原因
**影响范围**: 受影响的服务/模块

### 变更内容
- 包名: 旧版本 -> 新版本

### 验证结果
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 生产环境验证
```

---

## 2026-04-03 - 老虎证券API接入

**操作人**: @AI-Manager
**原因**: 添加港股/美股数据接入，支持模拟盘/实盘切换
**影响范围**: Agent1 MarketHarvester

### 变更内容
新增文件:
- `core/connectors/tiger.py` - 老虎证券连接器(400+行)

更新文件:
- `.env` - 添加TIGER_ACCOUNT/TIGER_PRIVATE_KEY配置
- `core/connectors/__init__.py` - 导出TigerConnector

### 功能特性
- 港股/美股实时行情
- 订单簿数据
- 模拟盘交易执行
- 持仓/账户查询
- WebSocket实时推送
- 自动签名认证

### 安全配置
```
TIGER_ENABLE_PAPER=true  # 默认模拟盘
```

### 验证结果
- [x] 连接器代码完成
- [ ] API密钥配置（用户自行配置）
- [ ] 连接测试（待密钥配置后）

---

## 2026-04-03 - P1核心决策模块

**操作人**: @AI-Manager
**原因**: 实现Agent4核心AI模型集成
**影响范围**: Agent4 TrendOracle

### 变更内容
新增文件:
- `core/ai_models.py` - AI模型客户端(400+行)
  - InformerModel - 时间序列预测
  - NHITSModel - 趋势分解
  - RLTradingModel - PPO强化学习
  - LLMTradingAnalyzer - GPT-4.1分析
  - ModelFactory - 模型工厂

更新文件:
- `core/config.py` - 添加AI模型配置项
- `agents/agent4_oracle/main.py` - 接入真实AI模型调用

### AI模型配置项
```
INFORMER_API_URL=...
NHITS_API_URL=...
RL_API_URL=...
OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
```

### 验证结果
- [x] 模型客户端实现完成
- [x] Agent4集成完成
- [ ] 云API接入（待配置）

---

## 2026-04-03 - 币安连接器依赖更新

**操作人**: @AI-Manager
**原因**: 添加币安WebSocket实时数据接入所需依赖
**影响范围**: Agent1 MarketHarvester

### 变更内容
新增依赖:
- `websockets==12.0` - WebSocket客户端（币安实时数据）
- `confluent-kafka==2.3.0` - Kafka高性能客户端
- `pydantic-settings==2.1.0` - Pydantic配置管理
- `httpx==0.25.2` - 异步HTTP客户端

### 验证结果
- [x] 依赖安装成功
- [x] 币安连接器模块可导入
- [ ] 集成测试（待实盘验证）

---

## 2026-04-03 - 币安API接入配置

**操作人**: @AI-Manager
**原因**: 配置币安实盘API密钥，实现BTC实时数据采集
**影响范围**: Agent1 MarketHarvester

### 变更内容
- 创建 `.env` 文件，配置币安API密钥
- 创建 `core/connectors/binance.py` 币安连接器
- 更新 `agents/agent1_harvester/main.py` 接入真实数据
- IP白名单已开启（安全措施）

### 配置信息
- API端点: wss://stream.binance.com:9443/ws
- 订阅交易对: BTCUSDT, ETHUSDT
- K线周期: 1m, 5m, 15m
- 数据类型: K线、逐笔成交、订单簿

### 验证结果
- [x] API密钥配置完成
- [x] 连接器代码编写完成
- [ ] WebSocket连接测试（待Kafka启动后）

---

## 2026-04-03 - 虚拟环境初始化

**操作人**: @AI-Manager
**原因**: 按开发规则创建隔离虚拟环境并安装依赖
**影响范围**: 全部服务

### 变更内容
- 创建 Python 3.12 虚拟环境 `.venv/`
- 安装 requirements.txt 中全部依赖（52个包）
- 生成精确版本锁定文件 `requirements.lock`

### 已安装核心依赖
- FastAPI==0.104.1
- SQLAlchemy==2.0.23
- Redis==5.0.1
- Kafka-Python==2.0.2
- Celery==5.3.4
- Pandas==2.1.4
- NumPy==1.26.2

### 验证结果
- [x] 虚拟环境创建成功
- [x] 依赖安装无错误
- [x] 锁定文件生成完成

---

## 2025-03-31 - 初始依赖锁定

**操作人**: @system
**原因**: 项目初始化，建立基础依赖
**影响范围**: 全部服务

### 变更内容
- 建立 requirements.txt 基础版本锁定
- 建立 requirements-dev.txt 开发依赖

### 验证结果
- [x] 开发环境验证通过
