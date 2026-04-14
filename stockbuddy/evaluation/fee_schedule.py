"""
Fixed FYP fee snapshot — no live web fetch. Override via config['backtest_fee_schedule'].
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Tuple

# Reproducible standard for this project (verify against official schedules for reports).
FEE_SNAPSHOT_VERSION = "fyp-hk-2025-03"
FEE_SNAPSHOT_AS_OF = "2025-03-01"

# Decimals are fraction of notional per side (buy leg / sell leg each).
# Roles: official_snapshot = published levies; config_assumption = broker/platform placeholder.
_HK_EQUITY_COMPONENTS: Dict[str, Dict[str, Any]] = {
    "stamp_duty": {
        "rate": 0.001,
        "role": "official_snapshot",
        "note": "Ad valorem stamp on stock transfers; snapshot for reproducibility only.",
    },
    "sfc_levy": {
        "rate": 0.000027,
        "role": "official_snapshot",
        "note": "SFC transaction levy; rate varies over time.",
    },
    "frc_levy": {
        "rate": 0.0000015,
        "role": "official_snapshot",
        "note": "AFRC/FRC transaction levy; naming per HK usage.",
    },
    "trading_fee": {
        "rate": 0.0000565,
        "role": "official_snapshot",
        "note": "Exchange trading fee; snapshot.",
    },
    "broker_platform_fee": {
        "rate": 0.0005,
        "role": "config_assumption",
        "note": "All-in broker/platform; not tied to a specific broker.",
    },
}

_HK_ETF_COMPONENTS: Dict[str, Dict[str, Any]] = {
    "stamp_duty": {
        "rate": 0.0,
        "role": "official_snapshot",
        "note": "Listed ETF secondary market stamp duty exemption (policy snapshot).",
    },
    "sfc_levy": deepcopy(_HK_EQUITY_COMPONENTS["sfc_levy"]),
    "frc_levy": deepcopy(_HK_EQUITY_COMPONENTS["frc_levy"]),
    "trading_fee": deepcopy(_HK_EQUITY_COMPONENTS["trading_fee"]),
    "broker_platform_fee": deepcopy(_HK_EQUITY_COMPONENTS["broker_platform_fee"]),
}


def _bps(rate: float) -> float:
    return round(rate * 10000.0, 6)


def _merge_components(
    base: Dict[str, Dict[str, Any]], override: Dict[str, Any] | None
) -> Dict[str, Dict[str, Any]]:
    out = deepcopy(base)
    if not override:
        return out
    for k, v in override.items():
        if k not in out:
            continue
        if isinstance(v, dict) and "rate" in v:
            out[k]["rate"] = float(v["rate"])
            if "note" in v:
                out[k]["note"] = str(v["note"])
        elif isinstance(v, (int, float)):
            out[k]["rate"] = float(v)
    return out


def resolve_fee_components(
    asset_type: str | None,
    config: Dict[str, Any],
) -> Tuple[str, Dict[str, Dict[str, Any]], int]:
    """
    Returns (schedule_key_used, components, unknown_fallback_count).
    unknown -> hk_equity rates for fee math; fallback_count 1 when input was unknown.
    """
    raw = (asset_type or "unknown").strip().lower()
    fallback = 0
    if raw == "unknown":
        raw = "hk_equity"
        fallback = 1

    if raw == "hk_etf":
        base = _HK_ETF_COMPONENTS
    else:
        base = _HK_EQUITY_COMPONENTS

    sched = config.get("backtest_fee_schedule") or {}
    if raw == "hk_etf":
        ov = sched.get("hk_etf")
    else:
        ov = sched.get("hk_equity")
    merged = _merge_components(base, ov if isinstance(ov, dict) else None)
    return raw, merged, fallback


def per_side_fee(notional: float, components: Dict[str, Dict[str, Any]]) -> float:
    if notional <= 0:
        return 0.0
    total = 0.0
    for _name, meta in components.items():
        total += notional * float(meta["rate"])
    return total


def build_fee_model_for_metrics(
    *,
    snapshot_version: str,
    snapshot_as_of: str,
    hk_equity: Dict[str, Dict[str, Any]],
    hk_etf: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    def pack(comp: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, meta in comp.items():
            r = float(meta["rate"])
            out[name] = {
                "rate": r,
                "bps": _bps(r),
                "role": meta.get("role"),
                "note": meta.get("note", ""),
            }
        return out

    return {
        "fee_snapshot_version": snapshot_version,
        "fee_snapshot_as_of": snapshot_as_of,
        "disclaimer": (
            "Rates are frozen for FYP reproducibility; official schedules change. "
            "broker_platform_fee is a configurable assumption, not an exchange rule."
        ),
        "hk_equity": {"components": pack(hk_equity)},
        "hk_etf": {"components": pack(hk_etf)},
        "unknown_asset_handling": "Fees use hk_equity schedule; count unknown_fallback_uses in performance.",
    }


def merge_fee_models_for_metrics(
    equity_comp: Dict[str, Dict[str, Any]],
    etf_comp: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return build_fee_model_for_metrics(
        snapshot_version=FEE_SNAPSHOT_VERSION,
        snapshot_as_of=FEE_SNAPSHOT_AS_OF,
        hk_equity=equity_comp,
        hk_etf=etf_comp,
    )
