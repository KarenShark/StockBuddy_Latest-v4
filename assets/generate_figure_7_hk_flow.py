"""Regenerate figure-7-hk-market-adaptation-flow.png (English, no overlapping text)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

FIG_W, FIG_H, DPI = 16, 12, 200
Y_MAX = 11.35


def add_rounded_box(ax, x, y, w, h, fc, ec, lw=1.8):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.03,rounding_size=0.14",
            facecolor=fc,
            edgecolor=ec,
            linewidth=lw,
        )
    )


def box_title_body(
    ax,
    x,
    y,
    w,
    h,
    title: str,
    body_lines: list[str],
    *,
    title_fs: float = 10.5,
    body_fs: float = 9,
    title_color: str = "#0f172a",
    body_color: str = "#1e293b",
    edge: str = "#94a3b8",
    face: str = "#ffffff",
    lw: float = 1.8,
    line_step: float = 0.175,
    title_band: float = 0.4,
):
    """line_step/title_band in axis data units (bold glyphs need ~0.16–0.2 per line)."""
    add_rounded_box(ax, x, y, w, h, face, edge, lw)
    cx = x + w / 2
    pad_top = 0.1

    ax.text(
        cx,
        y + h - pad_top,
        title,
        ha="center",
        va="top",
        fontsize=title_fs,
        fontweight="bold",
        color=title_color,
    )
    y_line = y + h - pad_top - title_band
    for line in body_lines:
        ax.text(
            cx,
            y_line,
            line,
            ha="center",
            va="top",
            fontsize=body_fs,
            fontweight="bold",
            color=body_color,
        )
        y_line -= line_step


def arrow(ax, x1, y1, x2, y2, color="#475569"):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>", color=color, lw=2.0, mutation_scale=14, shrinkA=5, shrinkB=5
        ),
    )


def layer_label(ax, y, h, name: str):
    ax.text(
        0.42,
        y + h / 2,
        name,
        ha="left",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="#64748b",
        rotation=90,
    )


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
        }
    )

    fig, ax = plt.subplots(1, 1, figsize=(FIG_W, FIG_H), dpi=DPI)
    ax.set_xlim(0, 15.5)
    ax.set_ylim(-0.02, Y_MAX)
    ax.axis("off")
    fig.patch.set_facecolor("#fafbfc")
    ax.set_facecolor("#fafbfc")

    C_PROMPT = "#1e3a5f"
    C_ROUTE = "#2d5a4a"
    C_NEWS = "#5c4b8a"
    C_FEE = "#8b4513"
    C_ACCENT = "#2563eb"
    C_BORDER = "#94a3b8"

    ax.text(
        7.75,
        10.92,
        "Hong Kong Market Adaptation Flow",
        ha="center",
        va="center",
        fontsize=19,
        fontweight="bold",
        color="#0f172a",
    )
    ax.text(
        7.75,
        10.48,
        "StockBuddy: data routing, merged news, fee model, prompting (HKEX)",
        ha="center",
        va="center",
        fontsize=11.5,
        fontweight="bold",
        color="#475569",
    )

    # --- INPUT (h_in fits 3 body lines at line_step 0.175) ---
    y_in, h_in = 8.92, 1.38
    layer_label(ax, y_in, h_in, "INPUT")
    box_title_body(
        ax,
        1.0,
        y_in,
        3.6,
        h_in,
        "Runtime config",
        [
            "DEFAULT_MARKET = HKEX",
            "DEFAULT_LANGUAGE = zh_TW",
            "API keys: EODHD, Finnhub, etc.",
        ],
        body_fs=8.6,
        line_step=0.172,
    )
    box_title_body(
        ax,
        4.85,
        y_in,
        3.95,
        h_in,
        "Ticker normalisation",
        [
            "Numeric code to XXXX.HK",
            "Smart ticker resolver",
            "yfinance symbol",
        ],
        body_fs=8.6,
        line_step=0.172,
    )
    box_title_body(
        ax,
        9.05,
        y_in,
        5.35,
        h_in,
        "HKEX-specific handling",
        [
            "HKEXnews URL in fundamentals prompt",
            "HK relevance filters on news items",
        ],
        body_fs=8.6,
        line_step=0.175,
    )
    arrow(ax, 4.6, y_in + h_in / 2, 4.82, y_in + h_in / 2)
    arrow(ax, 8.78, y_in + h_in / 2, 9.02, y_in + h_in / 2)

    # --- ADAPT ---
    y_ad, h_ad = 7.22, 1.52
    layer_label(ax, y_ad, h_ad, "ADAPT")
    add_rounded_box(ax, 1.0, y_ad, 13.4, h_ad, "#eff6ff", C_ACCENT, 2.0)
    ax.text(
        7.7,
        y_ad + h_ad - 0.1,
        "Bilingual prompting layer (Chinese + English templates)",
        ha="center",
        va="top",
        fontsize=11.5,
        fontweight="bold",
        color=C_PROMPT,
    )
    ax.text(
        7.7,
        y_ad + h_ad - 0.52,
        "hk_market_prompts: market, news, social, fundamentals, debate, trader, risk",
        ha="center",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color="#1e293b",
    )
    ax.text(
        7.7,
        y_ad + h_ad - 0.95,
        "English prompts when DEFAULT_MARKET is not HKEX",
        ha="center",
        va="top",
        fontsize=9.5,
        fontweight="bold",
        color="#1e293b",
    )
    arrow(ax, 7.75, y_in, 7.75, y_ad + h_ad + 0.02)

    # --- ROUTING (taller for 4-line body) ---
    y_rt, h_rt = 5.48, 1.58
    layer_label(ax, y_rt, h_rt, "ROUTING")
    box_title_body(
        ax,
        1.0,
        y_rt,
        6.5,
        h_rt,
        "route_to_vendor",
        [
            "Category- and tool-level vendors",
            "core_stock_apis to yfinance",
            "get_news to merged pipeline",
            "get_global_news to google, openai, local",
        ],
        title_color=C_ROUTE,
        face="#ecfdf5",
        edge=C_ROUTE,
        lw=2.0,
        body_fs=8.5,
        line_step=0.17,
    )
    box_title_body(
        ax,
        7.75,
        y_rt,
        6.65,
        h_rt,
        "News window policy",
        [
            "analysis_end_is_historical(end)",
            "EODHD path when historical; bounded windows",
            "STOCKBUDDY_NEWS_JSON metadata prefix",
        ],
        title_color=C_ROUTE,
        face="#f0fdf4",
        edge="#15803d",
        lw=2.0,
        body_fs=8.5,
        line_step=0.175,
    )
    arrow(ax, 3.5, y_ad, 3.5, y_rt + h_rt + 0.02)
    arrow(ax, 11.0, y_ad, 11.0, y_rt + h_rt + 0.02)

    # --- DATA ---
    y_dt, h_dt = 3.18, 2.15
    layer_label(ax, y_dt, h_dt, "DATA")
    add_rounded_box(ax, 1.0, y_dt, 13.4, h_dt, "#f5f3ff", C_NEWS, 2.2)
    ax.text(
        7.7,
        y_dt + h_dt - 0.08,
        "Merged news pipeline (get_news, merged vendor)",
        ha="center",
        va="top",
        fontsize=12.5,
        fontweight="bold",
        color=C_NEWS,
    )
    ax.text(
        7.7,
        y_dt + h_dt - 0.55,
        "De-duplication, date windowing, optional Newsdata.io (live only)",
        ha="center",
        va="top",
        fontsize=8.8,
        fontweight="bold",
        color="#5b21b6",
    )

    sub_h, sub_pad = 0.88, 0.52
    sy_sub = y_dt + sub_pad
    subs = [
        ("Google RSS (filtered)", 1.15, sy_sub, 2.45, sub_h),
        ("yfinance news stream", 3.75, sy_sub, 2.45, sub_h),
        ("EODHD history + sentiment", 6.35, sy_sub, 2.65, sub_h),
        ("Finnhub (HK tool path)", 9.15, sy_sub, 2.65, sub_h),
        ("HKEXnews fetcher", 11.95, sy_sub, 2.5, sub_h),
    ]
    for title, sx, sy, sw, sh in subs:
        add_rounded_box(ax, sx, sy, sw, sh, "#ffffff", "#a78bfa", 1.6)
        ax.text(
            sx + sw / 2,
            sy + sh - 0.07,
            title,
            ha="center",
            va="top",
            fontsize=8.8,
            fontweight="bold",
            color="#1e293b",
        )

    arrow(ax, 3.5, y_rt, 3.5, y_dt + h_dt + 0.02)
    arrow(ax, 7.75, y_rt, 7.75, y_dt + h_dt - 0.05)

    # --- EVAL ---
    y_ev, h_ev = 0.52, 2.52
    layer_label(ax, y_ev, h_ev, "EVAL")
    box_title_body(
        ax,
        1.0,
        y_ev,
        8.55,
        h_ev,
        "Local HK fee model",
        [
            "resolve_fee_components, frozen FEE_SNAPSHOT",
            "Stamp duty 0.1% per side (equity)",
            "SFC levy, AFRC/FRC levy, HKEX trading fee",
            "Broker/platform fee (config placeholder)",
        ],
        title_color=C_FEE,
        face="#fffbeb",
        edge=C_FEE,
        lw=2.0,
        body_fs=8.8,
        line_step=0.17,
    )
    box_title_body(
        ax,
        9.75,
        y_ev,
        4.65,
        h_ev,
        "Downstream use",
        [
            "Trading graph signals and backtests",
            "normalised tickers",
            "fee-aware P&L assumptions",
        ],
        body_fs=9.0,
        line_step=0.175,
    )
    arrow(ax, 7.75, y_dt, 7.75, y_ev + h_ev + 0.02)
    arrow(ax, 4.5, y_rt, 4.5, y_ev + h_ev + 0.02)

    # Legend
    leg_y = 0.18
    ax.text(1.0, leg_y + 0.48, "Legend", fontsize=10.5, fontweight="bold", color="#334155")
    for i, (col, lab) in enumerate(
        [
            ("#eff6ff", "Prompting"),
            ("#ecfdf5", "Routing"),
            ("#f5f3ff", "News merge"),
            ("#fffbeb", "Fees"),
        ]
    ):
        lx = 1.08 + i * 3.2
        ax.add_patch(
            plt.Rectangle((lx, leg_y), 0.3, 0.3, facecolor=col, edgecolor=C_BORDER, linewidth=1.2)
        )
        ax.text(lx + 0.42, leg_y + 0.15, lab, va="center", fontsize=9.5, fontweight="bold", color="#334155")

    out = Path(__file__).resolve().parent / "figure-7-hk-market-adaptation-flow.png"
    plt.savefig(
        out,
        dpi=DPI,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        edgecolor="none",
        pad_inches=0.12,
    )
    plt.close()
    print(out)


if __name__ == "__main__":
    main()
