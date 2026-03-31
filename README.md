# AlphaMind AM-HK 项目

## 项目概述

全新实施项目 - 香港站点

## 项目结构

```
AM-HK/
├── archive/              # 归档历史版本
│   └── 2025-03-31-init/  # 初始框架归档
├── config/               # 配置文件
├── docs/                 # 项目文档
├── scripts/              # 部署/运维脚本
├── specs/                # 技术规范
├── AGENTS.md             # OpenClaw 工作区指南
├── HEARTBEAT.md          # 心跳任务配置
├── IDENTITY.md           # AI 身份配置
├── SOUL.md               # AI 人格配置
└── USER.md               # 用户信息
```

## 快速开始

1. 查看技术规范：`specs/ports-and-deps.md`
2. 配置环境变量：`config/.env.example`
3. 启动服务：参考 `scripts/` 目录

## 技术栈

- Python (虚拟环境隔离)
- PostgreSQL (5452)
- Redis (6399)
- Kafka (9112) + Zookeeper (2201)
- API 服务 (8020)

## 端口速查

| 服务 | 端口 |
|------|------|
| API | 8020 |
| PostgreSQL | 5452 |
| Redis | 6399 |
| Kafka | 9112 |
| Zookeeper | 2201 |
| Kafka UI | 8100 |

---
*项目启动时间：2025-03-31*
