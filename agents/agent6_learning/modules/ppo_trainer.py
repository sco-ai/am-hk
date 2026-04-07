"""
PPO + LSTM 强化学习训练模块
负责策略参数的强化学习优化
"""
import json
import logging
import random
from typing import Dict, List, Optional, Any, Tuple, Deque
from collections import deque, defaultdict
import numpy as np

from core.utils import setup_logging

logger = setup_logging("ppo_trainer")

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.distributions import Categorical
    TORCH_AVAILABLE = True

    class LSTMNetwork(nn.Module):
        """LSTM策略网络"""
        
        def __init__(self, input_dim: int = 30, hidden_dim: int = 128, output_dim: int = 3):
            super(LSTMNetwork, self).__init__()
            self.hidden_dim = hidden_dim
            
            self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True, num_layers=2, dropout=0.2)
            self.fc1 = nn.Linear(hidden_dim, 64)
            self.fc2 = nn.Linear(64, output_dim)
            self.value_head = nn.Linear(hidden_dim, 1)
            
            self.relu = nn.ReLU()
            self.softmax = nn.Softmax(dim=-1)
        
        def forward(self, x, hidden=None):
            lstm_out, hidden = self.lstm(x, hidden)
            last_hidden = lstm_out[:, -1, :]  # 取最后一个时间步
            
            # 策略头
            x = self.relu(self.fc1(last_hidden))
            action_probs = self.softmax(self.fc2(x))
            
            # 价值头
            value = self.value_head(last_hidden)
            
            return action_probs, value, hidden

except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed, using mock implementation")
    LSTMNetwork = None


class PPOTrainer:
    """
    PPO (Proximal Policy Optimization) + LSTM 训练器
    
    功能：
    - 状态：市场特征 + 持仓状态
    - 动作：买入/卖出/持仓
    - 奖励：夏普比率 + 收益
    - 经验回放
    - 策略更新
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "models/ppo_lstm_model.pt"
        
        # 超参数
        self.gamma = 0.99  # 折扣因子
        self.gae_lambda = 0.95  # GAE lambda
        self.clip_epsilon = 0.2  # PPO clip参数
        self.learning_rate = 3e-4
        self.batch_size = 64
        self.epochs_per_update = 4
        self.min_experiences = 100
        
        # 状态维度
        self.state_dim = 30  # 市场特征 + 持仓特征
        self.action_dim = 3  # 买入、卖出、持仓
        self.seq_len = 10  # LSTM序列长度
        
        # 经验池
        self.experiences: Deque[Dict] = deque(maxlen=10000)
        
        # 当前episode
        self.current_episode = []
        
        # 网络
        if TORCH_AVAILABLE:
            self.policy_net = LSTMNetwork(self.state_dim, 128, self.action_dim)
            self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.learning_rate)
        else:
            self.policy_net = None
            self.optimizer = None
        
        # 训练统计
        self.training_stats = {
            "total_episodes": 0,
            "total_updates": 0,
            "policy_losses": [],
            "value_losses": [],
            "rewards": [],
        }
        
        logger.info("PPO trainer initialized")
    
    def add_experience(self, trade_record: Dict):
        """添加经验"""
        # 构建状态
        state = self._build_state(trade_record)
        
        # 确定动作
        action = self._trade_to_action(trade_record.get("action", "hold"))
        
        # 计算奖励
        reward = self._calculate_reward(trade_record)
        
        experience = {
            "state": state,
            "action": action,
            "reward": reward,
            "symbol": trade_record.get("symbol"),
            "timestamp": trade_record.get("timestamp"),
            "done": True,  # 交易完成后一个episode结束
        }
        
        self.current_episode.append(experience)
        
        # 交易完成，保存episode
        if trade_record.get("pnl") is not None:
            for exp in self.current_episode:
                exp["episode_reward"] = sum(e["reward"] for e in self.current_episode)
                self.experiences.append(exp)
            
            self.current_episode = []
            self.training_stats["total_episodes"] += 1
            self.training_stats["rewards"].append(reward)
    
    def has_enough_experiences(self) -> bool:
        """检查是否有足够经验"""
        return len(self.experiences) >= self.min_experiences
    
    def _build_state(self, trade_record: Dict) -> np.ndarray:
        """
        构建状态向量
        
        包含：
        - 市场特征
        - 持仓状态
        - 历史收益
        """
        factors = trade_record.get("factors", {})
        
        # 基础因子 (20维)
        base_features = [
            factors.get("mom_5m", 0),
            factors.get("mom_15m", 0),
            factors.get("mom_1h", 0),
            factors.get("rsi", 50) / 100,
            factors.get("macd", 0),
            factors.get("volatility_5m", 0),
            factors.get("volatility_15m", 0),
            factors.get("volume_ratio", 1),
            factors.get("bb_position", 0.5),
            factors.get("atr_ratio", 0),
            factors.get("price_momentum", 0),
            factors.get("trend_strength", 0),
            factors.get("support_distance", 0),
            factors.get("resistance_distance", 0),
            factors.get("ma_alignment", 0),
            factors.get("volume_trend", 0),
            factors.get("rsi_divergence", 0),
            factors.get("macd_divergence", 0),
            factors.get("market_regime", 0),  # 0:震荡, 1:趋势
            factors.get("liquidity_score", 0.5),
        ]
        
        # 持仓特征 (5维)
        position_features = [
            trade_record.get("signal_confidence", 0.5),
            trade_record.get("predicted_return", 0),
            1.0 if trade_record.get("action") == "buy" else 0.0,
            1.0 if trade_record.get("action") == "sell" else 0.0,
            1.0 if trade_record.get("action") == "hold" else 0.0,
        ]
        
        # 历史统计 (5维)
        recent_rewards = list(self.training_stats["rewards"])[-10:]
        history_features = [
            np.mean(recent_rewards) if recent_rewards else 0,
            np.std(recent_rewards) if len(recent_rewards) > 1 else 0,
            len(recent_rewards) / 10.0,
            self.training_stats["total_episodes"] / 1000.0,
            sum(1 for r in recent_rewards if r > 0) / max(len(recent_rewards), 1),
        ]
        
        state = base_features + position_features + history_features
        
        return np.array(state, dtype=np.float32)
    
    def _trade_to_action(self, action_str: str) -> int:
        """交易动作转数值"""
        action_map = {"buy": 0, "sell": 1, "hold": 2}
        return action_map.get(action_str, 2)
    
    def _action_to_trade(self, action: int) -> str:
        """数值转交易动作"""
        action_map = {0: "buy", 1: "sell", 2: "hold"}
        return action_map.get(action, "hold")
    
    def _calculate_reward(self, trade_record: Dict) -> float:
        """
        计算奖励
        
        奖励组成：
        - 基础收益
        - 夏普比率奖励
        - 风险控制奖励
        """
        pnl = trade_record.get("pnl", 0)
        pnl_pct = trade_record.get("pnl_pct", 0)
        holding_time = trade_record.get("holding_time", 0)
        
        # 基础收益奖励（归一化）
        base_reward = np.tanh(pnl_pct * 10)  # 将百分比收益映射到[-1, 1]
        
        # 夏普比率近似奖励
        if holding_time > 0:
            sharpe_like = pnl_pct / (np.sqrt(holding_time / 3600) + 0.01)
            sharpe_reward = np.tanh(sharpe_like)
        else:
            sharpe_reward = 0
        
        # 风险控制奖励（持仓时间惩罚）
        time_penalty = -0.01 * (holding_time / 3600)  # 每小时-0.01
        
        # 交易成本惩罚
        cost_penalty = -trade_record.get("transaction_cost", 0) / 100
        
        total_reward = base_reward * 0.5 + sharpe_reward * 0.3 + time_penalty + cost_penalty
        
        return float(total_reward)
    
    async def train(self) -> Dict:
        """
        执行PPO训练
        
        步骤：
        1. 采样经验
        2. 计算优势函数
        3. 更新策略
        4. 更新价值函数
        """
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available, returning mock result")
            return self._mock_train_result()
        
        try:
            logger.info(f"Training PPO with {len(self.experiences)} experiences")
            
            # 准备训练数据
            states, actions, rewards, next_states, dones = self._prepare_batch()
            
            if len(states) == 0:
                return {"status": "error", "error": "empty_batch"}
            
            # 计算回报和优势
            returns, advantages = self._compute_gae(rewards, states, next_states, dones)
            
            # 转换为tensor
            states_tensor = torch.FloatTensor(states)
            actions_tensor = torch.LongTensor(actions)
            returns_tensor = torch.FloatTensor(returns)
            advantages_tensor = torch.FloatTensor(advantages)
            
            # 旧策略概率（用于PPO clip）
            with torch.no_grad():
                old_probs, _, _ = self.policy_net(states_tensor)
                old_log_probs = torch.log(old_probs.gather(1, actions_tensor.unsqueeze(1)) + 1e-10)
            
            # 多次epoch更新
            total_policy_loss = 0
            total_value_loss = 0
            
            for epoch in range(self.epochs_per_update):
                # 策略前向
                action_probs, values, _ = self.policy_net(states_tensor)
                
                # 计算新策略概率
                new_log_probs = torch.log(action_probs.gather(1, actions_tensor.unsqueeze(1)) + 1e-10)
                
                # 计算比率
                ratio = torch.exp(new_log_probs.squeeze() - old_log_probs.squeeze())
                
                # PPO目标
                surr1 = ratio * advantages_tensor
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * advantages_tensor
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # 价值损失
                value_loss = nn.MSELoss()(values.squeeze(), returns_tensor)
                
                # 总损失
                loss = policy_loss + 0.5 * value_loss - 0.01 * (action_probs * torch.log(action_probs + 1e-10)).sum(dim=1).mean()
                
                # 反向传播
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 0.5)
                self.optimizer.step()
                
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
            
            # 保存模型
            self._save_model()
            
            # 更新统计
            self.training_stats["total_updates"] += 1
            self.training_stats["policy_losses"].append(total_policy_loss / self.epochs_per_update)
            self.training_stats["value_losses"].append(total_value_loss / self.epochs_per_update)
            
            # 计算策略改进
            avg_reward = np.mean([e["reward"] for e in list(self.experiences)[-100:]])
            policy_improvement = avg_reward - np.mean(self.training_stats["rewards"][-200:-100]) if len(self.training_stats["rewards"]) > 200 else 0
            
            logger.info(f"PPO training complete: policy_loss={total_policy_loss/self.epochs_per_update:.4f}, "
                       f"value_loss={total_value_loss/self.epochs_per_update:.4f}")
            
            return {
                "status": "success",
                "policy_loss": total_policy_loss / self.epochs_per_update,
                "value_loss": total_value_loss / self.epochs_per_update,
                "policy_improvement": policy_improvement,
                "avg_reward": avg_reward,
                "episodes_trained": self.training_stats["total_episodes"],
            }
        
        except Exception as e:
            logger.error(f"PPO training failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    def _prepare_batch(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """准备训练批次"""
        if len(self.experiences) < self.batch_size:
            batch = list(self.experiences)
        else:
            batch = random.sample(list(self.experiences), self.batch_size)
        
        states = np.array([e["state"] for e in batch])
        actions = np.array([e["action"] for e in batch])
        rewards = np.array([e["reward"] for e in batch])
        
        # next_states和dones（简化处理）
        next_states = states  # 实际应该取下一个状态
        dones = np.array([e.get("done", True) for e in batch], dtype=np.float32)
        
        return states, actions, rewards, next_states, dones
    
    def _compute_gae(self, rewards: np.ndarray, states: np.ndarray, 
                    next_states: np.ndarray, dones: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算广义优势估计 (Generalized Advantage Estimation)
        """
        if not TORCH_AVAILABLE or self.policy_net is None:
            returns = rewards
            advantages = rewards - rewards.mean()
            return returns, advantages
        
        with torch.no_grad():
            states_tensor = torch.FloatTensor(states)
            next_states_tensor = torch.FloatTensor(next_states)
            
            _, values, _ = self.policy_net(states_tensor)
            _, next_values, _ = self.policy_net(next_states_tensor)
            
            values = values.squeeze().numpy()
            next_values = next_values.squeeze().numpy()
        
        returns = np.zeros_like(rewards)
        advantages = np.zeros_like(rewards)
        gae = 0
        
        for t in reversed(range(len(rewards))):
            if dones[t]:
                delta = rewards[t] - values[t]
                gae = delta
            else:
                delta = rewards[t] + self.gamma * next_values[t] - values[t]
                gae = delta + self.gamma * self.gae_lambda * gae
            
            advantages[t] = gae
            returns[t] = gae + values[t]
        
        # 归一化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return returns, advantages
    
    def _save_model(self):
        """保存模型"""
        try:
            import os
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            torch.save({
                "policy_state_dict": self.policy_net.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "stats": self.training_stats,
            }, self.model_path)
            logger.info(f"PPO model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def predict(self, state: np.ndarray) -> Dict:
        """
        预测动作
        
        Returns:
            {
                "action": str,  # buy/sell/hold
                "action_prob": float,
                "value_estimate": float,
            }
        """
        if not TORCH_AVAILABLE or self.policy_net is None:
            # 随机策略
            action = random.choice(["buy", "sell", "hold"])
            return {
                "action": action,
                "action_prob": 0.33,
                "value_estimate": 0.0,
            }
        
        try:
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0)
                action_probs, value, _ = self.policy_net(state_tensor)
                
                probs = action_probs.squeeze().numpy()
                action_idx = np.argmax(probs)
                
                return {
                    "action": self._action_to_trade(action_idx),
                    "action_prob": float(probs[action_idx]),
                    "value_estimate": float(value.squeeze().item()),
                }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"action": "hold", "action_prob": 0.33, "value_estimate": 0.0}
    
    def _mock_train_result(self) -> Dict:
        """模拟训练结果"""
        return {
            "status": "mock",
            "policy_loss": np.random.uniform(0.1, 0.5),
            "value_loss": np.random.uniform(0.05, 0.3),
            "policy_improvement": np.random.uniform(-0.02, 0.05),
            "avg_reward": np.random.uniform(-0.1, 0.3),
            "episodes_trained": self.training_stats["total_episodes"],
        }
    
    def get_training_stats(self) -> Dict:
        """获取训练统计"""
        return {
            "total_episodes": self.training_stats["total_episodes"],
            "total_updates": self.training_stats["total_updates"],
            "avg_policy_loss": np.mean(self.training_stats["policy_losses"][-10:]) if self.training_stats["policy_losses"] else 0,
            "avg_value_loss": np.mean(self.training_stats["value_losses"][-10:]) if self.training_stats["value_losses"] else 0,
            "avg_reward": np.mean(self.training_stats["rewards"][-100:]) if self.training_stats["rewards"] else 0,
        }
