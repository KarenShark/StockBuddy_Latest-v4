# Figure 3.3 — Sequential multi-agent orchestration (ASCII)

纯 Markdown：同一 **TEAM / 层级** 用外层大框包住；框内为子模块与连线。

```
============================================================
   MULTI-AGENT SEQUENTIAL ORCHESTRATION (CONTROL FLOW)
============================================================

+----------------------------------------------------------+
| ANALYST TEAM                                             |
|  parallel exec.  |  Functional: Info Collection         |
|  [Market][News][Fundam.]  \ | /  merge  -->  v           |
+----------------------------------------------------------+
                          v
+----------------------------------------------------------+
| RESEARCH TEAM                                            |
|  debate-driven rec.  |  Research & Initial Reasoning     |
|  Pos* <-> Debate <-> Neg*  -->  Research Mgr.  -->  v   |
+----------------------------------------------------------+
                          v
+----------------------------------------------------------+
| TRADING TEAM                         Trading Proposal    |
|  Trader (invest. prop.)  --------------------------->  v   |
+----------------------------------------------------------+
                          v
+----------------------------------------------------------+
| RISK MANAGEMENT TEAM                                     |
|  multi-perspective  |  Risk Defense Layer                |
|  Agr* | Neu* | Con*  -->  Final Debate  ------------> v |
+----------------------------------------------------------+
                          v
+----------------------------------------------------------+
| PORTFOLIO MANAGER                                        |
|  Final: BUY / SELL / HOLD  +  narrative & structured   |
+----------------------------------------------------------+
============================================================
```

**读图约定**

- 每个 **`+--...+` 大框** 表示一个 TEAM / 逻辑层级；框外居中 **`v`** 表示进入下一层。
- 框内 **`[...]` / `|` / `-->`** 为子角色与顺序（简写版）；全图仍表示 **层内可并行、层间单路径**（LangGraph）。
- `*` 对应原图中的勾选标记（示意）；`Debate` / `Final Debate` 为观点交锋后再收敛。
- 实现上 Bull/Bear、Risky/Neutral/Safe 与角色名对应；五档动作为 BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL，图中 BUY/SELL/HOLD 为简写。

**图注（可贴论文）**  
*Figure 3.3 — Sequential multi-agent orchestration.* 各 TEAM 由外层框界定职责边界；分析、研究、交易、风险与组合决策依次衔接，形成顺序编排的多智能体流水线。
