#!/usr/bin/env python3
"""
测试 NewsAPI 配置
"""
import sys
import asyncio
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.news import NewsConnector

async def test_newsapi():
    """测试 NewsAPI"""
    print("="*60)
    print("测试 NewsAPI 配置")
    print("="*60)
    
    connector = NewsConnector()
    
    print(f"\n📋 NewsAPI Key: {'已配置' if connector.newsapi_key else '未配置'}")
    
    if connector.newsapi_key:
        print("\n🔍 获取财经新闻...")
        try:
            await connector.connect()
            
            # 获取比特币相关新闻
            articles = await connector.fetch_newsapi(query="bitcoin", category="business")
            
            print(f"✅ 成功获取 {len(articles)} 条新闻")
            
            if articles:
                print("\n📰 最新新闻:")
                for i, article in enumerate(articles[:3], 1):
                    print(f"\n{i}. {article['title']}")
                    print(f"   来源: {article['source']}")
                    print(f"   时间: {article['published_at']}")
            
            await connector.disconnect()
            
        except Exception as e:
            print(f"❌ 获取失败: {e}")
    else:
        print("⚠️ 请先配置 NEWSAPI_KEY")

if __name__ == "__main__":
    asyncio.run(test_newsapi())
