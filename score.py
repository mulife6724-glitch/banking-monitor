# -*- coding: utf-8 -*-
"""③ 점수 계산 + 히스토리 적재. 결정론적. 원본 V6.1 공식 사용."""
from __future__ import annotations
import json
import os

from util import INDICES, data_sufficiency, raw_index, robust_index, status_badge, today_str

HISTORY_PATH = os.environ.get("HISTORY_PATH", "history.json")


def _signals(analyzed: list[dict]) -> list[dict]:
    """분석 결과를 스코어러가 먹는 형태로. include_in_index 존중."""
    sigs = []
    for a in analyzed:
        sigs.append({
            "event_key": a.get("event_key"),
            "source": a.get("source"),
            "source_domain": a.get("source_domain"),
            "source_tier": a.get("source_tier", "SECONDARY"),
            "include_in_index": bool(a.get("include_in_index", False)),
            **{k: a.get(k, {"direction": 0, "importance": 1, "confidence": 0.2}) for k in INDICES},
        })
    return sigs


def compute(analyzed: list[dict], prev: dict | None) -> dict:
    sigs = _signals(analyzed)
    suff = data_sufficiency(sigs)
    rec = {"date": today_str(), "sufficiency": suff, "indices": {}}
    for key in INDICES:
        raw = raw_index(sigs, key)
        rob = robust_index(raw, suff)
        prev_raw = (prev or {}).get("indices", {}).get(key, {}).get("raw") if prev else None
        delta = round(raw - prev_raw, 4) if prev_raw is not None else None
        rec["indices"][key] = {
            "raw": raw, "robust": rob, "prev_raw": prev_raw, "delta": delta,
            "status": status_badge(key, raw, delta),
        }
    rec["event_count"] = sum(1 for s in sigs if s["include_in_index"])
    return rec


def load_history() -> list[dict]:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: list[dict]) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH) or ".", exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def append_today(rec: dict) -> list[dict]:
    """오늘 레코드를 히스토리에 추가(같은 날짜면 덮어씀). 히스토리는 추이 차트의 근거."""
    history = load_history()
    history = [h for h in history if h.get("date") != rec["date"]]
    history.append(rec)
    history.sort(key=lambda h: h["date"])
    save_history(history)
    return history
