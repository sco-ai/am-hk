"""
消息总线 - Redis 降级模式 (Kafka 不可用时使用)

当 Kafka 不可用时，使用 Redis Pub/Sub 作为替代消息总线。
功能受限但足够支持单节点运行。
"""
import json
import logging
from typing import Callable, Dict, Optional

from core.config import settings
from core.models import MarketType
from core.utils import setup_logging

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from confluent_kafka import Producer, Consumer, KafkaException
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

logger = setup_logging("message_bus")


class MessageBus:
    """
    消息总线 - 自动选择 Kafka 或 Redis
    
    优先级:
    1. Kafka (高性能，分布式)
    2. Redis Pub/Sub (降级模式，单节点)
    3. 内存模式 (仅测试)
    """
    
    def __init__(self, client_id: str = "am-hk"):
        self.client_id = client_id
        self.backend = None
        self.producer = None
        self.redis_client = None
        self.subscribers = {}  # 内存模式使用
        
        # 尝试连接 Kafka
        if KAFKA_AVAILABLE:
            try:
                from core.kafka.config import KafkaConfig
                self.producer = Producer(KafkaConfig.PRODUCER_CONFIG)
                self.backend = "kafka"
                logger.info(f"[{client_id}] 使用 Kafka 消息总线")
                return
            except Exception as e:
                logger.warning(f"Kafka 连接失败: {e}")
        
        # 降级到 Redis
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(settings.redis_url)
                self.redis_client.ping()
                self.backend = "redis"
                logger.info(f"[{client_id}] 使用 Redis 降级模式")
                return
            except Exception as e:
                logger.warning(f"Redis 连接失败: {e}")
        
        # 内存模式
        self.backend = "memory"
        logger.warning(f"[{client_id}] 使用内存模式 (无持久化)")
    
    def send(self, topic: str, key: str, value: Dict):
        """发送消息"""
        try:
            if self.backend == "kafka" and self.producer:
                self.producer.produce(
                    topic=topic,
                    key=key.encode() if key else None,
                    value=json.dumps(value).encode()
                )
                self.producer.poll(0)
            
            elif self.backend == "redis" and self.redis_client:
                message = {
                    "key": key,
                    "value": value,
                    "topic": topic
                }
                self.redis_client.publish(topic, json.dumps(message))
            
            elif self.backend == "memory":
                if topic not in self.subscribers:
                    self.subscribers[topic] = []
                for callback in self.subscribers[topic]:
                    callback(key, value)
                    
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def publish_market_data(self, symbol: str, data: Dict):
        """发布市场数据"""
        self.send("am-hk-raw-market-data", symbol, data)
    
    def publish_status(self, status: Dict):
        """发布Agent状态"""
        self.send("am-hk-agent-status", self.client_id, status)
    
    def subscribe(self, topic: str, callback: Callable):
        """订阅主题 (仅内存模式)"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
    
    def flush(self):
        """刷新缓冲区"""
        if self.backend == "kafka" and self.producer:
            self.producer.flush()
    
    def close(self):
        """关闭连接"""
        if self.backend == "kafka" and self.producer:
            self.producer.flush()
        if self.backend == "redis" and self.redis_client:
            self.redis_client.close()
        logger.info(f"[{self.client_id}] 消息总线已关闭")


# 兼容旧代码的导入
KafkaProducer = MessageBus
