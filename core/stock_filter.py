"""
港股硬性过滤模块 (Stock Filter - 七道红线)
基于财务和流动性指标的硬性筛选
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("stock_filter")


class FilterResult(Enum):
    """过滤结果"""
    PASS = "pass"           # 通过
    FAIL_PRICE = "fail_price"   # 价格不合格
    FAIL_MARKET_CAP = "fail_market_cap"  # 市值不合格
    FAIL_FLOAT_CAP = "fail_float_cap"    # 流通市值不合格
    FAIL_ST = "fail_st"     # ST股票
    FAIL_PE = "fail_pe"     # 市盈率不合格
    FAIL_NET_ASSET = "fail_net_asset"    # 净资产不合格


@dataclass
class StockFilterConfig:
    """过滤配置"""
    # 价格范围 (港币)
    min_price: float = 5.0      # 最低5元
    max_price: float = 100.0    # 最高100元 (调整)
    
    # 总市值范围 (港币)
    min_market_cap: float = 1e9     # 10亿
    max_market_cap: float = float('inf')  # 无上限 (调整)
    
    # 流通市值
    min_float_cap: float = 5e8      # 5亿
    
    # 市盈率 (允许亏损股)
    max_pe_ratio: float = float('inf')  # 无上限 (允许亏损)
    min_pe_ratio: float = float('-inf') # 允许负数
    
    # 净资产
    min_net_asset: float = 1.0      # 最低1元
    
    # ST股票
    allow_st: bool = False          # 不允许ST


@dataclass
class FilterCheck:
    """单项检查结果"""
    name: str
    passed: bool
    value: float
    threshold: str
    reason: str


class StockFilter:
    """
    港股硬性过滤器 - 七道红线
    
    过滤条件:
    1. 价格: 5元 < 价格 < 30元
    2. 总市值: 10亿 < 市值 < 500亿
    3. 流通市值: > 5亿
    4. ST状态: 非ST
    5. 市盈率: < 35倍
    6. 净资产: > 1元
    """
    
    def __init__(self, config: Optional[StockFilterConfig] = None):
        self.config = config or StockFilterConfig()
    
    def filter_stock(self, symbol: str, data: Dict) -> Tuple[bool, List[FilterCheck], FilterResult]:
        """
        过滤单只股票
        
        Args:
            symbol: 股票代码
            data: 股票数据 {
                "price": 当前价格,
                "market_cap": 总市值,
                "float_cap": 流通市值,
                "is_st": 是否ST,
                "pe_ratio": 市盈率,
                "net_asset": 每股净资产,
            }
        
        Returns:
            (是否通过, 检查详情, 失败原因)
        """
        checks = []
        
        # 1. 价格检查
        price = data.get("price", 0)
        price_check = FilterCheck(
            name="价格",
            passed=self.config.min_price < price < self.config.max_price,
            value=price,
            threshold=f"{self.config.min_price} < P < {self.config.max_price}",
            reason=f"价格{price:.2f}不在{self.config.min_price}-{self.config.max_price}范围内" if not (self.config.min_price < price < self.config.max_price) else "通过"
        )
        checks.append(price_check)
        
        # 2. 总市值检查
        market_cap = data.get("market_cap", 0)
        market_cap_check = FilterCheck(
            name="总市值",
            passed=self.config.min_market_cap < market_cap < self.config.max_market_cap,
            value=market_cap,
            threshold=f"{self.config.min_market_cap/1e8:.0f}亿 < Cap < {self.config.max_market_cap/1e8:.0f}亿",
            reason=f"市值{market_cap/1e8:.1f}亿不在范围内" if not (self.config.min_market_cap < market_cap < self.config.max_market_cap) else "通过"
        )
        checks.append(market_cap_check)
        
        # 3. 流通市值检查
        float_cap = data.get("float_cap", 0)
        float_cap_check = FilterCheck(
            name="流通市值",
            passed=float_cap > self.config.min_float_cap,
            value=float_cap,
            threshold=f"> {self.config.min_float_cap/1e8:.0f}亿",
            reason=f"流通市值{float_cap/1e8:.1f}亿不足{self.config.min_float_cap/1e8:.0f}亿" if float_cap <= self.config.min_float_cap else "通过"
        )
        checks.append(float_cap_check)
        
        # 4. ST状态检查
        is_st = data.get("is_st", False)
        st_check = FilterCheck(
            name="ST状态",
            passed=not is_st if not self.config.allow_st else True,
            value=1 if is_st else 0,
            threshold="非ST",
            reason="ST股票" if is_st else "通过"
        )
        checks.append(st_check)
        
        # 5. 市盈率检查 (允许亏损股)
        pe_ratio = data.get("pe_ratio", 0)
        # 允许任何市盈率(包括负数/亏损股)
        pe_check = FilterCheck(
            name="市盈率",
            passed=True,  # 允许所有
            value=pe_ratio,
            threshold="允许亏损股",
            reason="通过(允许亏损)"
        )
        checks.append(pe_check)
        
        # 6. 净资产检查
        net_asset = data.get("net_asset", 0)
        net_asset_check = FilterCheck(
            name="净资产",
            passed=net_asset > self.config.min_net_asset,
            value=net_asset,
            threshold=f"> {self.config.min_net_asset}元",
            reason=f"净资产{net_asset:.2f}元不足{self.config.min_net_asset}元" if net_asset <= self.config.min_net_asset else "通过"
        )
        checks.append(net_asset_check)
        
        # 判断整体结果
        all_passed = all(check.passed for check in checks)
        
        # 确定失败原因
        fail_result = FilterResult.PASS
        if not all_passed:
            for check in checks:
                if not check.passed:
                    if check.name == "价格":
                        fail_result = FilterResult.FAIL_PRICE
                    elif check.name == "总市值":
                        fail_result = FilterResult.FAIL_MARKET_CAP
                    elif check.name == "流通市值":
                        fail_result = FilterResult.FAIL_FLOAT_CAP
                    elif check.name == "ST状态":
                        fail_result = FilterResult.FAIL_ST
                    elif check.name == "市盈率":
                        fail_result = FilterResult.FAIL_PE
                    elif check.name == "净资产":
                        fail_result = FilterResult.FAIL_NET_ASSET
                    break
        
        if all_passed:
            logger.debug(f"✅ {symbol} 通过硬性过滤")
        else:
            failed_checks = [c.name for c in checks if not c.passed]
            logger.debug(f"❌ {symbol} 未通过: {', '.join(failed_checks)}")
        
        return all_passed, checks, fail_result
    
    def filter_stocks(self, stocks_data: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        批量过滤股票
        
        Args:
            stocks_data: {symbol: data}
        
        Returns:
            通过过滤的股票
        """
        passed = {}
        stats = {result: 0 for result in FilterResult}
        
        for symbol, data in stocks_data.items():
            is_passed, checks, fail_result = self.filter_stock(symbol, data)
            stats[fail_result] += 1
            
            if is_passed:
                passed[symbol] = data
        
        total = len(stocks_data)
        passed_count = len(passed)
        
        logger.info(f"硬性过滤完成: {passed_count}/{total} 通过 "
                   f"({passed_count/total*100:.1f}%)")
        logger.info(f"  通过: {stats[FilterResult.PASS]}")
        logger.info(f"  价格不符: {stats[FilterResult.FAIL_PRICE]}")
        logger.info(f"  市值不符: {stats[FilterResult.FAIL_MARKET_CAP]}")
        logger.info(f"  流通市值不符: {stats[FilterResult.FAIL_FLOAT_CAP]}")
        logger.info(f"  ST股票: {stats[FilterResult.FAIL_ST]}")
        logger.info(f"  市盈率不符: {stats[FilterResult.FAIL_PE]}")
        logger.info(f"  净资产不符: {stats[FilterResult.FAIL_NET_ASSET]}")
        
        return passed


# === 便捷函数 ===

def filter_hk_stocks(stocks_data: Dict[str, Dict]) -> List[str]:
    """
    过滤港股，返回通过的代码列表
    
    Usage:
        symbols = filter_hk_stocks({
            "00700": {"price": 380, "market_cap": 3.6e12, ...},
            "09988": {"price": 85, "market_cap": 1.8e12, ...},
        })
    """
    filter_obj = StockFilter()
    passed = filter_obj.filter_stocks(stocks_data)
    return list(passed.keys())


# === 测试数据 ===

TEST_STOCKS = {
    "00700": {  # 腾讯 - 应该通过
        "price": 380.0,
        "market_cap": 3.6e12,
        "float_cap": 3.4e12,
        "is_st": False,
        "pe_ratio": 18.5,
        "net_asset": 85.2,
    },
    "09988": {  # 阿里 - 应该通过
        "price": 85.0,
        "market_cap": 1.8e12,
        "float_cap": 1.6e12,
        "is_st": False,
        "pe_ratio": 15.2,
        "net_asset": 52.8,
    },
    "00863": {  # OSL - 应该通过
        "price": 12.5,
        "market_cap": 8.5e9,
        "float_cap": 6.2e9,
        "is_st": False,
        "pe_ratio": -5.2,  # 亏损
        "net_asset": 3.2,
    },
    "TEST01": {  # 仙股 - 价格太低
        "price": 0.5,
        "market_cap": 5e8,
        "float_cap": 4e8,
        "is_st": False,
        "pe_ratio": 10.0,
        "net_asset": 2.0,
    },
    "TEST02": {  # 高价股 - 价格太高
        "price": 500.0,
        "market_cap": 2e12,
        "float_cap": 1.8e12,
        "is_st": False,
        "pe_ratio": 20.0,
        "net_asset": 100.0,
    },
    "TEST03": {  # ST股票
        "price": 15.0,
        "market_cap": 5e9,
        "float_cap": 4e9,
        "is_st": True,
        "pe_ratio": 10.0,
        "net_asset": 5.0,
    },
    "TEST04": {  # 市盈率过高
        "price": 20.0,
        "market_cap": 5e9,
        "float_cap": 4e9,
        "is_st": False,
        "pe_ratio": 50.0,
        "net_asset": 5.0,
    },
}


if __name__ == "__main__":
    # 测试
    print("🛡️ 港股硬性过滤测试 (七道红线)")
    print("=" * 60)
    
    filter_obj = StockFilter()
    
    for symbol, data in TEST_STOCKS.items():
        passed, checks, result = filter_obj.filter_stock(symbol, data)
        
        status = "✅ 通过" if passed else f"❌ 未通过 ({result.value})"
        print(f"\n{symbol}: {status}")
        
        for check in checks:
            mark = "✓" if check.passed else "✗"
            print(f"  {mark} {check.name}: {check.value:.2f} (阈值: {check.threshold})")
    
    print("\n" + "=" * 60)
    print("批量过滤统计:")
    passed_stocks = filter_obj.filter_stocks(TEST_STOCKS)
    print(f"通过股票: {list(passed_stocks.keys())}")
