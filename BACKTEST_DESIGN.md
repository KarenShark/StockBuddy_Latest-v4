# 回测与策略库设计方案
# Backtesting & Strategy Library Design

## 🎯 设计目标

1. **与 Multi-Agent 系统无缝集成** - Agents 生成策略 → 回测验证 → 优化迭代
2. **港股市场特性支持** - T+2、交易成本、港股通限制
3. **高质量可靠** - 准确的历史数据、严格的回测引擎
4. **可扩展** - 支持多种策略类型和参数
5. **易用性** - 清晰的 API 和可视化报告

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Multi-Agent Analysis                     │
│  (Market/News/Fundamentals/Sentiment Analysts)              │
└───────────────────────┬─────────────────────────────────────┘
                        │ 生成交易信号和策略建议
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Strategy Library                          │
│  - Strategy Definition (策略定义)                            │
│  - Strategy Parameters (参数配置)                            │
│  - Strategy Templates (策略模板)                             │
└───────────────────────┬─────────────────────────────────────┘
                        │ 策略实例化
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backtesting Engine                          │
│  - Historical Data (历史数据)                                │
│  - Execution Simulator (执行模拟器)                          │
│  - Market Rules (市场规则: T+2, 成本)                        │
│  - Performance Metrics (性能指标)                            │
└───────────────────────┬─────────────────────────────────────┘
                        │ 回测结果
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Results & Optimization                      │
│  - Performance Report (绩效报告)                             │
│  - Risk Analysis (风险分析)                                  │
│  - Strategy Comparison (策略对比)                            │
│  - Parameter Optimization (参数优化)                         │
└─────────────────────────────────────────────────────────────┘
                        │ 反馈到 Agents
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Agent Memory & Learning                         │
│  - 记录成功/失败的策略                                        │
│  - 优化决策逻辑                                               │
│  - 持续改进                                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 策略库 (Strategy Library)

### 1. 策略分类

#### **基于信号类型**
- **技术指标策略** (Technical)
  - 均线交叉 (MA Crossover)
  - MACD 信号
  - RSI 超买超卖
  - 布林带突破
  
- **基本面策略** (Fundamental)
  - 价值投资 (P/E, P/B)
  - 成长投资 (营收增长率)
  - 股息投资 (高股息率)
  
- **情绪策略** (Sentiment)
  - 新闻情绪驱动
  - 社交媒体情绪
  - 分析师评级变化
  
- **混合策略** (Hybrid)
  - Multi-Agent 综合决策
  - 多因子模型

#### **基于持有期**
- **日内交易** (Day Trading) - 当日平仓
- **短线交易** (Swing Trading) - 数天至数周
- **中线投资** (Position Trading) - 数周至数月
- **长线投资** (Buy & Hold) - 数月至数年

---

### 2. 策略定义规范

```python
class BaseStrategy:
    """策略基类"""
    
    # 元数据
    name: str  # 策略名称
    description: str  # 策略描述
    category: str  # 策略分类
    holding_period: str  # 持有期类型
    
    # 参数
    parameters: Dict[str, Any]  # 可调参数
    
    # 市场要求
    required_data: List[str]  # 需要的数据 (OHLCV, indicators, news, etc.)
    min_lookback: int  # 最小回溯期
    
    # 方法
    def initialize(self):
        """初始化策略"""
        
    def generate_signals(self, data) -> Signal:
        """生成交易信号"""
        
    def calculate_position_size(self, capital, signal) -> float:
        """计算仓位大小"""
        
    def should_exit(self, position) -> bool:
        """判断是否退出"""
```

---

### 3. Agent-Generated Strategies

**核心思路：** Agents 的分析报告自动转换为可回测的策略

```python
class AgentStrategy(BaseStrategy):
    """基于 Agent 决策的策略"""
    
    def __init__(self, agent_decision: Dict):
        """
        Args:
            agent_decision: {
                'action': 'BUY' | 'SELL' | 'HOLD',
                'confidence': 0.0-1.0,
                'reasoning': str,
                'target_price': float,
                'stop_loss': float,
                'holding_period': int (days),
                'position_size': float (0-1, 资金比例)
            }
        """
        self.decision = agent_decision
        
    def generate_signals(self, date, current_price):
        """根据 Agent 决策生成信号"""
        if self.decision['action'] == 'BUY':
            return BuySignal(
                price=current_price,
                size=self.decision['position_size'],
                stop_loss=self.decision['stop_loss'],
                target=self.decision['target_price']
            )
        # ...
```

---

## 🔧 回测引擎 (Backtesting Engine)

### 1. 核心组件

#### **数据管理**
```python
class DataManager:
    """历史数据管理"""
    
    def get_stock_data(ticker, start_date, end_date):
        """获取 OHLCV 数据"""
        
    def get_indicators(ticker, indicators_list):
        """获取技术指标"""
        
    def get_fundamentals(ticker, date):
        """获取基本面数据"""
        
    def get_news_sentiment(ticker, date):
        """获取新闻情绪"""
```

#### **执行模拟器**
```python
class ExecutionSimulator:
    """交易执行模拟"""
    
    # 港股特性
    settlement: str = "T+2"  # T+2 交收
    trading_cost: float = 0.0028  # 双边约 0.28%
    slippage: float = 0.001  # 滑点 0.1%
    min_lot: int = None  # 每手股数（因股而异）
    
    def execute_buy(self, date, ticker, price, shares):
        """执行买入"""
        # 检查资金是否充足
        # 计算交易成本
        # T+2 交收检查
        
    def execute_sell(self, date, ticker, price, shares):
        """执行卖出"""
        # 检查是否持仓
        # 检查是否已交收（T+2）
        # 计算交易成本和税费
```

#### **港股市场规则**
```python
class HKMarketRules:
    """港股特殊规则"""
    
    # 交易成本
    stamp_duty = 0.0013  # 印花税 0.13%
    trading_fee = 0.00005  # 交易费
    transaction_levy = 0.0000565  # 交易征费
    brokerage = 0.0003  # 经纪佣金（估算）
    
    total_cost_one_way = 0.0014  # 单边约 0.14%
    total_cost_round_trip = 0.0028  # 双边约 0.28%
    
    # 交易时间
    morning_session = ("09:30", "12:00")
    afternoon_session = ("13:00", "16:00")
    
    # 交收制度
    settlement_days = 2  # T+2
    
    # 价位规则
    tick_sizes = {
        (0.01, 0.25): 0.001,
        (0.25, 0.50): 0.005,
        (0.50, 10.00): 0.01,
        # ...
    }
    
    def validate_price(self, price):
        """验证价格是否符合价位规则"""
        
    def calculate_total_cost(self, trade_value):
        """计算总交易成本"""
```

---

### 2. 性能指标

```python
class PerformanceMetrics:
    """回测性能指标"""
    
    # 收益指标
    total_return: float  # 总收益率
    annualized_return: float  # 年化收益率
    excess_return: float  # 超额收益（vs 基准）
    
    # 风险指标
    volatility: float  # 波动率
    max_drawdown: float  # 最大回撤
    sharpe_ratio: float  # 夏普比率
    sortino_ratio: float  # 索提诺比率
    calmar_ratio: float  # 卡玛比率
    
    # 交易指标
    total_trades: int  # 总交易次数
    win_rate: float  # 胜率
    profit_factor: float  # 盈亏比
    avg_win: float  # 平均盈利
    avg_loss: float  # 平均亏损
    
    # 时间指标
    avg_holding_period: float  # 平均持仓天数
    time_in_market: float  # 市场暴露时间
    
    # 港股特定
    trading_cost_total: float  # 总交易成本
    cost_impact_on_return: float  # 成本对收益的影响
```

---

## 🔄 工作流程

### 1. Agent → Strategy 转换

```python
# Trader Agent 输出
trader_decision = {
    'action': 'BUY',
    'ticker': '0700.HK',
    'confidence': 0.75,
    'reasoning': '技术面突破 + 基本面改善 + 新闻正面',
    'entry_price': 380.0,
    'target_price': 420.0,
    'stop_loss': 360.0,
    'position_size': 0.2,  # 20% 仓位
    'holding_period': 30  # 预计持有30天
}

# 转换为策略
strategy = AgentStrategy(trader_decision)

# 创建回测任务
backtest = BacktestEngine(
    strategy=strategy,
    ticker='0700.HK',
    start_date='2023-01-01',
    end_date='2025-12-31',
    initial_capital=1000000,  # 100万港元
    market='HKEX'
)

# 运行回测
results = backtest.run()
```

### 2. 策略库回测

```python
# 从策略库加载策略
strategy = StrategyLibrary.load('ma_crossover', {
    'fast_period': 10,
    'slow_period': 50,
    'position_size': 0.3
})

# 批量回测多个股票
results = backtest_portfolio(
    strategy=strategy,
    tickers=['0700.HK', '9988.HK', '0941.HK'],
    start_date='2020-01-01',
    end_date='2025-12-31'
)
```

### 3. 参数优化

```python
# 定义参数范围
param_grid = {
    'fast_period': [5, 10, 20],
    'slow_period': [30, 50, 100],
    'stop_loss_pct': [0.05, 0.10, 0.15]
}

# 网格搜索最优参数
optimizer = ParameterOptimizer(
    strategy_class=MACrossoverStrategy,
    param_grid=param_grid,
    ticker='0700.HK',
    optimization_metric='sharpe_ratio'
)

best_params, best_score = optimizer.optimize()
```

---

## 📊 报告与可视化

### 1. 回测报告内容

```markdown
# 回测报告 - [策略名称]

## 基本信息
- 股票代码: 0700.HK
- 回测期间: 2023-01-01 至 2025-12-31
- 初始资金: HKD 1,000,000
- 策略类型: Agent-Generated Strategy

## 绩效摘要
| 指标 | 值 |
|------|-----|
| 总收益率 | +45.8% |
| 年化收益率 | +18.2% |
| 最大回撤 | -12.5% |
| 夏普比率 | 1.85 |
| 胜率 | 62.5% |
| 总交易次数 | 24 |

## 交易详情
[详细交易记录表格]

## 收益曲线
[可视化图表]

## 风险分析
- 月度收益分布
- 回撤分析
- 波动率分析

## 成本分析（港股特定）
- 印花税: HKD 15,000
- 交易费用: HKD 8,500
- 总成本占比: 2.3%
```

---

## 🎓 实施建议

### Phase 1: 基础框架（1-2周）
- ✅ 策略基类定义
- ✅ Backtrader 集成
- ✅ 港股市场规则
- ✅ 基础性能指标

### Phase 2: Agent 集成（1-2周）
- ✅ Agent 决策转策略
- ✅ 自动化回测流程
- ✅ 结果反馈到 Agent Memory

### Phase 3: 策略库（2-3周）
- ✅ 常见策略模板
- ✅ 参数优化工具
- ✅ 策略对比分析

### Phase 4: 高级功能（2-3周）
- ✅ 实时监控
- ✅ 自动交易（纸上交易）
- ✅ Web 界面

---

## 🔐 质量保证

### 1. 数据质量
- 使用多个数据源交叉验证
- 处理缺失数据和异常值
- 考虑股票分割、股息调整

### 2. 回测准确性
- 避免前视偏差 (Look-ahead bias)
- 避免幸存者偏差 (Survivorship bias)
- 考虑实际交易限制

### 3. 与 Agent 兼容性
- Agent 输出格式标准化
- 策略参数可解释性
- 反馈循环清晰

---

## 🚀 下一步行动

1. **选择实施路径**：
   - 快速原型（简化版）
   - 完整实现（标准版）
   
2. **技术栈确认**：
   - Backtrader (已安装)
   - TA-Lib (技术指标)
   - Plotly/Matplotlib (可视化)
   
3. **测试数据集**：
   - 选择 3-5 只港股作为测试
   - 准备 2-3 年历史数据

想从哪里开始？🤔
