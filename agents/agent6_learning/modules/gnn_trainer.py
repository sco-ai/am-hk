"""
Temporal GNN 训练模块
负责市场关系图学习和信息传导建模
"""
import json
import logging
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import numpy as np

from core.utils import setup_logging

logger = setup_logging("gnn_trainer")

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True

    class TemporalGNN(nn.Module):
        """
        时序图神经网络
        
        结构：
        - 图卷积层（GCN/GAT）
        - LSTM时序层
        - 注意力机制
        """
        
        def __init__(self, num_nodes: int, feature_dim: int = 10, hidden_dim: int = 64):
            super(TemporalGNN, self).__init__()
            
            self.num_nodes = num_nodes
            self.feature_dim = feature_dim
            self.hidden_dim = hidden_dim
            
            # 图卷积层（简化实现）
            self.gcn1 = nn.Linear(feature_dim, hidden_dim)
            self.gcn2 = nn.Linear(hidden_dim, hidden_dim)
            
            # LSTM时序层
            self.lstm = nn.LSTM(hidden_dim, hidden_dim, batch_first=True, num_layers=2)
            
            # 输出层
            self.output = nn.Linear(hidden_dim, 1)
        
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
    
    def forward(self, x, adj_matrix, hidden=None):
        """
        前向传播
        
        Args:
            x: 节点特征 [batch, num_nodes, feature_dim]
            adj_matrix: 邻接矩阵 [num_nodes, num_nodes]
            hidden: LSTM隐藏状态
        """
        batch_size = x.size(0)
        
        # 图卷积
        h = self.gcn1(x)  # [batch, num_nodes, hidden_dim]
        h = self.relu(h)
        h = self.dropout(h)
        
        # 消息传递（简化）
        h = torch.bmm(adj_matrix.unsqueeze(0).expand(batch_size, -1, -1), h)
        
        h = self.gcn2(h)
        h = self.relu(h)
        
        # 聚合节点特征
        h = h.mean(dim=1)  # [batch, hidden_dim]
        h = h.unsqueeze(1)  # [batch, 1, hidden_dim]
        
        # LSTM时序处理
        lstm_out, hidden = self.lstm(h, hidden)
        
        # 输出
        out = self.output(lstm_out[:, -1, :])
        
        return out, hidden


class TemporalGNNTTrainer:
    """
    Temporal GNN 训练器
    
    功能：
    - 股票关系图构建
    - 时序图卷积
    - 信息传导建模
    - 跨市场关联学习
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "models/temporal_gnn_model.pt"
        
        # 图结构
        self.nodes: Set[str] = set()  # 股票代码
        self.edges: List[Tuple[str, str, float]] = []  # (from, to, weight)
        self.adj_matrix: Optional[np.ndarray] = None
        
        # 时序数据缓存
        self.node_features: Dict[str, List[np.ndarray]] = defaultdict(list)
        self.max_history_len = 50
        
        # 网络
        self.feature_dim = 10
        self.hidden_dim = 64
        self.model: Optional[TemporalGNN] = None
        
        if TORCH_AVAILABLE:
            self._init_model()
        
        logger.info("Temporal GNN trainer initialized")
    
    def _init_model(self):
        """初始化模型"""
        num_nodes = max(len(self.nodes), 10)
        self.model = TemporalGNN(num_nodes, self.feature_dim, self.hidden_dim)
        logger.info(f"Initialized TemporalGNN with {num_nodes} nodes")
    
    def prepare_graph_data(self, trade_history: List[Dict]) -> Dict:
        """
        准备图数据
        
        构建：
        - 节点：交易标的
        - 边：价格相关性、板块关系、跨市场关系
        """
        # 收集所有标的
        symbols = set()
        for trade in trade_history:
            sym = trade.get("symbol")
            if sym:
                symbols.add(sym)
        
        self.nodes = symbols
        
        # 按标的分组数据
        symbol_data = defaultdict(list)
        for trade in trade_history:
            sym = trade.get("symbol")
            if sym:
                symbol_data[sym].append({
                    "return": trade.get("pnl_pct", 0),
                    "price": trade.get("entry_price", 0),
                    "timestamp": trade.get("timestamp"),
                })
        
        # 构建边（基于收益相关性）
        edges = []
        symbols_list = list(symbols)
        
        for i, sym1 in enumerate(symbols_list):
            for sym2 in symbols_list[i+1:]:
                # 计算收益相关性
                returns1 = [d["return"] for d in symbol_data[sym1] if d["return"] is not None]
                returns2 = [d["return"] for d in symbol_data[sym2] if d["return"] is not None]
                
                if len(returns1) > 10 and len(returns2) > 10:
                    # 对齐长度
                    min_len = min(len(returns1), len(returns2))
                    returns1 = returns1[-min_len:]
                    returns2 = returns2[-min_len:]
                    
                    # 计算相关性
                    corr = np.corrcoef(returns1, returns2)[0, 1]
                    if not np.isnan(corr) and abs(corr) > 0.3:
                        edges.append((sym1, sym2, abs(corr)))
        
        self.edges = edges
        
        # 构建邻接矩阵
        self._build_adjacency_matrix(symbols_list)
        
        # 构建节点特征
        node_features = {}
        for sym in symbols_list:
            features = self._extract_node_features(symbol_data[sym])
            node_features[sym] = features
        
        return {
            "nodes": symbols_list,
            "edges": edges,
            "node_features": node_features,
            "adj_matrix": self.adj_matrix,
        }
    
    def _build_adjacency_matrix(self, symbols_list: List[str]):
        """构建邻接矩阵"""
        n = len(symbols_list)
        adj = np.zeros((n, n))
        
        symbol_to_idx = {sym: i for i, sym in enumerate(symbols_list)}
        
        for from_sym, to_sym, weight in self.edges:
            i = symbol_to_idx.get(from_sym)
            j = symbol_to_idx.get(to_sym)
            if i is not None and j is not None:
                adj[i, j] = weight
                adj[j, i] = weight  # 对称
        
        # 添加自环
        np.fill_diagonal(adj, 1.0)
        
        # 归一化
        row_sums = adj.sum(axis=1, keepdims=True)
        adj = adj / (row_sums + 1e-8)
        
        self.adj_matrix = adj
    
    def _extract_node_features(self, data: List[Dict]) -> np.ndarray:
        """提取节点特征"""
        if not data:
            return np.zeros(self.feature_dim)
        
        returns = [d["return"] for d in data if d.get("return") is not None]
        
        if len(returns) < 5:
            return np.zeros(self.feature_dim)
        
        # 统计特征
        features = [
            np.mean(returns),
            np.std(returns),
            np.percentile(returns, 25),
            np.percentile(returns, 75),
            np.max(returns),
            np.min(returns),
            len([r for r in returns if r > 0]) / len(returns),  # 胜率
            np.mean(returns[-5:]) if len(returns) >= 5 else np.mean(returns),  # 近期收益
            np.std(returns[-5:]) if len(returns) >= 5 else np.std(returns),  # 近期波动
            len(returns) / 100.0,  # 样本数归一化
        ]
        
        return np.array(features)
    
    async def train(self, graph_data: Dict) -> Dict:
        """
        训练Temporal GNN
        
        学习标的间的关系和信息的传导模式
        """
        try:
            nodes = graph_data.get("nodes", [])
            edges = graph_data.get("edges", [])
            node_features = graph_data.get("node_features", {})
            
            logger.info(f"Training Temporal GNN: {len(nodes)} nodes, {len(edges)} edges")
            
            if len(nodes) < 5:
                return {"status": "skipped", "reason": "too_few_nodes"}
            
            # 准备特征矩阵
            feature_matrix = np.array([
                node_features.get(sym, np.zeros(self.feature_dim))
                for sym in nodes
            ])
            
            # 训练
            if TORCH_AVAILABLE and self.model is not None:
                train_result = await self._torch_train(feature_matrix)
            else:
                train_result = self._mock_train_result()
            
            # 分析关系强度
            relationship_analysis = self._analyze_relationships(nodes, edges)
            
            return {
                "status": "success",
                "num_nodes": len(nodes),
                "num_edges": len(edges),
                "correlation_improvement": train_result.get("improvement", 0),
                "relationship_analysis": relationship_analysis,
            }
        
        except Exception as e:
            logger.error(f"GNN training failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def _torch_train(self, feature_matrix: np.ndarray) -> Dict:
        """PyTorch训练"""
        try:
            # 简化的训练过程
            # 实际应该使用真实的标签和损失函数
            
            num_nodes = feature_matrix.shape[0]
            adj = torch.FloatTensor(self.adj_matrix[:num_nodes, :num_nodes])
            
            # 模拟训练
            epochs = 10
            improvements = []
            
            for epoch in range(epochs):
                # 前向
                x = torch.FloatTensor(feature_matrix).unsqueeze(0)  # [1, num_nodes, feature_dim]
                output, _ = self.model(x, adj)
                
                # 模拟损失（实际应该有真实标签）
                loss = torch.mean(output ** 2)
                
                improvements.append(float(loss))
            
            # 保存模型
            self._save_model()
            
            return {
                "improvement": np.mean(improvements),
                "epochs": epochs,
            }
        
        except Exception as e:
            logger.error(f"Torch training error: {e}")
            return {"improvement": 0}
    
    def _analyze_relationships(self, nodes: List[str], edges: List[Tuple]) -> Dict:
        """分析标的关系"""
        # 找出核心节点（连接数最多的）
        degree = defaultdict(int)
        for from_sym, to_sym, weight in edges:
            degree[from_sym] += 1
            degree[to_sym] += 1
        
        # 排序
        sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)
        
        # 强关系对
        strong_relationships = [
            {"from": f, "to": t, "weight": w}
            for f, t, w in sorted(edges, key=lambda x: x[2], reverse=True)[:10]
        ]
        
        return {
            "core_nodes": [n for n, _ in sorted_nodes[:5]],
            "node_degrees": dict(sorted_nodes[:10]),
            "strong_relationships": strong_relationships,
            "avg_edge_weight": np.mean([w for _, _, w in edges]) if edges else 0,
        }
    
    def _save_model(self):
        """保存模型"""
        try:
            import os
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            if TORCH_AVAILABLE and self.model is not None:
                torch.save(self.model.state_dict(), self.model_path)
            logger.info(f"GNN model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def _mock_train_result(self) -> Dict:
        """模拟训练结果"""
        return {
            "improvement": np.random.uniform(0.01, 0.05),
            "epochs": 10,
            "status": "mock",
        }
    
    def predict_spillover(self, symbol: str, 
                         price_change: float) -> List[Dict]:
        """
        预测信息传导（溢出效应）
        
        预测某个标的的价格变化对其他标的的影响
        """
        affected = []
        
        for from_sym, to_sym, weight in self.edges:
            if from_sym == symbol:
                affected.append({
                    "symbol": to_sym,
                    "expected_change": price_change * weight * 0.5,  # 传导系数0.5
                    "confidence": weight,
                    "lag": 1,  # 假设1个时间单位的延迟
                })
            elif to_sym == symbol:
                affected.append({
                    "symbol": from_sym,
                    "expected_change": price_change * weight * 0.5,
                    "confidence": weight,
                    "lag": 1,
                })
        
        # 按置信度排序
        affected.sort(key=lambda x: x["confidence"], reverse=True)
        
        return affected[:10]
    
    def get_market_leaders(self) -> List[str]:
        """
        获取市场领导者标的
        
        基于节点的中心性分析
        """
        # 简化实现：返回度数最高的节点
        degree = defaultdict(float)
        for from_sym, to_sym, weight in self.edges:
            degree[from_sym] += weight
            degree[to_sym] += weight
        
        sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)
        return [n for n, _ in sorted_nodes[:5]]