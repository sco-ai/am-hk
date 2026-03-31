# 项目记忆手册 - AlphaMind HK 市场分析

## 项目概述
- **项目名称**: AlphaMind HK 市场分析
- **项目代号**: AM-HK
- **创建日期**: 2026-03-30
- **负责人**: 陈精坤
- **工作区路径**: /home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK
- **飞书群ID**: oc_0a55a3ff64a6f07263da77bf5a30e445

## 项目背景
AM-HK 是 AlphaMind 系列的香港市场分析系统，专注于港股、外汇和衍生品市场分析。系统整合了香港交易所数据、宏观经济数据和市场情绪指标，为投资决策提供全面的市场洞察。

## 核心目标
1. 实时监控香港金融市场数据
2. 提供港股分析和投资建议
3. 外汇市场趋势预测
4. 衍生品风险评估

## 技术栈
- **后端**: Python, FastAPI, Celery
- **前端**: Vue.js, TypeScript, ECharts
- **数据库**: PostgreSQL, MongoDB, Redis
- **部署**: Docker, Kubernetes, Alibaba Cloud
- **其他**: Apache Kafka, Elasticsearch, Kibana

## 项目结构
```
AM-HK/
├── src/                    # 源代码
│   ├── market/            # 市场数据模块
│   ├── analysis/          # 分析引擎
│   ├── api/               # API接口
│   └── utils/             # 工具函数
├── config/                # 配置文件
├── tests/                 # 测试文件
├── docs/                  # 文档
├── scripts/               # 脚本文件
└── docker/                # Docker配置
```

## 关键文件说明
- `main_hk.py`: 主程序入口
- `config/`: 配置文件目录
- `src/`: 源代码目录
- `tests/`: 测试文件目录
- `docs/`: 文档目录

## 开发规范
1. **代码规范**: 遵循 PEP 8
2. **提交规范**: 使用 Conventional Commits
3. **文档要求**: 关键函数必须有文档字符串
4. **测试要求**: 核心功能必须有单元测试

## 部署说明
- **开发环境**: Docker Compose 本地部署
- **测试环境**: Alibaba Cloud ECS
- **生产环境**: Alibaba Cloud ACK

## 依赖管理
- 使用 `requirements.txt` 精确锁定版本
- 虚拟环境目录: `.venv/`
- 定期更新安全依赖

## 端口配置
- **基础端口**: 8200
- **开发端口范围**: 8200-8239
- **测试端口范围**: 8240-8279
- **生产端口范围**: 8280-8319
- **API端口**: 8210
- **监控端口**: 8220

## 运维监控
- **日志路径**: /var/log/am-hk/
- **监控指标**: Prometheus + Grafana
- **告警规则**: Alertmanager 配置

## 项目联系人
- **技术负责人**: 陈精坤
- **运维支持**: AlphaMind 运维团队
- **业务对接**: 香港市场分析团队

## 更新记录
| 日期 | 版本 | 更新内容 | 更新人 |
|------|------|----------|--------|
| 2026-03-30 | 1.0.0 | 初始创建 | 陈精坤 |

---

**注意**: 此文档为项目记忆手册，供 Subagent 了解项目背景和历史决策。