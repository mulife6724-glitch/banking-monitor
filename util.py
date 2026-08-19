# -*- coding: utf-8 -*-
"""공통 유틸 + 결정론적 스코어링 (원본 V6.1 방법론 그대로).

핵심 원칙: AI는 방향/중요도/신뢰도 '라벨'만 만든다. 실제 점수는 이 코드가
결정론적으로 계산한다. 같은 입력이면 언제나 같은 숫자.
"""
from __future__ import annotations
import datetime as _dt
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 지표 정의: 키 -> (한글 라벨, 방향의 '상승'이 좋은가)
INDICES = {
    "personal":         ("개인 부담 지수", False),
    "corporate":        ("기업 압력 지수", False),
    "bank_risk":        ("은행 리스크 지수", False),
    "bank_opportunity": ("은행 기회 지수", True),
}

# 출처 등급별 품질 가중치 (V4_SCORING_PARAMETERS.json)
SOURCE_QUALITY = {
    "OFFICIAL": 1.00, "PRIMARY_CORPORATE": 0.95, "WIRE": 0.90,
    "MAJOR_MEDIA": 0.75, "SECONDARY": 0.55,
}


def now_kst() -> _dt.datetime:
    return _dt.datetime.now(tz=KST)


def today_str() -> str:
    return now_kst().strftime("%Y-%m-%d")


def clip(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def tier_kind(tier: str) -> str:
    s = str(tier or "").upper()
    for k in ("OFFICIAL", "PRIMARY", "WIRE", "MAJOR", "SECONDARY"):
        if k in s:
            return {"PRIMARY": "PRIMARY_CORPORATE", "MAJOR": "MAJOR_MEDIA"}.get(k, k)
    return "SECONDARY"


def raw_index(signals: list[dict], key: str) -> float:
    """Index = clip(50 + 25 * weighted_direction), weight = importance*confidence.
    signals: [{'personal': {'direction','importance','confidence'}, ..., 'include_in_index': bool}]
    지수에 포함(include_in_index)된 신호만, 해당 지표 방향이 0이 아니어도 가중평균에 참여."""
    num = den = 0.0
    for s in signals:
        if not s.get("include_in_index", True):
            continue
        blk = s.get(key) or {}
        try:
            d = float(blk.get("direction", 0))
            imp = float(blk.get("importance", 0))
            conf = float(blk.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        w = imp * conf
        if w <= 0:
            continue
        num += d * w
        den += w
    if den == 0:
        return 50.0
    return round(clip(50 + 25 * (num / den)), 4)


def data_sufficiency(signals: list[dict]) -> float:
    """근거 충분도 0~100 (V4). 사건수/도메인수/유효가중/공식·1차 비중/평균 출처품질."""
    incl = [s for s in signals if s.get("include_in_index", True)]
    events = len({s.get("event_key") for s in incl}) or len(incl)
    domains = len({(s.get("source_domain") or s.get("source") or "") for s in incl})
    eff_weight = sum(max(float((s.get(k) or {}).get("importance", 0)) * float((s.get(k) or {}).get("confidence", 0))
                         for k in INDICES) for s in incl)
    kinds = [tier_kind(s.get("source_tier", "SECONDARY")) for s in incl]
    off_primary = sum(1 for k in kinds if k in ("OFFICIAL", "PRIMARY_CORPORATE"))
    off_share = (off_primary / len(kinds)) if kinds else 0.0
    avg_q = (sum(SOURCE_QUALITY.get(k, 0.55) for k in kinds) / len(kinds)) if kinds else 0.0
    score = 100 * (
        0.35 * min(events / 5, 1) +
        0.20 * min(domains / 3, 1) +
        0.20 * min(eff_weight / 10, 1) +
        0.15 * off_share +
        0.10 * avg_q
    )
    return round(score, 2)


def robust_index(raw: float, sufficiency: float) -> float:
    """Robust = 50 + (충분도/100) * (Raw - 50). 근거 부족하면 중립(50)으로 끌어당김."""
    rf = sufficiency / 100.0
    return round(clip(50 + rf * (raw - 50)), 4)


def status_badge(key: str, value: float, delta: float | None) -> str:
    """상태 배지 (V3/V4 임계값). 기회 지표는 방향 반대로 해석."""
    if delta is not None and abs(delta) >= 5:
        return "MATERIAL_RISE" if delta > 0 else "MATERIAL_FALL"
    if value >= 70:
        return "HIGH"
    if value >= 60:
        return "ELEVATED"
    if value >= 55:
        return "WATCH"
    return "NEUTRAL"
