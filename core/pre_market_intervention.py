#!/usr/bin/env python3
"""
港股开市前人工干预模块
允许用户在开市前1小时调整选股池
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import os
from datetime import datetime, time
from typing import Dict, List, Optional, Set


class PreMarketIntervention:
    """
    开市前人工干预模块
    
    功能:
    1. 在港股开市前1小时(8:30-9:30)允许人工干预
    2. 支持添加、删除、调整股票
    3. 无干预则默认认可系统选股
    4. 干预记录保存
    """
    
    HK_MARKET_OPEN = time(9, 30)  # 港股开市时间
    INTERVENTION_WINDOW_MINUTES = 60  # 干预窗口(开市前1小时)
    
    def __init__(self, data_dir: str = "/tmp/am-hk/intervention"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.intervention_file = os.path.join(data_dir, "manual_override.json")
        self.system_pool_file = os.path.join(data_dir, "system_pool.json")
        self.final_pool_file = os.path.join(data_dir, "final_pool.json")
        self.history_file = os.path.join(data_dir, "intervention_history.jsonl")
    
    def is_intervention_window(self) -> bool:
        """检查当前是否在干预窗口期"""
        now = datetime.now()
        
        # 计算干预窗口开始时间
        open_time = datetime.combine(now.date(), self.HK_MARKET_OPEN)
        window_start = open_time - __import__('datetime').timedelta(minutes=self.INTERVENTION_WINDOW_MINUTES)
        
        return window_start <= now < open_time
    
    def get_intervention_status(self) -> Dict:
        """获取干预状态"""
        now = datetime.now()
        open_time = datetime.combine(now.date(), self.HK_MARKET_OPEN)
        window_start = open_time - __import__('datetime').timedelta(minutes=self.INTERVENTION_WINDOW_MINUTES)
        
        time_to_open = (open_time - now).total_seconds() / 60
        
        return {
            "in_window": self.is_intervention_window(),
            "market_open_time": open_time.strftime("%H:%M"),
            "window_start": window_start.strftime("%H:%M"),
            "minutes_to_open": int(time_to_open),
            "can_intervene": time_to_open <= self.INTERVENTION_WINDOW_MINUTES and time_to_open > 0,
        }
    
    def save_system_pool(self, symbols: List[str], scores: Dict[str, float]):
        """保存系统选股池"""
        data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "symbols": symbols,
            "scores": scores,
            "count": len(symbols),
        }
        
        with open(self.system_pool_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ 系统选股池已保存: {len(symbols)}只")
        return data
    
    def load_system_pool(self) -> Optional[Dict]:
        """加载系统选股池"""
        if not os.path.exists(self.system_pool_file):
            return None
        
        with open(self.system_pool_file, 'r') as f:
            return json.load(f)
    
    def apply_intervention(self, 
                          add_symbols: List[str] = None,
                          remove_symbols: List[str] = None,
                          adjust_weights: Dict[str, float] = None,
                          notes: str = "") -> Dict:
        """
        应用人工干预
        
        Args:
            add_symbols: 添加的股票代码
            remove_symbols: 删除的股票代码
            adjust_weights: 调整权重 {symbol: weight}
            notes: 干预备注
        
        Returns:
            干预结果
        """
        if not self.is_intervention_window():
            return {
                "success": False,
                "error": "当前不在干预窗口期",
                "status": self.get_intervention_status(),
            }
        
        # 加载系统选股池
        system_pool = self.load_system_pool()
        if not system_pool:
            return {
                "success": False,
                "error": "系统选股池不存在",
            }
        
        # 应用干预
        original_symbols = set(system_pool["symbols"])
        
        # 删除
        if remove_symbols:
            original_symbols -= set(remove_symbols)
        
        # 添加
        if add_symbols:
            original_symbols |= set(add_symbols)
        
        # 生成最终池
        final_symbols = sorted(list(original_symbols))
        
        # 记录干预
        intervention_record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "original_count": len(system_pool["symbols"]),
            "final_count": len(final_symbols),
            "added": add_symbols or [],
            "removed": remove_symbols or [],
            "adjusted_weights": adjust_weights or {},
            "notes": notes,
        }
        
        # 保存干预记录
        with open(self.intervention_file, 'w') as f:
            json.dump(intervention_record, f, indent=2)
        
        # 追加到历史
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(intervention_record) + '\n')
        
        # 保存最终池
        final_pool = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generated_at": system_pool["generated_at"],
            "intervened_at": datetime.now().isoformat(),
            "intervened": True,
            "symbols": final_symbols,
            "count": len(final_symbols),
        }
        
        with open(self.final_pool_file, 'w') as f:
            json.dump(final_pool, f, indent=2)
        
        print(f"✅ 人工干预已应用:")
        print(f"   添加: {add_symbols or '无'}")
        print(f"   删除: {remove_symbols or '无'}")
        print(f"   原数量: {intervention_record['original_count']}")
        print(f"   现数量: {intervention_record['final_count']}")
        
        return {
            "success": True,
            "intervention": intervention_record,
            "final_pool": final_pool,
        }
    
    def finalize_pool(self) -> Dict:
        """
        Finalize选股池 (开市前自动调用)
        如果有干预记录则使用干预后的池，否则使用系统池
        """
        system_pool = self.load_system_pool()
        
        if not system_pool:
            return {
                "success": False,
                "error": "系统选股池不存在",
            }
        
        # 检查是否有干预
        if os.path.exists(self.intervention_file):
            with open(self.intervention_file, 'r') as f:
                intervention = json.load(f)
            
            # 检查是否是今天的干预
            if intervention.get("date") == datetime.now().strftime("%Y-%m-%d"):
                with open(self.final_pool_file, 'r') as f:
                    final_pool = json.load(f)
                
                print(f"✅ 使用人工干预后的选股池: {final_pool['count']}只")
                return {
                    "success": True,
                    "intervened": True,
                    "pool": final_pool,
                }
        
        # 无干预，使用系统池
        final_pool = {
            "date": system_pool["date"],
            "generated_at": system_pool["generated_at"],
            "intervened": False,
            "symbols": system_pool["symbols"],
            "count": system_pool["count"],
        }
        
        with open(self.final_pool_file, 'w') as f:
            json.dump(final_pool, f, indent=2)
        
        print(f"✅ 使用系统选股池(无干预): {final_pool['count']}只")
        return {
            "success": True,
            "intervened": False,
            "pool": final_pool,
        }
    
    def get_final_pool(self) -> Optional[Dict]:
        """获取最终选股池"""
        if not os.path.exists(self.final_pool_file):
            return None
        
        with open(self.final_pool_file, 'r') as f:
            return json.load(f)


def main():
    """测试"""
    print("🎯 开市前人工干预模块测试")
    print("=" * 60)
    
    intervention = PreMarketIntervention()
    
    # 1. 检查干预窗口
    print("\n1️⃣ 干预窗口状态:")
    status = intervention.get_intervention_status()
    print(f"   是否在窗口期: {status['in_window']}")
    print(f"   开市时间: {status['market_open_time']}")
    print(f"   窗口开始: {status['window_start']}")
    print(f"   距离开市: {status['minutes_to_open']}分钟")
    
    # 2. 模拟系统选股池
    print("\n2️⃣ 保存系统选股池:")
    system_pool = intervention.save_system_pool(
        symbols=["00700", "09988", "03690", "00863", "01211"],
        scores={
            "00700": 0.78,
            "09988": 0.74,
            "03690": 0.71,
            "00863": 0.69,
            "01211": 0.65,
        }
    )
    print(f"   选股: {system_pool['symbols']}")
    
    # 3. 模拟人工干预 (添加+删除)
    print("\n3️⃣ 模拟人工干预:")
    print("   操作: 添加'01810'(小米), 删除'00863'(OSL)")
    
    result = intervention.apply_intervention(
        add_symbols=["01810"],
        remove_symbols=["00863"],
        notes="看好小米新车发布，不看好OSL短期波动"
    )
    
    if result["success"]:
        print(f"   ✅ 干预成功")
        print(f"   最终池: {result['final_pool']['symbols']}")
    else:
        print(f"   ⚠️ {result['error']}")
    
    # 4. 最终确认
    print("\n4️⃣ 最终选股池确认:")
    final = intervention.finalize_pool()
    if final["success"]:
        print(f"   是否干预: {final['intervened']}")
        print(f"   最终股票: {final['pool']['symbols']}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成!")


if __name__ == "__main__":
    main()
