# 部署架构（生产级）

## 服务器配置

- 🖥 RTX4090 服务器
- ✅ 完全够用（因为不用本地模型）

## 技术栈

| 层 | 技术 |
|----|------|
| 数据 | Kafka |
| 存储 | TimescaleDB |
| 缓存 | Redis |
| 后端 | Python FastAPI |
| 调度 | Airflow |
| 训练 | Ray |
| 监控 | Prometheus |

## 端口分配

| 服务 | 端口 |
|------|------|
| API | 8020 |
| PostgreSQL | 5452 |
| Redis | 6399 |
| Kafka | 9112 |
| Zookeeper | 2201 |
| Kafka UI | 8100 |

---
*归档时间: 2025-03-31*
