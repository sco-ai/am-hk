#!/usr/bin/env python3
"""
Agent 6 测试脚本 - LearningFeedback 进化层
测试策略持续优化、模型更新广播
"""
import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/AlphaMind/AM-HK/am-hk')

import json
import time
import random


class LearningFeedback:
    """Agent 6: 策略学习与进化"""
    
    def __init__(self):
        # 策略性能追踪
        self.strategy_performance = {
            "momentum": {"wins": 0, "losses": 0, "total_pnl": 0},
            "value": {"wins": 0, "losses": 0, "total_pnl": 0},
            "sentiment": {"wins": 0, "losses": 0, "total_pnl": 0},
            "cross_market": {"wins": 0, "losses": 0, "total_pnl": 0}
        }
        
        # 当前策略权重
        self.current_weights = {
            "momentum": 0.35,
            "value": 0.20,
            "sentiment": 0.25,
            "cross_market": 0.20
        }
        
        # 因子权重
        self.factor_weights = {
            "momentum_5m": 1.0,
            "momentum_15m": 0.8,
            "rsi_14": 1.0,
            "liquidity_score": 1.0,
            "volume_ratio": 1.0,
            "order_imbalance": 1.0
        }
        
        # 学习率
        self.learning_rate = 0.1
    
    def calculate_kelly_fraction(self, win_rate, avg_profit, avg_loss):
        """凯利公式计算最优仓位比例"""
        if avg_loss == 0:
            return 0.1  # 默认保守仓位
        
        b = avg_profit / avg_loss  # 盈亏比
        p = win_rate                 # 胜率
        q = 1 - p                    # 败率
        
        # f* = (p*b - q) / b
        kelly = (p * b - q) / b if b > 0 else 0
        
        # 限制在合理范围 (0.05 - 0.25)
        return max(0.05, min(0.25, kelly))
    
    def update_strategy_weights(self):
        """基于表现更新策略权重 (LightGBM增量学习模拟)"""
        print("\n📊 策略权重更新 (LightGBM增量学习)")
        print("-" * 50)
        
        # 计算各策略的夏普比率近似值
        strategy_scores = {}
        for name, perf in self.strategy_performance.items():
            total_trades = perf["wins"] + perf["losses"]
            if total_trades > 0:
                win_rate = perf["wins"] / total_trades
                avg_return = perf["total_pnl"] / total_trades if total_trades > 0 else 0
                # 简化的性能评分
                strategy_scores[name] = win_rate * max(0, avg_return + 0.01)
            else:
                strategy_scores[name] = 0.01
        
        # 归一化并更新权重
        total_score = sum(strategy_scores.values())
        if total_score > 0:
            new_weights = {
                name: score / total_score 
                for name, score in strategy_scores.items()
            }
            
            # 平滑过渡 (EMA)
            for name in self.current_weights:
                old_w = self.current_weights[name]
                new_w = new_weights.get(name, 0.25)
                self.current_weights[name] = old_w * (1 - self.learning_rate) + new_w * self.learning_rate
        
        # 打印变化
        for name in self.current_weights:
            print(f"   {name:<15}: {self.current_weights[name]:.2%}")
    
    def update_factor_weights(self, trade_results):
        """基于交易结果更新因子权重"""
        print("\n🔧 因子权重优化")
        print("-" * 50)
        
        # 计算各因子的有效性
        factor_performance = {}
        for factor in self.factor_weights:
            factor_performance[factor] = random.uniform(0.8, 1.2)  # 模拟
        
        # 更新权重
        for factor, perf in factor_performance.items():
            old_w = self.factor_weights[factor]
            new_w = old_w * (0.9 + 0.2 * (perf - 1.0))  # 根据表现调整
            self.factor_weights[factor] = max(0.5, min(2.0, new_w))
            
            change = "↑" if new_w > old_w else "↓" if new_w < old_w else "→"
            print(f"   {factor:<20}: {old_w:.2f} → {new_w:.2f} {change}")
    
    def simulate_rl_optimization(self):
        """模拟RL (PPO+LSTM) 策略参数优化"""
        print("\n🧠 RL策略参数优化 (PPO+LSTM)")
        print("-" * 50)
        
        # 模拟优化后的参数
        rl_params = {
            "entry_threshold": random.uniform(0.55, 0.65),
            "exit_threshold": random.uniform(0.70, 0.80),
            "stop_loss_multiplier": random.uniform(1.5, 2.5),
            "position_scale_factor": random.uniform(0.8, 1.2)
        }
        
        for param, value in rl_params.items():
            print(f"   {param:<25}: {value:.4f}")
        
        return rl_params
    
    def simulate_temporal_gnn_update(self):
        """模拟Temporal GNN市场关系图学习"""
        print("\n🕸️ 市场关系图学习 (Temporal GNN)")
        print("-" * 50)
        
        # 模拟市场间传导系数更新
        correlations = {
            "BTC→ETH": random.uniform(0.75, 0.95),
            "BTC→Altcoins": random.uniform(0.60, 0.80),
            "SPX→Crypto": random.uniform(0.30, 0.50),
            "Gold→BTC": random.uniform(-0.2, 0.1)
        }
        
        for pair, corr in correlations.items():
            print(f"   {pair:<20}: {corr:+.3f}")
        
        return correlations
    
    def generate_model_update(self, trade_results):
        """生成模型更新广播"""
        print("\n" + "="*60)
        print("🔄 Agent 6 - 模型更新生成")
        print("="*60)
        
        # 1. 更新策略权重
        self.update_strategy_weights()
        
        # 2. 更新因子权重
        self.update_factor_weights(trade_results)
        
        # 3. RL参数优化
        rl_params = self.simulate_rl_optimization()
        
        # 4. GNN关系图更新
        correlations = self.simulate_temporal_gnn_update()
        
        # 5. 凯利公式最优仓位
        total_wins = sum(p["wins"] for p in self.strategy_performance.values())
        total_losses = sum(p["losses"] for p in self.strategy_performance.values())
        
        if total_wins + total_losses > 0:
            win_rate = total_wins / (total_wins + total_losses)
            avg_profit = 0.03  # 假设3%平均盈利
            avg_loss = 0.02    # 假设2%平均亏损
            kelly_fraction = self.calculate_kelly_fraction(win_rate, avg_profit, avg_loss)
        else:
            kelly_fraction = 0.10
        
        print("\n📐 凯利公式最优仓位")
        print("-" * 50)
        print(f"   胜率: {win_rate:.2%}")
        print(f"   盈亏比: {avg_profit/avg_loss:.2f}")
        print(f"   凯利最优仓位: {kelly_fraction:.2%}")
        print(f"   建议仓位(半凯利): {kelly_fraction/2:.2%}")
        
        # 构建更新消息
        update = {
            "update_type": "model_evolution",
            "timestamp": int(time.time() * 1000),
            "version": f"v{int(time.time())}",
            
            "strategy_weights": self.current_weights.copy(),
            "factor_weights": self.factor_weights.copy(),
            
            "rl_parameters": rl_params,
            "market_correlations": correlations,
            
            "position_sizing": {
                "kelly_fraction": round(kelly_fraction, 4),
                "recommended": round(kelly_fraction / 2, 4),
                "max_single_position": 0.15
            },
            
            "performance_summary": {
                name: {
                    "win_rate": perf["wins"] / (perf["wins"] + perf["losses"]) if perf["wins"] + perf["losses"] > 0 else 0,
                    "total_pnl": perf["total_pnl"]
                }
                for name, perf in self.strategy_performance.items()
            },
            
            "applicable_agents": [
                "agent3_scanner",
                "agent4_oracle",
                "agent5_guardian"
            ],
            
            "update_priority": "high" if kelly_fraction > 0.15 else "normal"
        }
        
        return update
    
    def process_trade_results(self, trade_results):
        """处理交易结果反馈"""
        print("\n📥 接收交易结果反馈")
        print("="*60)
        
        for result in trade_results:
            symbol = result["symbol"]
            pnl = result.get("pnl", 0)
            strategy = result.get("strategy", "momentum")
            
            print(f"\n   {symbol}: PnL={pnl:+.2%}")
            
            # 更新策略性能统计
            if strategy in self.strategy_performance:
                if pnl > 0:
                    self.strategy_performance[strategy]["wins"] += 1
                else:
                    self.strategy_performance[strategy]["losses"] += 1
                self.strategy_performance[strategy]["total_pnl"] += pnl
        
        # 生成模型更新
        update = self.generate_model_update(trade_results)
        
        return update


def main():
    """主测试函数"""
    print("🚀 Agent 6 (LearningFeedback) 测试")
    print("="*60)
    
    # 模拟交易结果反馈
    trade_results = [
        {
            "symbol": "XRPUSDT",
            "strategy": "momentum",
            "entry_price": 100,
            "exit_price": 104.5,
            "pnl": 0.045,
            "hold_time": "2h",
            "status": "win"
        },
        {
            "symbol": "DOGEUSDT",
            "strategy": "sentiment",
            "entry_price": 100,
            "exit_price": 97.8,
            "pnl": -0.022,
            "hold_time": "3h",
            "status": "loss"
        },
        {
            "symbol": "SOLUSDT",
            "strategy": "momentum",
            "entry_price": 150,
            "exit_price": 158,
            "pnl": 0.053,
            "hold_time": "1.5h",
            "status": "win"
        }
    ]
    
    # 初始化学习器
    learner = LearningFeedback()
    
    # 处理交易结果并生成更新
    update = learner.process_trade_results(trade_results)
    
    # 输出结果
    print("\n" + "="*60)
    print("📤 Agent6 输出格式 (Kafka: am-hk-model-updates)")
    print("="*60)
    print(json.dumps(update, indent=2, ensure_ascii=False))
    
    print("\n" + "="*60)
    print("📊 模型更新汇总")
    print("="*60)
    print(f"   更新类型: {update['update_type']}")
    print(f"   版本: {update['version']}")
    print(f"   优先级: {update['update_priority']}")
    print(f"   影响Agent: {len(update['applicable_agents'])} 个")
    print(f"   凯利最优仓位: {update['position_sizing']['kelly_fraction']:.2%}")
    
    print("\n✅ Agent6 测试完成")
    print(f"   输出: 模型更新广播")
    print(f"   推送到: am-hk-model-updates (所有Agent订阅)")
    
    return update


if __name__ == "__main__":
    main()
