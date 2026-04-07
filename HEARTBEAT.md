# HEARTBEAT.md - 定时任务检查

## 说明
此文件配置定时检查任务，用于触发工作日志生成和系统监控。

## 每日任务

### 午间总结 (12:00)
检查上午工作进展，生成午间工作日志。

### 日终总结 (22:00)
总结全天工作，生成日终报告并同步到长期记忆。

## 系统检查
每 4 小时检查一次：
- 数据库连接状态
- Redis 连接状态
- 系统资源使用情况
- 错误日志扫描

## 执行命令
```bash
cd /home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk
source .venv/bin/activate
python scripts/generate_worklog.py --type noon
# 或
python scripts/generate_worklog.py --type evening --sync
```
