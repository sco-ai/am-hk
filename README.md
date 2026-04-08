# AM-HK v3.0 - 机构级量化交易系统

## 系统架构

```
Agent1 (MarketHarvester) → Agent2 (DataCurator) → Agent3 (AlphaScanner)
                                                          ↓
Agent6 (LearningFeedback) ← Agent5 (RiskGuardian) ← Agent4 (TrendOracle)
        ↑                                               ↓
        └───────────── Agent7 (PerformanceAnalyzer) ←───┘
```

## 7大Agent职责

| Agent | 名称 | 职责 | 核心模型 |
|-------|------|------|----------|
| Agent1 | MarketHarvester | 多市场数据采集 | 规则驱动 |
| Agent2 | DataCurator | 30+因子计算 | Z-score / Isolation Forest |
| Agent3 | AlphaScanner | 机会筛选 | LightGBM + GPT-4.1 |
| Agent4 | TrendOracle | 核心决策 | Informer + PPO + GPT-4.1 |
| Agent5 | RiskGuardian | 风控审批 | 规则 + AI风控 |
| Agent6 | LearningFeedback | 学习进化 | PPO + GNN + FinBERT |
| Agent7 | PerformanceAnalyzer | 绩效分析 | 统计分析 + VaR/CVaR |

## 四大AI能力

- **时间序列预测**: Informer / N-HiTS / Autoformer
- **强化学习**: PPO / DQN / A3C (云训练)
- **图神经网络**: Temporal GNN (市场联动)
- **NLP情绪分析**: FinBERT / GPT-4.1

## 快速启动

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp config/.env.example .env
# 编辑 .env 文件，填入API密钥
```

### 3. 启动基础设施

```bash
# 启动Kafka, Redis, PostgreSQL
docker-compose up -d
```

### 4. 启动系统

```bash
# 启动所有Agent和API
python main.py

# 或单独启动Agent
python -m agents.agent1_harvester.main
python -m agents.agent2_curator.main
...
```

## API接口

启动后访问: http://localhost:8020

- `GET /` - 系统信息
- `GET /health` - 健康检查
- `POST /trading/start` - 启动交易
- `POST /trading/stop` - 停止交易
- `GET /signals` - 获取信号
- `GET /metrics` - 性能指标

## 端口分配

| 服务 | 端口 |
|------|------|
| API | 8020 |
| PostgreSQL | 5452 |
| Redis | 6399 |
| Kafka | 9112 |
| Zookeeper | 2201 |
| Kafka UI | 8100 |

## 项目结构

```
am-hk/
├── agents/              # 7个Agent实现
│   ├── agent1_harvester/
│   ├── agent2_curator/
│   ├── agent3_scanner/
│   ├── agent4_oracle/
│   ├── agent5_guardian/
│   ├── agent6_learning/
│   └── agent7_performance/
├── core/                # 核心组件
│   ├── kafka/          # Kafka消息系统
│   ├── models.py       # 数据模型
│   ├── config.py       # 配置管理
│   └── utils.py        # 工具函数
├── api/                 # API服务
├── config/              # 配置文件
├── docs/                # 文档
└── main.py             # 主入口
```

## 开发规范

详见 `DEVELOPMENT_RULES.md`

- Python依赖完全隔离（虚拟环境）
- 版本锁定（requirements.lock）
- 仅使用相对路径
- 禁止/tmp/和系统绝对路径

## License

Proprietary - AlphaMind HK
