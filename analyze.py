# -*- coding: utf-8 -*-
"""② AI 분석: 각 뉴스를 Gemini(무료 티어)에 보내 4개 지표별 방향/중요도/신뢰도와
한국어 사실·해석·검증을 받는다. 실패하면 중립 폴백(신뢰도 낮춤)으로 내려가 절대 안 죽는다."""
from __future__ import annotations
import json
import os
import time

import requests

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# 무료 티어 후보. 앞의 것이 404면 뒤로 폴백 → 모델명이 바뀌어도 안 터짐.
MODEL_FALLBACKS = [
    os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

SYSTEM_RULE = (
    "너는 한국 은행의 리스크·전략 담당자를 돕는 금융 뉴스 분석기다. "
    "입력 뉴스가 한국 은행 비즈니스에 주는 영향을 4개 관점에서 평가한다: "
    "personal(개인·가계 차주 부담), corporate(기업 차주 압력), bank_risk(은행이 지는 신용·자금조달 리스크), "
    "bank_opportunity(은행의 고객지원·상담·자금지원 기회 = 지원 수요의 크기, '위기=영업기회'가 아님). "
    "각 관점마다 direction(-2,-1,0,1,2), importance(1,2,3), confidence(0~1)를 매겨라. "
    "direction은 해당 지표를 '악화/상승'시키면 양수(단 bank_opportunity는 지원수요 증가가 양수). "
    "모든 서술(fact_ko, interpretation_ko, verification_ko, title_ko)은 반드시 한국어로 써라. "
    "사실(fact)과 해석(interpretation)과 검증(verification)을 절대 섞지 마라. "
    "이 뉴스가 한국 은행과 사실상 무관하면 include_in_index를 false로 하라."
)

_BLK = {
    "type": "object",
    "properties": {
        "direction": {"type": "integer"},
        "importance": {"type": "integer"},
        "confidence": {"type": "number"},
    },
    "required": ["direction", "importance", "confidence"],
}

# Gemini structured output은 $ref/$defs를 지원하지 않아 전부 인라인으로 풀어씀.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title_ko": {"type": "string"},
        "fact_ko": {"type": "string"},
        "interpretation_ko": {"type": "string"},
        "verification_ko": {"type": "string"},
        "include_in_index": {"type": "boolean"},
        "personal": _BLK,
        "corporate": _BLK,
        "bank_risk": _BLK,
        "bank_opportunity": _BLK,
    },
    "required": ["title_ko", "fact_ko", "interpretation_ko", "verification_ko",
                 "include_in_index", "personal", "corporate", "bank_risk", "bank_opportunity"],
}


def _neutral(reason: str, news: dict) -> dict:
    """폴백: 방향 0, 신뢰도 낮게. 원본 폴백 정책(신뢰도 상한)과 동일 취지."""
    blk = {"direction": 0, "importance": 1, "confidence": 0.2}
    return {
        "title_ko": news.get("title", ""),
        "fact_ko": (news.get("summary") or news.get("title", ""))[:300],
        "interpretation_ko": "자동 분석 실패로 중립 처리됨(폴백).",
        "verification_ko": "원문 확인 필요.",
        "include_in_index": False,
        "personal": dict(blk), "corporate": dict(blk),
        "bank_risk": dict(blk), "bank_opportunity": dict(blk),
        "analysis_mode": f"FALLBACK:{reason}",
    }


def _call_gemini(api_key: str, model: str, prompt: str) -> dict:
    url = GEMINI_ENDPOINT.format(model=model)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_RULE}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    r = requests.post(url, headers={"x-goog-api-key": api_key,
                                    "Content-Type": "application/json"},
                      data=json.dumps(body), timeout=60)
    if r.status_code == 404:
        raise FileNotFoundError(f"model {model} not found")
    if r.status_code >= 400:
        # 실패 원인을 로그에 그대로 남겨 다음에 바로 진단 가능하게 함.
        raise RuntimeError(f"gemini {r.status_code}: {r.text[:300]}")
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def analyze_one(api_key: str, news: dict) -> dict:
    prompt = (
        f"[제목] {news.get('title','')}\n"
        f"[출처] {news.get('source','')} ({news.get('source_tier','')})\n"
        f"[발행] {news.get('published_at','')}\n"
        f"[요약] {news.get('summary','')}\n"
        f"[URL] {news.get('url','')}\n\n"
        "위 뉴스를 스키마에 맞춰 분석해줘."
    )
    last_err = "unknown"
    for model in MODEL_FALLBACKS:
        for attempt in range(2):  # 스키마 실패 시 1회 재시도
            try:
                res = _call_gemini(api_key, model, prompt)
                res["analysis_mode"] = f"LLM:{model}"
                # 값 범위 방어
                for k in ("personal", "corporate", "bank_risk", "bank_opportunity"):
                    b = res.get(k) or {}
                    b["direction"] = max(-2, min(2, int(b.get("direction", 0))))
                    b["importance"] = max(1, min(3, int(b.get("importance", 1))))
                    b["confidence"] = max(0.0, min(1.0, float(b.get("confidence", 0.2))))
                    res[k] = b
                return res
            except FileNotFoundError as e:
                last_err = str(e)
                print(f"[analyze] {model} 없음 → 다음 모델로: {last_err[:120]}")
                break  # 다음 모델로
            except Exception as e:
                last_err = str(e)
                print(f"[analyze] {model} 시도 {attempt+1} 실패: {last_err[:200]}")
                time.sleep(1.5)
    print(f"[analyze] 전체 폴백 — 마지막 에러: {last_err[:200]}")
    return _neutral(last_err[:80], news)


def analyze(api_key: str, news_list: list[dict], limit: int = 12) -> list[dict]:
    """상위 `limit`건만 분석(무료 한도·시간 절약). 각 뉴스 dict에 분석 필드를 합쳐 반환."""
    out = []
    for news in news_list[:limit]:
        res = analyze_one(api_key, news)
        merged = dict(news)
        merged.update(res)
        out.append(merged)
    return out
