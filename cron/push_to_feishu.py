#!/usr/bin/env python3
import json
from datetime import datetime
from confluent_kafka import Consumer, KafkaError

def format_price(data):
    symbol = data.get('symbol', 'UNKNOWN')
    payload = data.get('payload', {})
    price = payload.get('close', 0)
    change = payload.get('change', 0)
    emoji = "🟢" if change >= 0 else "🔴"
    change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
    return f"{emoji} {symbol}: ${price:.5f} ({change_str})"

def main():
    conf = {'bootstrap.servers': 'localhost:9092', 'group.id': 'feishu-pusher', 'auto.offset.reset': 'latest'}
    consumer = Consumer(conf)
    consumer.subscribe(['am-hk-raw-market-data'])
    prices = {}
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None: continue
            if msg.error(): continue
            try:
                data = json.loads(msg.value().decode('utf-8'))
                msg_data = data.get('value', data)
                if msg_data.get('data_type') == 'kline':
                    symbol = msg_data.get('symbol')
                    payload = msg_data.get('payload', {})
                    if payload.get('interval') == '1m':
                        prices[symbol] = msg_data
                        if len(prices) >= 5:
                            time_str = datetime.now().strftime("%H:%M:%S")
                            message = f"📊 实时行情 ({time_str})\n\n"
                            for s in sorted(prices.keys()):
                                message += format_price(prices[s]) + "\n"
                            print("===FEISHU_PUSH===")
                            print(message)
                            print("===END_PUSH===")
                            prices = {}
            except: pass
    except KeyboardInterrupt: pass
    finally: consumer.close()

if __name__ == "__main__":
    main()