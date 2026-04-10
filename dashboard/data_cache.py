"""Dashboard 数据缓存 - 存储最新数据供新连接使用"""
from typing import Dict, Any
from collections import defaultdict

class DataCache:
    def __init__(self):
        self.prices: Dict[str, Any] = {}
        self.funding_rates: Dict[str, Any] = {}
        self.news: list = []
        self.max_news = 20
    
    def update_price(self, symbol: str, data: dict):
        self.prices[symbol] = data
    
    def update_funding(self, symbol: str, data: dict):
        self.funding_rates[symbol] = data
    
    def add_news(self, data: dict):
        self.news.insert(0, data)
        if len(self.news) > self.max_news:
            self.news = self.news[:self.max_news]
    
    def get_all(self):
        return {
            "prices": self.prices,
            "funding_rates": self.funding_rates,
            "news": self.news
        }

# 全局缓存实例
cache = DataCache()
