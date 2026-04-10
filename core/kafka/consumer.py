"""
Kafka 消费者封装
"""
import json
import logging
import signal
import threading
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

from .config import KafkaConfig

logger = logging.getLogger(__name__)


class BaseConsumer(ABC):
    """消费者基类"""
    
    def __init__(self, group_id: str, topics: List[str]):
        self.group_id = group_id
        self.topics = topics
        self.consumer = Consumer(KafkaConfig.get_consumer_config(group_id))
        self.running = False
        self._stop_event = threading.Event()
        
        # 信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"Received signal {signum}, stopping consumer...")
        self.stop()
    
    def subscribe(self):
        """订阅 topics"""
        self.consumer.subscribe(self.topics)
        logger.info(f"Subscribed to topics: {self.topics}")
    
    @abstractmethod
    def process_message(self, msg_key: str, msg_value: Dict, headers: Optional[Dict]):
        """
        处理消息 - 子类必须实现
        
        Args:
            msg_key: 消息键
            msg_value: 消息内容
            headers: 消息头
        """
        pass
    
    def start(self):
        """启动消费者"""
        self.subscribe()
        self.running = True
        logger.info(f"Consumer started: {self.group_id}")
        
        try:
            while self.running and not self._stop_event.is_set():
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"Reached end of partition: {msg.topic()}")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        raise KafkaException(msg.error())
                else:
                    # 处理消息
                    try:
                        key = msg.key().decode('utf-8') if msg.key() else None
                        value = json.loads(msg.value().decode('utf-8'))
                        headers = dict(msg.headers()) if msg.headers() else None
                        
                        self.process_message(key, value, headers)
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            self.close()
    
    def stop(self):
        """停止消费者"""
        logger.info("Stopping consumer...")
        self.running = False
        self._stop_event.set()
    
    def close(self):
        """关闭消费者"""
        logger.info("Closing consumer...")
        self.consumer.close()


class AgentConsumer(BaseConsumer):
    """Agent专用消费者 - 带消息路由"""
    
    def __init__(self, agent_name: str, topics: List[str]):
        group_id = KafkaConfig.CONSUMER_GROUPS.get(
            agent_name.replace("agent", "").lower(),
            f"am-hk-{agent_name}-group"
        )
        super().__init__(group_id, topics)
        self.agent_name = agent_name
        self.handlers: Dict[str, Callable] = {}
    
    def register_handler(self, msg_type: str, handler: Callable):
        """注册消息处理器"""
        self.handlers[msg_type] = handler
        logger.info(f"Registered handler for {msg_type}")
    
    def process_message(self, msg_key: str, msg_value: Dict, headers: Optional[Dict]):
        """路由消息到对应处理器"""
        # 支持 msg_type 或 data_type 字段
        msg_type = msg_value.get("msg_type") or msg_value.get("data_type", "unknown")

        if msg_type in self.handlers:
            try:
                self.handlers[msg_type](msg_key, msg_value, headers)
            except Exception as e:
                logger.error(f"Handler error for {msg_type}: {e}", exc_info=True)
        else:
            # 尝试使用默认的 market_data handler
            if "market_data" in self.handlers:
                try:
                    self.handlers["market_data"](msg_key, msg_value, headers)
                except Exception as e:
                    logger.error(f"Handler error for market_data: {e}", exc_info=True)
            else:
                logger.debug(f"No handler for message type: {msg_type}")
