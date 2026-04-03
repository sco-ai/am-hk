"""
Kafka 生产者封装
"""
import json
import logging
from typing import Any, Dict, Optional

from confluent_kafka import Producer, KafkaError

from .config import KafkaConfig

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka 生产者"""
    
    def __init__(self, client_id: Optional[str] = None):
        config = KafkaConfig.PRODUCER_CONFIG.copy()
        if client_id:
            config["client.id"] = client_id
        self.producer = Producer(config)
        logger.info(f"Kafka producer initialized: {config['client.id']}")
    
    def _delivery_callback(self, err, msg):
        """消息发送回调"""
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()}")
    
    def send(self, topic: str, key: str, value: Dict[str, Any], headers: Optional[Dict] = None):
        """
        发送消息到指定 topic
        
        Args:
            topic: Kafka topic
            key: 消息键（用于分区）
            value: 消息内容
            headers: 消息头
        """
        try:
            self.producer.produce(
                topic=topic,
                key=key.encode('utf-8') if key else None,
                value=json.dumps(value).encode('utf-8'),
                headers=headers,
                callback=self._delivery_callback
            )
        except KafkaError as e:
            logger.error(f"Failed to produce message: {e}")
            raise
    
    def flush(self, timeout: float = 10.0):
        """刷新缓冲区，确保消息发送"""
        remaining = self.producer.flush(timeout)
        if remaining > 0:
            logger.warning(f"{remaining} messages not delivered")
    
    def close(self):
        """关闭生产者"""
        self.flush()
        logger.info("Kafka producer closed")


class MessageBus:
    """消息总线 - Agent间通信"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.producer = KafkaProducer(client_id=f"{agent_name}-producer")
        self.topics = KafkaConfig.TOPICS
        logger.info(f"MessageBus initialized for {agent_name}")
    
    def publish_market_data(self, symbol: str, data: Dict):
        """发布原始市场数据"""
        self.producer.send(
            topic=self.topics["raw_market_data"],
            key=symbol,
            value=data
        )
    
    def publish_factors(self, symbol: str, factors: Dict):
        """发布因子数据"""
        self.producer.send(
            topic=self.topics["factor_data"],
            key=symbol,
            value=factors
        )
    
    def publish_signal(self, signal: Dict):
        """发布交易信号"""
        self.producer.send(
            topic=self.topics["signals"],
            key=signal.get("symbol", "unknown"),
            value=signal
        )
    
    def publish_decision(self, decision: Dict):
        """发布交易决策"""
        self.producer.send(
            topic=self.topics["decisions"],
            key=decision.get("symbol", "unknown"),
            value=decision
        )
    
    def publish_command(self, target_agent: str, command: Dict):
        """发送命令到指定Agent"""
        self.producer.send(
            topic=self.topics["agent_commands"],
            key=target_agent,
            value={
                "source": self.agent_name,
                "target": target_agent,
                "command": command
            }
        )
    
    def publish_status(self, status: Dict):
        """发布Agent状态"""
        self.producer.send(
            topic=self.topics["agent_status"],
            key=self.agent_name,
            value={
                "agent": self.agent_name,
                "status": status,
            }
        )
    
    def publish_feedback(self, feedback: Dict):
        """发布学习反馈"""
        self.producer.send(
            topic=self.topics["feedback"],
            key=feedback.get("symbol", "unknown"),
            value=feedback
        )
    
    def flush(self):
        """刷新消息"""
        self.producer.flush()
    
    def close(self):
        """关闭消息总线"""
        self.producer.close()
