"""
Kafka 生产者封装 - 支持 Redis 降级模式
"""
import json
import logging
from typing import Any, Dict, Optional

from .config import KafkaConfig
from core.config import settings
from core.utils import setup_logging

logger = setup_logging("kafka_producer")

# 尝试导入 Kafka，不可用则标记
try:
    from confluent_kafka import Producer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger.warning("confluent-kafka 不可用，将使用降级模式")

# 尝试导入 Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


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
    """消息总线 - Agent间通信 (支持 Kafka/Redis/内存降级)"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.topics = KafkaConfig.TOPICS
        self.backend = None
        self.producer = None
        self.redis_client = None
        
        # 尝试 Kafka
        if KAFKA_AVAILABLE:
            try:
                self.producer = KafkaProducer(client_id=f"{agent_name}-producer")
                # 测试连接 - 尝试 flush 检查连接状态
                import socket
                host, port = KafkaConfig.BOOTSTRAP_SERVERS.split(':')
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((host, int(port)))
                sock.close()
                if result == 0:
                    self.backend = "kafka"
                    logger.info(f"[{agent_name}] MessageBus using Kafka")
                    return
                else:
                    logger.warning(f"Kafka 端口 {KafkaConfig.BOOTSTRAP_SERVERS} 未开放")
                    self.producer = None
            except Exception as e:
                logger.warning(f"Kafka 连接失败: {e}")
                self.producer = None
        
        # 降级到 Redis
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(settings.redis_url)
                self.redis_client.ping()
                self.backend = "redis"
                logger.info(f"[{agent_name}] MessageBus using Redis fallback")
                return
            except Exception as e:
                logger.warning(f"Redis 连接失败: {e}")
        
        # 内存模式
        self.backend = "memory"
        logger.warning(f"[{agent_name}] MessageBus using memory mode (no persistence)")
    
    def _send(self, topic: str, key: str, value: Dict):
        """内部发送方法，根据后端选择实现"""
        try:
            if self.backend == "kafka" and self.producer:
                self.producer.send(topic=topic, key=key, value=value)
            elif self.backend == "redis" and self.redis_client:
                message = json.dumps({"key": key, "value": value, "topic": topic})
                self.redis_client.publish(topic, message)
            else:
                logger.debug(f"[memory] {topic}: {key} = {value}")
        except Exception as e:
            logger.error(f"发送失败: {e}")
    
    def send(self, topic: str, key: str, value: Dict):
        """发送消息（公共API）"""
        self._send(topic, key, value)
    
    def publish_market_data(self, symbol: str, data: Dict):
        """发布原始市场数据"""
        self._send(self.topics["raw_market_data"], symbol, data)
    
    def publish_factors(self, symbol: str, factors: Dict):
        """发布因子数据"""
        self._send(self.topics["factor_data"], symbol, factors)
    
    def publish_signal(self, signal: Dict):
        """发布交易信号"""
        self._send(self.topics["signals"], signal.get("symbol", "unknown"), signal)
    
    def publish_decision(self, decision: Dict):
        """发布交易决策"""
        self._send(self.topics["decisions"], decision.get("symbol", "unknown"), decision)
    
    def publish_command(self, target_agent: str, command: Dict):
        """发送命令到指定Agent"""
        self._send(
            self.topics["agent_commands"],
            target_agent,
            {"source": self.agent_name, "target": target_agent, "command": command}
        )
    
    def publish_status(self, status: Dict):
        """发布Agent状态"""
        self._send(self.topics["agent_status"], self.agent_name, {"agent": self.agent_name, "status": status})
    
    def publish_feedback(self, feedback: Dict):
        """发布学习反馈"""
        self._send(self.topics["feedback"], feedback.get("symbol", "unknown"), feedback)
    
    def flush(self):
        """刷新消息"""
        if self.backend == "kafka" and self.producer:
            self.producer.flush()
    
    def close(self):
        """关闭消息总线"""
        if self.backend == "kafka" and self.producer:
            self.producer.close()
        if self.backend == "redis" and self.redis_client:
            self.redis_client.close()
        logger.info(f"[{self.agent_name}] MessageBus closed")
