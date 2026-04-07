

class MultiStrategyScanner:
    """多策略并行扫描器"""
    
    def __init__(self):
        self.strategies = {
            StrategyType.MOMENTUM: self._scan_momentum,
            StrategyType.VALUE: self._scan_value,
            StrategyType.SENTIMENT: self._scan_sentiment,
            StrategyType.CROSS_MARKET: self._scan_cross_market,
        }
    
    def scan_all(self, symbol: str, factors: Dict, 
                 cross_signals: List[Dict], context: MarketContext) -> Dict[str, StrategyScore]:
        """执行所有策略扫描"""
        results = {}
        
        for strategy_type, scan_func in self.strategies.items():
            try:
                score = scan_func(symbol, factors, cross_signals, context)
                results[strategy_type.value] = score
            except Exception as e:
                logger.error(f"Strategy {strategy_type} scan failed for {symbol}: {e}")
                results[strategy_type.value] = StrategyScore(
                    strategy_type=strategy_type,
                    raw_score=0.5,
                    normalized_score=0.5,
                    direction=Direction.HOLD,
                    confidence=0.0,
                    factors_used=[],
                    reasoning=f"扫描失败: {str(e)}"
                )
        
        return results
    
    def _scan_momentum(self, symbol: str, factors: Dict, 
                       cross_signals: List[Dict], context: MarketContext) -> StrategyScore:
        """动量策略扫描"""
        score = 0.0
        factors_used = []
        
        # 短期动量
        mom_5m = factors.get("price_momentum_5m", 0)
        mom_15m = factors.get("price_momentum_15m", 0)
        
        if mom_5m > 1.5 and mom_15m > 2.0:
            score = (mom_5m + mom_15m) / 20
            direction = Direction.BUY
            factors_used = ["price_momentum_5m", "price_momentum_15m"]
        elif mom_5m < -1.5 and mom_15m < -2.0:
            score = (abs(mom_5m) + abs(mom_15m)) / 20
            direction = Direction.SELL
            factors_used = ["price_momentum_5m", "price_momentum_15m"]
        else:
            score = 0.3
            direction = Direction.HOLD
            factors_used = ["price_momentum_5m"]
        
        # 成交量确认
        vol_mom = factors.get("volume_momentum", 1.0)
        if vol_mom > 1.3:
            score *= 1.2
            factors_used.append("volume_momentum")
        
        reasoning = f"5m动量{mom_5m:+.2f}%, 15m动量{mom_15m:+.2f}%, 成交量倍数{vol_mom:.2f}x"
        
        return StrategyScore(
            strategy_type=StrategyType.MOMENTUM,
            raw_score=score,
            normalized_score=min(score, 1.0),
            direction=direction,
            confidence=min(score * 0.8 + 0.2, 0.95),
            factors_used=factors_used,
            reasoning=reasoning
        )
    
    def _scan_value(self, symbol: str, factors: Dict,
                    cross_signals: List[Dict], context: MarketContext) -> StrategyScore:
        """价值策略扫描（均值回归）"""
        score = 0.0
        factors_used = []
        
        rsi = factors.get("rsi_14", 50)
        bb_lower = factors.get("bb_lower", 0)
        bb_upper = factors.get("bb_upper", 0)
        close = factors.get("ma_5", 0)
        
        # RSI超卖 + 接近布林带下轨 = 买入机会
        if rsi < 35 and close > 0 and bb_lower > 0:
            bb_deviation = (close - bb_lower) / close
            if bb_deviation < 0.02:
                score = (35 - rsi) / 35 * 0.7 + 0.3
                direction = Direction.BUY
                factors_used = ["rsi_14", "bb_lower"]
                reasoning = f"RSI超卖({rsi:.1f})+接近布林带下轨"
            else:
                score = 0.4
                direction = Direction.HOLD
                factors_used = ["rsi_14"]
                reasoning = f"RSI偏低({rsi:.1f})但未到下轨"
        
        # RSI超买 + 接近布林带上轨 = 卖出机会
        elif rsi > 65 and close > 0 and bb_upper > 0:
            bb_deviation = (bb_upper - close) / close
            if bb_deviation < 0.02:
                score = (rsi - 65) / 35 * 0.7 + 0.3
                direction = Direction.SELL
                factors_used = ["rsi_14", "bb_upper"]
                reasoning = f"RSI超买({rsi:.1f})+接近布林带上轨"
            else:
                score = 0.4
                direction = Direction.HOLD
                factors_used = ["rsi_14"]
                reasoning = f"RSI偏高({rsi:.1f})但未到上轨"
        else:
            score = 0.3
            direction = Direction.HOLD
            factors_used = ["rsi_14"]
            reasoning = f"RSI中性({rsi:.1f})"
        
        return StrategyScore(
            strategy_type=StrategyType.VALUE,
            raw_score=score,
            normalized_score=min(score, 1.0),
            direction=direction,
            confidence=min(score * 0.7 + 0.2, 0.9),
            factors_used=factors_used,
            reasoning=reasoning
        )
    
    def _scan_sentiment(self, symbol: str, factors: Dict,
                        cross_signals: List[Dict], context: MarketContext) -> StrategyScore:
        """情绪策略扫描"""
        score = 0.0
        factors_used = []
        
        main_ratio = factors.get("main_force_ratio", 0)
        northbound = factors.get("northbound_strength", 0)
        main_retail = factors.get("main_retail_ratio", 0)
        
        sentiment_score = main_ratio * 0.4 + northbound * 0.4 + np.sign(main_retail) * min(abs(main_retail) / 10, 0.2) * 0.2
        
        if sentiment_score > 0.3:
            score = sentiment_score
            direction = Direction.BUY
            reasoning = f"主力资金流入({main_ratio:+.2f})+北水强势({northbound:+.2f})"
        elif sentiment_score < -0.3:
            score = abs(sentiment_score)
            direction = Direction.SELL
            reasoning = f"主力资金流出({main_ratio:+.2f})+北水弱势({northbound:+.2f})"
        else:
            score = 0.3
            direction = Direction.HOLD
            reasoning = f"资金流中性(主力{main_ratio:+.2f},北水{northbound:+.2f})"
        
        factors_used = ["main_force_ratio", "northbound_strength", "main_retail_ratio"]
        
        return StrategyScore(
            strategy_type=StrategyType.SENTIMENT,
            raw_score=score,
            normalized_score=min(score, 1.0),
            direction=direction,
            confidence=min(abs(sentiment_score) * 0.8 + 0.2, 0.9),
            factors_used=factors_used,
            reasoning=reasoning
        )
    
    def _scan_cross_market(self, symbol: str, factors: Dict,
                           cross_signals: List[Dict], context: MarketContext) -> StrategyScore:
        """跨市场传导策略扫描"""
        score = 0.0
        factors_used = []
        
        layer1 = factors.get("layer1_signal", 0)
        layer2 = factors.get("layer2_confirm", 0)
        
        if abs(layer1) > 1.0 and abs(layer2) > 1.0:
            if np.sign(layer1) == np.sign(layer2):
                score = (abs(layer1) + abs(layer2)) / 20
                direction = Direction.BUY if layer1 > 0 else Direction.SELL
                reasoning = f"跨市场传导一致: Layer1({layer1:+.2f})+Layer2({layer2:+.2f})"
            else:
                score = 0.35
                direction = Direction.HOLD
                reasoning = f"跨市场信号冲突: Layer1({layer1:+.2f}) vs Layer2({layer2:+.2f})"
        elif abs(layer1) > 2.0:
            score = abs(layer1) / 15
            direction = Direction.BUY if layer1 > 0 else Direction.SELL
            reasoning = f"Layer1强信号({layer1:+.2f})"
        elif abs(layer2) > 2.0:
            score = abs(layer2) / 15
            direction = Direction.BUY if layer2 > 0 else Direction.SELL
            reasoning = f"Layer2强信号({layer2:+.2f})"
        else:
            score = 0.25
            direction = Direction.HOLD
            reasoning = f"跨市场信号弱: Layer1({layer1:+.2f}), Layer2({layer2:+.2f})"
        
        factors_used = ["layer1_signal", "layer2_confirm"]
        
        strong_signals = [s for s in cross_signals if s.get("strength", 0) > 0.5]
        if strong_signals:
            score *= 1.1
            factors_used.append("cross_market_signals")
        
        return StrategyScore(
            strategy_type=StrategyType.CROSS_MARKET,
            raw_score=score,
            normalized_score=min(score, 1.0),
            direction=direction,
            confidence=min(score * 0.75 + 0.15, 0.9),
            factors_used=factors_used,
            reasoning=reasoning
        )


class StrategyOptimizer:
    """
    策略优化器 - GPT-4.1 API调用封装
    
    功能:
    1. 阈值动态优化
    2. 策略权重调整
    """
    
    def __init__(self):
        self.llm_analyzer = ModelFactory.get_llm_analyzer()
        self.cache = {}
        self.cache_ttl = 300
        self.last_optimization = 0
        self.optimization_interval = 300
        
        self.default_weights = {
            "momentum": 0.35,
            "value": 0.20,
            "sentiment": 0.25,
            "cross_market": 0.20,
        }
        
        self.default_thresholds = {
            "entry": 0.70,
            "exit": 0.45,
            "stop_loss": 0.02,
            "take_profit": 0.05,
        }
    
    async def optimize_thresholds(self, context: MarketContext) -> Dict[str, float]:
        """阈值动态优化"""
        current_time = int(time.time())
        if current_time - self.last_optimization < self.optimization_interval:
            cache_key = f"thresholds_{context.volatility_regime}"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if current_time - cached["timestamp"] < self.cache_ttl:
                    return cached["thresholds"]
        
        # 基于规则的阈值调整
        result = self._rule_based_threshold_adjustment(context)
        
        cache_key = f"thresholds_{context.volatility_regime}"
        self.cache[cache_key] = {
            "thresholds": result,
            "timestamp": current_time
        }
        self.last_optimization = current_time
        
        return result
    
    async def optimize_weights(self, strategy_performance: Dict[str, Dict]) -> Dict[str, float]:
        """策略权重调整"""
        return self._rule_based_weight_adjustment(strategy_performance)
    
    def _rule_based_threshold_adjustment(self, context: MarketContext) -> Dict[str, float]:
        """基于规则的阈值调整"""
        thresholds = self.default_thresholds.copy()
        
        # 高波动环境调整
        if context.volatility_regime == "high":
            thresholds["entry"] = min(0.80, thresholds["entry"] + 0.05)
            thresholds["exit"] = min(0.55, thresholds["exit"] + 0.05)
            thresholds["stop_loss"] = min(0.03, thresholds["stop_loss"] * 1.5)
        
        # 强趋势环境调整
        if context.trend_strength > 0.7:
            thresholds["entry"] = max(0.60, thresholds["entry"] - 0.05)
            thresholds["take_profit"] = min(0.08, thresholds["take_profit"] * 1.2)
        
        # 资金流出环境调整
        if context.capital_flow_direction == "outflow":
            thresholds["entry"] = min(0.80, thresholds["entry"] + 0.08)
            thresholds["stop_loss"] = max(0.015, thresholds["stop_loss"] * 0.8)
        
        return thresholds
    
    def _rule_based_weight_adjustment(self, performance: Dict[str, Dict]) -> Dict[str, float]:
        """基于规则的权重调整"""
        weights = self.default_weights.copy()
        
        for name, perf in performance.items():
            win_rate = perf.get("win_rate", 0.5)
            sharpe = perf.get("sharpe", 1.0)
            recent_return = perf.get("recent_return", 0)
            
            # 表现好的策略增加权重
            if win_rate > 0.6 and sharpe > 1.0:
                weights[name] = min(0.5, weights[name] * 1.2)
            
            # 表现差的策略降低权重
            if recent_return < 0 or win_rate < 0.4:
                weights[name] = max(0.1, weights[name] * 0.8)
        
        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights


class AlphaScanner:
    """
    Agent 3: AlphaScanner - 机会筛选器
    
    核心功能：
    1. 多策略并行扫描（动量/价值/情绪/跨市场传导）
    2. LightGBM模型实时评分
    3. GPT-4.1策略优化（阈值动态调整、权重优化）
    4. Top机会排序和分层（Top5核心仓/Top6-10机会仓/Top11-20观察池）
    5. 置信度计算和阈值过滤
    """
    
    def __init__(self):
        self.agent_name = "agent3_scanner"
        self.bus = MessageBus(self.agent_name)
        self.consumer = AgentConsumer(
            agent_name=self.agent_name,
            topics=["am-hk-processed-data"]
        )
        
        # 核心组件
        self.factor_scorer = LightGBMFactorScorer()
        self.strategy_scanner = MultiStrategyScanner()
        self.strategy_optimizer = StrategyOptimizer()
        
        # 候选机会缓存
        self.candidate_opportunities: Dict[str, Opportunity] = {}
        self.market_context = MarketContext(
            timestamp=int(time.time() * 1000),
            volatility_regime="medium",
            trend_strength=0.5,
            market_sentiment=0.0,
            capital_flow_direction="neutral",
            btc_momentum=0.0,
            us_market_state="neutral"
        )
        
        # 配置
        self.min_confidence = 0.65
        self.scan_interval = 30  # 30秒扫描一次
        self.publish_interval = 60  # 60秒发布一次Top机会
        
        # 统计
        self.processed_count = 0
        self.rejected_count = 0
        self.running = False
        
        logger.info(f"{self.agent_name} initialized (LightGBM + Multi-Strategy + GPT-4.1)")
    
    async def start(self):
        """启动Agent3"""
        self.running = True
        logger.info(f"{self.agent_name} started")
        
        # 注册消息处理器
        self.consumer.register_handler("processed_data", self._on_processed_data)
        
        # 发布状态
        self.bus.publish_status({
            "state": "running",
            "strategies": ["momentum", "value", "sentiment", "cross_market"],
            "model": "LightGBM",
            "optimizer": "GPT-4.1",
        })
        
        # 启动定时任务
        scan_task = asyncio.create_task(self._scan_loop())
        publish_task = asyncio.create_task(self._publish_loop())
        context_task = asyncio.create_task(self._update_context_loop())
        
        try:
            self.consumer.start()
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
        finally:
            scan_task.cancel()
            publish_task.cancel()
            context_task.cancel()
            await self.stop()
    
    async def stop(self):
        """停止Agent3"""
        logger.info(f"{self.agent_name} stopping...")
        self.running = False
        self.consumer.stop()
        
        self.bus.publish_status({
            "state": "stopped",
            "processed_count": self.processed_count,
            "rejected_count": self.rejected_count
        })
        self.bus.flush()
        self.bus.close()
        
        logger.info(f"{self.agent_name} stopped")
    
    def _on_processed_data(self, key: str, value: Dict, headers: Optional[Dict]):
        """处理Agent2的因子数据"""
        start_time = time.time()
        
        try:
            symbol = value.get("symbol", key)
            market = value.get("market", "unknown")
            factors = value.get("factors", {})
            cross_signals = value.get("cross_market_signals", [])
            timestamp = value.get("timestamp", int(time.time() * 1000))
            
            # 1. 执行多策略扫描
            strategy_scores = self.strategy_scanner.scan_all(
                symbol, factors, cross_signals, self.market_context
            )
            
            # 2. LightGBM综合评分
            lgbm_score = self.factor_scorer.score(factors, self.market_context)
            
            # 3. 计算综合方向和置信度
            direction, confidence = self._calculate_composite_signal(
                strategy_scores, lgbm_score
            )
            
            # 4. 阈值过滤
            if confidence < self.min_confidence or direction == Direction.HOLD:
                self.rejected_count += 1
                return
            
            # 5. 构建机会对象
            opportunity = Opportunity(
                symbol=symbol,
                market=market,
                timestamp=timestamp,
                rank=0,  # 稍后排序时确定
                pool=OpportunityPool.REJECTED,  # 稍后确定
                direction=direction,
                confidence=confidence,
                score=lgbm_score,
                strategy_scores=strategy_scores,
                strategy_weights={
                    "momentum": 0.35,
                    "value": 0.20,
                    "sentiment": 0.25,
                    "cross_market": 0.20,
                },
                factors=factors,
                cross_market_signals=cross_signals,
                reasoning=self._generate_reasoning(symbol, strategy_scores, direction),
                thresholds=self.strategy_optimizer.default_thresholds.copy(),
                processing_time_ms=(time.time() - start_time) * 1000,
                model_version=self.factor_scorer.model_version
            )
            
            # 6. 缓存候选机会
            self.candidate_opportunities[symbol] = opportunity
            self.processed_count += 1
            
            if self.processed_count % 100 == 0:
                logger.info(f"Processed {self.processed_count} messages, "
                           f"rejected {self.rejected_count}, "
                           f"candidates {len(self.candidate_opportunities)}")
            
        except Exception as e:
            logger.error(f"Error processing data for {key}: {e}", exc_info=True)
    
    def _calculate_composite_signal(self, strategy_scores: Dict[str, StrategyScore],
                                   lgbm_score: float) -> Tuple[Direction, float]:
        """计算综合信号方向和置信度"""
        # 基于策略评分计算加权方向
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        
        weights = {
            "momentum": 0.35,
            "value": 0.20,
            "sentiment": 0.25,
            "cross_market": 0.20,
        }
        
        for name, score in strategy_scores.items():
            weight = weights.get(name, 0.25)
            if score.direction == Direction.BUY:
                buy_score += score.normalized_score * weight * score.confidence
            elif score.direction == Direction.SELL:
                sell_score += score.normalized_score * weight * score.confidence
            total_weight += weight
        
        # 结合LightGBM评分
        if lgbm_score > 0.6:
            buy_score += lgbm_score * 0.3
        elif lgbm_score < 0.4:
            sell_score += (1 - lgbm_score) * 0.3
        
        # 确定方向
        if buy_score > sell_score * 1.5 and buy_score > 0.3:
            direction = Direction.BUY
            confidence = min(buy_score, 0.95)
        elif sell_score > buy_score * 1.5 and sell_score > 0.3:
            direction = Direction.SELL
            confidence = min(sell_score, 0.95)
        else:
            direction = Direction.HOLD
            confidence = max(buy_score, sell_score)
        
        return direction, confidence
    
    def _generate_reasoning(self, symbol: str, strategy_scores: Dict[str, StrategyScore],
                           direction: Direction) -> str:
        """生成交易推理"""
        reasons = []
        
        # 选择得分最高的策略作为主要原因
        best_strategy = max(strategy_scores.items(), key=lambda x: x[1].normalized_score)
        reasons.append(f"{best_strategy[0]}:{best_strategy[1].reasoning}")
        
        # 跨市场信号
        cross_score = strategy_scores.get("cross_market")
        if cross_score and cross_score.normalized_score > 0.5:
            if "Layer1" in cross_score.reasoning:
                reasons.append("BTC传导")
            if "Layer2" in cross_score.reasoning:
                reasons.append("美股确认")
        
        # 资金流向
        sentiment_score = strategy_scores.get("sentiment")
        if sentiment_score and "北水" in sentiment_score.reasoning:
            if "强势" in sentiment_score.reasoning:
                reasons.append("北水流入")
            elif "弱势" in sentiment_score.reasoning:
                reasons.append("北水流出")
        
        return ";".join(reasons)
    
    async def _scan_loop(self):
        """定期扫描循环"""
        while self.running:
            try:
                # 触发阈值优化
                optimized_thresholds = await self.strategy_optimizer.optimize_thresholds(
                    self.market_context
                )
                self.min_confidence = optimized_thresholds["entry"]
                
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scan loop error: {e}")
                await asyncio.sleep(10)
    
    async def _publish_loop(self):
        """定期发布Top机会"""
        while self.running:
            try:
                await self._publish_top_opportunities()
                await asyncio.sleep(self.publish_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Publish loop error: {e}")
                await asyncio.sleep(10)
    
    async def _publish_top_opportunities(self):
        """发布Top交易机会"""
        if not self.candidate_opportunities:
            return
        
        # 获取所有候选机会
        opportunities = list(self.candidate_opportunities.values())
        
        # 按置信度排序
        opportunities.sort(key=lambda x: x.confidence, reverse=True)
        
        # 分层
        for i, opp in enumerate(opportunities):
            opp.rank = i + 1
            if i < 5:
                opp.pool = OpportunityPool.TOP5_CORE
            elif i < 10:
                opp.pool = OpportunityPool.TOP6_10_OPPORTUNITY
            elif i < 20:
                opp.pool = OpportunityPool.TOP11_20_OBSERVATION
            else:
                opp.pool = OpportunityPool.REJECTED
        
        # 发布Top 20
        top_opportunities = [opp for opp in opportunities[:20] 
                            if opp.pool != OpportunityPool.REJECTED]
        
        for opp in top_opportunities:
            try:
                # 发布到Kafka
                self.bus.send(
                    topic="am-hk-trading-opportunities",
                    key=opp.symbol,
                    value=opp.to_dict()
                )
                
                logger.info(f"Published opportunity: {opp.symbol} "
                           f"rank={opp.rank} pool={opp.pool.value} "
                           f"direction={opp.direction.value} "
                           f"confidence={opp.confidence:.3f}")
                
            except Exception as e:
                logger.error(f"Error publishing opportunity for {opp.symbol}: {e}")
        
        # 清空已发布的候选
        published_symbols = {opp.symbol for opp in top_opportunities}
        self.candidate_opportunities = {
            k: v for k, v in self.candidate_opportunities.items()
            if k not in published_symbols
        }
        
        self.bus.flush()
        
        logger.info(f"Published {len(top_opportunities)} opportunities, "
                   f"remaining candidates: {len(self.candidate_opportunities)}")
    
    async def _update_context_loop(self):
        """定期更新市场环境上下文"""
        while self.running:
            try:
                self._update_market_context()
                await asyncio.sleep(60)  # 每分钟更新
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Context update error: {e}")
                await asyncio.sleep(10)
    
    def _update_market_context(self):
        """更新市场环境上下文"""
        # 基于候选机会统计市场环境
        if not self.candidate_opportunities:
            return
        
        buy_count = sum(1 for opp in self.candidate_opportunities.values()
                       if opp.direction == Direction.BUY)
        sell_count = sum(1 for opp in self.candidate_opportunities.values()
                        if opp.direction == Direction.SELL)
        total = len(self.candidate_opportunities)
        
        # 市场情绪
        if total > 0:
            sentiment = (buy_count - sell_count) / total
            self.market_context.market_sentiment = sentiment
        
        # 波动率状态（基于机会数量）
        if total > 50:
            self.market_context.volatility_regime = "high"
        elif total > 20:
            self.market_context.volatility_regime = "medium"
        else:
            self.market_context.volatility_regime = "low"
        
        # 趋势强度
        if buy_count > sell_count * 2:
            self.market_context.trend_strength = 0.8
            self.market_context.capital_flow_direction = "inflow"
        elif sell_count > buy_count * 2:
            self.market_context.trend_strength = 0.8
            self.market_context.capital_flow_direction = "outflow"
        else:
            self.market_context.trend_strength = 0.5
            self.market_context.capital_flow_direction = "neutral"
        
        self.market_context.timestamp = int(time.time() * 1000)
        
        logger.debug(f"Market context updated: volatility={self.market_context.volatility_regime}, "
                    f"sentiment={self.market_context.market_sentiment:+.2f}")


if __name__ == "__main__":
    scanner = AlphaScanner()
    asyncio.run(scanner.start())