import json
import sys
from pathlib import Path

# streamlit run demo/app.py: cwd 常在仓库根目录，但 sys.path 不含仓库根，需手动加入
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

st.set_page_config(page_title="StockBuddy FYP Demo", layout="wide")

st.title("StockBuddy — Research")

EXPERIMENTS_DIR = _ROOT / "experiments/batches"


@st.cache_data
def load_batches():
    batches = []
    if EXPERIMENTS_DIR.exists():
        for d in sorted(EXPERIMENTS_DIR.iterdir(), reverse=True):
            if d.is_dir() and (d / "batch_meta.json").exists():
                batches.append(d)
    return batches


st.caption(
    "Batch runs from formal eval / pilot: action, gate, lineage, order handoff."
)
batches = load_batches()
if not batches:
    st.warning(
        "No batches under `experiments/batches/`. Run a timeline or pilot first."
    )
else:
    meta_by_batch = {}
    for b in batches:
        try:
            meta_by_batch[b] = json.loads((b / "batch_meta.json").read_text())
        except (OSError, json.JSONDecodeError):
            meta_by_batch[b] = {}

    batch = st.selectbox(
        "Experiment batch",
        batches,
        format_func=lambda x: x.name,
        key="research_batch",
    )
    meta = meta_by_batch.get(batch, {})
    st.write(
        f"**profile** {meta.get('pipeline_profile')} · **ticker** {meta.get('ticker')} · "
        f"**dates** {', '.join(meta.get('dates', []) or [])}"
    )

    bt_dirs = list((batch / "backtest").glob("bt_*"))
    if bt_dirs:
        latest_bt = sorted(bt_dirs)[-1]
        mp = latest_bt / "metrics.json"
        if mp.exists():
            with st.expander("Backtest snapshot (latest)"):
                m = json.loads(mp.read_text())
                c1, c2, c3 = st.columns(3)
                c1.metric("Total return", f"{m.get('total_return', 0) * 100:.2f}%")
                c2.metric("Max drawdown", f"{m.get('max_drawdown', 0) * 100:.2f}%")
                c3.metric("Ignored by protocol", m.get("num_signals_ignored_by_protocol"))

    decisions_path = batch / "decisions.jsonl"
    if not decisions_path.exists():
        st.error("decisions.jsonl missing.")
    else:
        decisions = []
        for line in decisions_path.read_text().strip().split("\n"):
            if line.strip():
                decisions.append(json.loads(line))
        if not decisions:
            st.warning("Empty decisions.jsonl.")
        else:
            selected_date = st.selectbox(
                "Analysis date",
                [d["analysis_date"] for d in decisions],
                key="research_date",
            )
            current_row = next(
                d for d in decisions if d["analysis_date"] == selected_date
            )
            run_dir = Path(current_row["experiment_dir"])
            dj_path = run_dir / "decision.json"
            if not dj_path.exists():
                st.error("decision.json missing for this run.")
            else:
                dj = json.loads(dj_path.read_text())
                action = dj.get("action", "HOLD")
                blocked = dj.get("blocked_by_risk_gate", False)

                st.subheader("Final action")
                if action == "BUY" and not blocked:
                    st.success(
                        f"**{action}** · confidence `{dj.get('confidence')}`"
                    )
                elif blocked:
                    st.warning("**HOLD** (blocked by risk gate)")
                    st.caption(dj.get("gate_reason") or "")
                else:
                    st.info(f"**{action}**")

                st.subheader("Rationale & risk")
                st.markdown(dj.get("rationale_summary") or "_N/A_")
                flags = dj.get("risk_flags") or []
                st.markdown("**risk_flags**")
                if flags:
                    for f in flags:
                        st.markdown(f"- `{f}`")
                else:
                    st.markdown("- _none_")

                st.subheader("Gate")
                gt = dj.get("gate_triggers")
                if gt is None:
                    st.caption("No `gate_triggers` (older decision schema).")
                    gt = []
                st.markdown(f"**gate_triggers:** `{gt}`")
                st.markdown(f"**gate_summary:** {dj.get('gate_summary') or '_N/A_'}")

                st.subheader("Lineage summary")
                lin_path = run_dir / "lineage.json"
                if lin_path.exists():
                    lin = json.loads(lin_path.read_text())
                    st.json(
                        {
                            "gate_summary": lin.get("gate_summary"),
                            "gate_triggers": lin.get("gate_triggers"),
                            "report_paths": lin.get("report_paths"),
                            "order_spec_path": lin.get("order_spec_path"),
                            "parsed_action_pre_gate": lin.get(
                                "parsed_action_pre_gate"
                            ),
                            "parsed_action_post_gate": lin.get(
                                "parsed_action_post_gate"
                            ),
                        }
                    )
                else:
                    st.info("No `lineage.json` for this run (older artifact set).")

                st.subheader("Order spec")
                spec_path = run_dir / "order_spec.json"
                if spec_path.exists():
                    st.json(json.loads(spec_path.read_text()))
                else:
                    st.info("No order_spec.json.")

                with st.expander("Process traceability (full_state)"):
                    fs_path = run_dir / "full_state.json"
                    if fs_path.exists():
                        fs = json.loads(fs_path.read_text())
                        prof = meta.get("pipeline_profile") or ""
                        st.caption(
                            f"当前 batch **pipeline_profile** = `{prof}`。"
                            "`single_agent` 只跑 Market 子图，基本面与多空/风险辩论不会执行，"
                            "对应字段在 full_state 里会为空；`full_system` 才会有辩论与 risk judge。"
                        )
                        st.text_area(
                            "market_report",
                            fs.get("market_report") or "",
                            height=120,
                            disabled=True,
                        )
                        fund = fs.get("fundamentals_report") or ""
                        st.text_area(
                            "fundamentals_report",
                            fund,
                            height=120,
                            disabled=True,
                        )
                        if not fund.strip():
                            st.caption(
                                "空：常见于 **single_agent**（未跑基本面节点），"
                                "或 full_system 下基本面未成功写入。"
                            )
                        inv = fs.get("investment_debate_state") or {}
                        if not isinstance(inv, dict):
                            inv = {}
                        st.markdown("**investment_debate_state**（正文多在 bull/bear，不一定在 history）")
                        st.text_area(
                            "bull_history",
                            inv.get("bull_history") or "",
                            height=80,
                            disabled=True,
                        )
                        st.text_area(
                            "bear_history",
                            inv.get("bear_history") or "",
                            height=80,
                            disabled=True,
                        )
                        st.text_area(
                            "history (合并串，可能为空)",
                            inv.get("history") or "",
                            height=60,
                            disabled=True,
                        )
                        st.text_area(
                            "investment judge_decision",
                            inv.get("judge_decision") or "",
                            height=60,
                            disabled=True,
                        )
                        if not (
                            (inv.get("bull_history") or "").strip()
                            or (inv.get("bear_history") or "").strip()
                            or (inv.get("history") or "").strip()
                        ):
                            st.caption(
                                "空：常见于 **single_agent**（无多空辩论图），"
                                "或 full_system 但本轮未写入 debate state。"
                            )
                        risk = fs.get("risk_debate_state") or {}
                        if not isinstance(risk, dict):
                            risk = {}
                        st.markdown("**risk_debate_state**")
                        st.text_area(
                            "risk judge_decision",
                            risk.get("judge_decision") or "",
                            height=80,
                            disabled=True,
                        )
                        st.text_area(
                            "risky / safe / neutral (摘录)",
                            "\n---\n".join(
                                [
                                    risk.get("risky_history") or "",
                                    risk.get("safe_history") or "",
                                    risk.get("neutral_history") or "",
                                ]
                            ),
                            height=100,
                            disabled=True,
                        )
                        if not (risk.get("judge_decision") or "").strip():
                            st.caption(
                                "空：常见于 **single_agent**（无 Risk Judge 节点）。"
                            )
                    else:
                        st.info("No full_state.json.")
