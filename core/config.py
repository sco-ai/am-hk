"""
应用配置管理
"""
import os
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用信息
    APP_NAME: str = "AM-HK"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    
    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8020
    
    # 数据库配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5452
    POSTGRES_DB: str = "alphamind_hk"
    POSTGRES_USER: str = "am_hk_user"
    POSTGRES_PASSWORD: str = "changeme"
    
    # Redis 配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6399
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    
    # Kafka 配置
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9112"
    KAFKA_ZOOKEEPER: str = "localhost:2201"
    KAFKA_PORT: int = 9112
    ZOOKEEPER_PORT: int = 2201
    KAFKA_UI_PORT: int = 8100
    
    # === AI 模型配置 ===
    
    # OpenAI GPT-4.1
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    
    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    
    # Informer时序预测
    INFORMER_API_URL: str = ""
    INFORMER_API_KEY: str = ""
    
    # N-HiTS时序模型
    NHITS_API_URL: str = ""
    NHITS_API_KEY: str = ""
    
    # 强化学习模型
    RL_API_URL: str = ""
    RL_API_KEY: str = ""
    
    # GNN图神经网络
    GNN_API_URL: str = ""
    GNN_API_KEY: str = ""
    
    # FinBERT情绪分析
    FINBERT_API_URL: str = ""
    FINBERT_API_KEY: str = ""
    
    # === 新闻 API 配置 ===
    NEWSAPI_KEY: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_SECRET: str = ""
    
    # === 交易 API 配置 ===
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET: str = ""
    BINANCE_TESTNET: bool = True
    
    TIGER_ACCOUNT: str = ""
    TIGER_PRIVATE_KEY: str = ""
    TIGER_ENABLE_PAPER: bool = True  # true=模拟盘, false=实盘
    
    # 数据采集配置
    DATA_COLLECTION_INTERVAL: int = 60  # 秒
    MARKETS: List[str] = ["btc", "hk_stock", "us_stock"]
    
    # 风控配置
    MAX_POSITION_SIZE: float = 0.1  # 最大仓位10%
    MAX_DAILY_LOSS: float = 0.05    # 最大日亏损5%
    STOP_LOSS_PCT: float = 0.02     # 止损2%
    TAKE_PROFIT_PCT: float = 0.05   # 止盈5%
    
    # 模型配置
    MODEL_UPDATE_INTERVAL: int = 3600  # 模型更新间隔（秒）
    PREDICTION_TIMEFRAMES: List[str] = ["5min", "15min", "1h"]
    
    # 飞书配置
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_WEBHOOK_URL: str = ""
    
    # 代理配置
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""
    
    # 应用安全配置
    SECRET_KEY: str = "generate_a_strong_secret_key_here"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def database_url(self) -> str:
        """PostgreSQL 连接字符串"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def redis_url(self) -> str:
        """Redis 连接字符串"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    def ai_model_enabled(self, model_name: str) -> bool:
        """检查AI模型是否已配置"""
        config_map = {
            "openai": bool(self.OPENAI_API_KEY),
            "deepseek": bool(self.DEEPSEEK_API_KEY),
            "informer": bool(self.INFORMER_API_URL),
            "n-hits": bool(self.NHITS_API_URL),
            "rl": bool(self.RL_API_URL),
            "gnn": bool(self.GNN_API_URL),
            "finbert": bool(self.FINBERT_API_URL),
        }
        return config_map.get(model_name.lower(), False)


# 全局配置实例
settings = Settings()
