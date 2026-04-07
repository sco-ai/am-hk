#!/usr/bin/env python3
"""
Test script for funding data collection
验证资金数据格式是否符合规范
"""

import sys
import asyncio
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

from core.connectors.binance_rest import (
    convert_funding_rate_to_standard,
    convert_open_interest_to_standard,
    convert_long_short_ratio_to_standard,
    convert_kline_to_standard,
)
from core.models import MarketType
import json


def test_funding_rate_conversion():
    """测试资金费率数据转换"""
    print("=" * 60)
    print("Testing Funding Rate Conversion")
    print("=" * 60)

    raw_data = {
        "e": "fundingRate",
        "E": 1712553600000,
        "s": "BTCUSDT",
        "r": "0.00010000",
        "T": 1712553600000
    }

    result = convert_funding_rate_to_standard("BTCUSDT", raw_data)

    print(f"Input: {json.dumps(raw_data, indent=2)}")
    print(f"\nOutput (Standard Format):")
    print(json.dumps(result, indent=2))

    # 验证格式
    assert result["symbol"] == "BTCUSDT", "symbol 不匹配"
    assert result["market"] == "CRYPTO", "market 应该是 CRYPTO"
    assert result["data_type"] == "funding_rate", "data_type 应该是 funding_rate"
    assert "payload" in result, "缺少 payload"
    assert "funding_rate" in result["payload"], "payload 缺少 funding_rate"
    assert "funding_time" in result["payload"], "payload 缺少 funding_time"

    print("\n✓ Funding Rate format validation PASSED\n")
    return result


def test_open_interest_conversion():
    """测试持仓量数据转换"""
    print("=" * 60)
    print("Testing Open Interest Conversion")
    print("=" * 60)

    raw_data = {
        "e": "openInterest",
        "E": 1712553600000,
        "s": "BTCUSDT",
        "o": "123456.789",
        "p": "9876543210"
    }

    result = convert_open_interest_to_standard("BTCUSDT", raw_data)

    print(f"Input: {json.dumps(raw_data, indent=2)}")
    print(f"\nOutput (Standard Format):")
    print(json.dumps(result, indent=2))

    # 验证格式
    assert result["symbol"] == "BTCUSDT", "symbol 不匹配"
    assert result["market"] == "CRYPTO", "market 应该是 CRYPTO"
    assert result["data_type"] == "open_interest", "data_type 应该是 open_interest"
    assert "payload" in result, "缺少 payload"
    assert "open_interest" in result["payload"], "payload 缺少 open_interest"

    print("\n✓ Open Interest format validation PASSED\n")
    return result


def test_long_short_ratio_conversion():
    """测试多空比数据转换"""
    print("=" * 60)
    print("Testing Long/Short Ratio Conversion")
    print("=" * 60)

    raw_data = {
        "e": "longShortRatio",
        "E": 1712553600000,
        "s": "BTCUSDT",
        "l": "0.55",
        "srt": "0.45",
        "r": "1.22"
    }

    result = convert_long_short_ratio_to_standard("BTCUSDT", raw_data)

    print(f"Input: {json.dumps(raw_data, indent=2)}")
    print(f"\nOutput (Standard Format):")
    print(json.dumps(result, indent=2))

    # 验证格式
    assert result["symbol"] == "BTCUSDT", "symbol 不匹配"
    assert result["market"] == "CRYPTO", "market 应该是 CRYPTO"
    assert result["data_type"] == "long_short_ratio", "data_type 应该是 long_short_ratio"
    assert "payload" in result, "缺少 payload"
    assert "long_account_ratio" in result["payload"], "payload 缺少 long_account_ratio"
    assert "short_account_ratio" in result["payload"], "payload 缺少 short_account_ratio"
    assert "long_short_ratio" in result["payload"], "payload 缺少 long_short_ratio"

    print("\n✓ Long/Short Ratio format validation PASSED\n")
    return result


def test_kline_conversion():
    """测试K线数据转换（验证兼容性）"""
    print("=" * 60)
    print("Testing KLine Conversion (Compatibility)")
    print("=" * 60)

    raw_data = {
        "e": "kline",
        "E": 1712553600000,
        "s": "BTCUSDT",
        "k": {
            "t": 1712553600000,
            "T": 1712553659999,
            "s": "BTCUSDT",
            "i": "1m",
            "o": "65000.00",
            "h": "65100.00",
            "l": "64900.00",
            "c": "65050.00",
            "v": "100.5",
            "x": True
        }
    }

    result = convert_kline_to_standard("BTCUSDT", raw_data)

    print(f"Input: {json.dumps(raw_data, indent=2)}")
    print(f"\nOutput (Standard Format):")
    print(json.dumps(result, indent=2))

    # 验证格式
    assert result["symbol"] == "BTCUSDT", "symbol 不匹配"
    assert result["market"] == "CRYPTO", "market 应该是 CRYPTO"
    assert result["data_type"] == "kline", "data_type 应该是 kline"
    assert "payload" in result, "缺少 payload"

    print("\n✓ KLine format validation PASSED\n")
    return result


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("AM-HK Funding Data Format Test Suite")
    print("=" * 60 + "\n")

    try:
        # 测试资金费率
        funding_result = test_funding_rate_conversion()

        # 测试持仓量
        oi_result = test_open_interest_conversion()

        # 测试多空比
        ratio_result = test_long_short_ratio_conversion()

        # 测试K线（兼容性）
        kline_result = test_kline_conversion()

        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print("\nData format summary:")
        print(f"  - Symbol: {funding_result['symbol']}")
        print(f"  - Market: {funding_result['market']}")
        print(f"  - Timestamp: {funding_result['timestamp']} (millisecond)")
        print(f"  - Data types: funding_rate, open_interest, long_short_ratio")
        print()

        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
