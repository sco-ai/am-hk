"""
Kafka 配置和连接管理
"""
import os
from typing import Dict, List


class KafkaConfig:
    """Kafka 配置"""
    BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # Topics 定义
    TOPICS = {
        # 数据流
        "raw_market_data": "am-hk-raw-market-data",
        "factor_data": "am-hk-factor-data",
        "signals": "am-hk-signals",
        "decisions": "am-hk-decisions",
        "trading_decisions": "am-hk-trading-decisions",  # Agent4 -> Agent5
        "executions": "am-hk-executions",
        "risk_approved_trades": "am-hk-risk-approved-trades",  # Agent5输出
        
        # Agent 命令
        "agent_commands": "am-hk-agent-commands",
        "agent_status": "am-hk-agent-status",
        
        # 学习反馈
        "feedback": "am-hk-feedback",
        "model_updates": "am-hk-model-updates",
    }
    
    # 消费者组
    CONSUMER_GROUPS = {
        "harvester": "am-hk-harvester-group",
        "curator": "am-hk-curator-group",
        "scanner": "am-hk-scanner-group",
        "oracle": "am-hk-oracle-group",
        "guardian": "am-hk-guardian-group",
        "learning": "am-hk-learning-group",
    }
    
    # 生产者配置
    PRODUCER_CONFIG = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "client.id": "am-hk-producer",
        "compression.type": "lz4",
        "batch.size": 16384,
        "linger.ms": 10,
        "acks": "all",
        "retries": 3,
        "retry.backoff.ms": 1000,
    }
    
    # 消费者配置
    @classmethod
    def get_consumer_config(cls, group_id: str) -> Dict:
        return {
            "bootstrap.servers": cls.BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 45000,
        }


# Topic 分区配置
TOPIC_PARTITIONS = {
    "am-hk-raw-market-data": 6,      # 多市场数据，高并发
    "am-hk-factor-data": 4,
    "am-hk-signals": 3,
    "am-hk-decisions": 2,
    "am-hk-trading-decisions": 2,    # Agent4输出到Agent5
    "am-hk-risk-approved-trades": 2, # Agent5输出
    "am-hk-executions": 2,
    "am-hk-agent-commands": 1,       # 命令串行处理
    "am-hk-agent-status": 1,
    "am-hk-feedback": 2,
    "am-hk-model-updates": 1,
}

# Topic 复制因子
TOPIC_REPLICATION = 1  # 开发环境，生产环境建议3
