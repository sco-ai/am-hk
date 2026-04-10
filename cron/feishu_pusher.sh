#!/bin/bash
cd /home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk
while true; do
    .venv/bin/python3 << 'PYEOF'
import json
from confluent_kafka import Consumer
from datetime import datetime
conf = {'bootstrap.servers': 'localhost:9092', 'group.id': 'feishu-pusher-' + str(__import__('time').time()), 'auto.offset.reset': 'latest'}
consumer = Consumer(conf)
consumer.subscribe(['am-hk-raw-market-data'])
prices = {}
import time
start = time.time()
while len(prices) < 5 and time.time() - start < 10:
    msg = consumer.poll(timeout=1.0)
    if msg and not msg.error():
        try:
            data = json.loads(msg.value().decode('utf-8'))
            msg_data = data.get('value', data)
            if msg_data.get('data_type') == 'kline':
                symbol = msg_data.get('symbol')
                payload = msg_data.get('payload', {})
                if payload.get('interval') == '1m':
                    prices[symbol] = msg_data
        except: pass
consumer.close()
if prices:
    time_str = datetime.now().strftime("%H:%M:%S")
    print(f"📊 实时行情 ({time_str})\n")
    for symbol in sorted(prices.keys()):
        d = prices[symbol]
        payload = d.get('payload', {})
        price = payload.get('close', 0)
        change = payload.get('change', 0)
        emoji = "🟢" if change >= 0 else "🔴"
        change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
        print(f"{emoji} {symbol}: ${price:.5f} ({change_str})")
PYEOF
    sleep 60
done
