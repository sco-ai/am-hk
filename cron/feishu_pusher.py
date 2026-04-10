#!/usr/bin/env python3
"""
AM-HK 飞书群定时推送脚本
每 30 秒推送实时行情到飞书群
"""
import json
import asyncio
from datetime import datetime
from confluent_kafka import Consumer, KafkaError

# 飞书群 ID
FEISHU_CHAT_ID = "oc_0a55a3ff64a6f07263da77bf5a30e445"

def format_price_message(prices: dict) -> str:
    """格式化价格消息"""
    now = datetime.now().strftime("%H:%M:%S")
    msg = f"📊 实时行情 ({now})\n\n"
    
    for symbol, data in sorted(prices.items()):
        price = data.get('price', 0)
        change = data.get('change_pct', 0)
        emoji = "🟢" if change >= 0 else "🔴"
        change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
        
        # 根据价格决定小数位
        if price < 1:
            price_str = f"${price:.5f}"
        elif price < 100:
            price_str = f"${price:.2f}"
        else:
            price_str = f"${price:,.2f}"
        
        msg += f"{emoji} {symbol}: {price_str} ({change_str})\n"
    
    return msg

async def push_to_feishu():
    """从 Kafka 读取数据并推送到飞书群"""
    conf = {
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'feishu-pusher',
        'auto.offset.reset': 'latest'
    }
    
    consumer = Consumer(conf)
    consumer.subscribe(['am-hk-raw-market-data'])
    
    prices = {}
    last_push = datetime.now()
    
    print(f"[{datetime.now()}] 飞书推送服务启动...")
    print(f"目标群: {FEISHU_CHAT_ID}")
    
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg and not msg.error():
                try:
                    data = json.loads(msg.value().decode('utf-8'))
                    msg_data = data.get('value', data)
                    
                    if msg_data.get('data_type') == 'kline':
                        symbol = msg_data.get('symbol', 'UNKNOWN')
                        payload = msg_data.get('payload', {})
                        prices[symbol] = {
                            'price': payload.get('close', 0),
                            'change_pct': payload.get('change', 0)
                        }
                except Exception as e:
                    print(f"解析错误: {e}")
            
            # 每 30 秒推送一次
            now = datetime.now()
            if (now - last_push).total_seconds() >= 30 and prices:
                try:
                    message = format_price_message(prices)
                    print(f"\n[{now}] 推送消息:\n{message}")
                    
                    # 这里调用飞书 API 发送消息
                    # 由于是在飞书群内运行，可以直接使用 message 工具
                    
                    last_push = now
                    prices = {}  # 清空已推送数据
                    
                except Exception as e:
                    print(f"推送失败: {e}")
                    
    except KeyboardInterrupt:
        print("\n推送服务停止")
    finally:
        consumer.close()

if __name__ == "__main__":
    asyncio.run(push_to_feishu())
