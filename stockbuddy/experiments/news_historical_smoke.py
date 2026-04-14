"""
Smoke: historical analysis_date uses bounded windows; no 2026 leakage from Newsdata path.

Run: python -m stockbuddy.experiments.news_historical_smoke
"""

from __future__ import annotations

from unittest import mock

from stockbuddy.dataflows.config import set_config
from stockbuddy.dataflows.interface import _route_get_global_news, route_to_vendor
from stockbuddy.dataflows.merged_news import get_merged_stock_news
from stockbuddy.dataflows.news_window_policy import analysis_end_is_historical
from stockbuddy.default_config import DEFAULT_CONFIG


def main() -> None:
    assert analysis_end_is_historical("2024-06-03"), "expect 2024-06-03 < today UTC"

    cfg = {**DEFAULT_CONFIG}
    set_config(cfg)

    # 1) merged company news: Newsdata must not run (would return undated "latest" feed)
    poison = "\n## 99. Fake 2026 headline\n\n**时间**: 2026-03-27\n"
    with mock.patch(
        "stockbuddy.dataflows.merged_news.get_newsdata_hk_stock_news",
        return_value=poison,
    ) as p_nd:
        merged = get_merged_stock_news("0700", "2024-05-28", "2024-06-03")
    p_nd.assert_not_called()
    assert "2026" not in merged, merged[:500]
    assert "historical_mode_newsdata_unbounded" in merged

    # 2) global news: historical path must not call OpenAI / reddit live paths
    with mock.patch(
        "stockbuddy.dataflows.interface.get_global_news_openai"
    ) as p_oa, mock.patch(
        "stockbuddy.dataflows.interface.get_reddit_global_news"
    ) as p_rd:
        gout = _route_get_global_news("2024-06-03", 7, 5)
    p_oa.assert_not_called()
    p_rd.assert_not_called()
    assert gout.startswith("STOCKBUDDY_NEWS_JSON:")
    assert "2026" not in gout, gout[:800]

    # 3) route_to_vendor entry never raises
    out2 = route_to_vendor("get_global_news", "2024-06-03", 7, 5)
    assert out2.startswith("STOCKBUDDY_NEWS_JSON:")

    print("news_historical_smoke: OK")


if __name__ == "__main__":
    main()
