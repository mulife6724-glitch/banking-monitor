# -*- coding: utf-8 -*-
"""아침 브리핑 오케스트레이터: ①수집 → ②AI분석 → ③점수 → ④대시보드 → ⑤카톡.
어느 단계가 실패해도 가능한 만큼 진행하고, 마지막에 요약을 출력한다.

환경변수:
  GEMINI_API_KEY        (필수) Gemini 무료 API 키
  KAKAO_REST_KEY        (전송 시) 카카오 REST API 키
  KAKAO_REFRESH_TOKEN   (전송 시) 카카오 refresh token
  KAKAO_CLIENT_SECRET   (선택) 카카오 client secret 사용 시
  DASHBOARD_URL         (선택) 카톡에 넣을 GitHub Pages 주소
  FEEDS_PATH            (선택) 기본 feeds.yaml
  ANALYZE_LIMIT         (선택) 분석할 최대 뉴스 수 (기본 12)

옵션:
  --offline <sample.json>  네트워크 없이 샘플 뉴스로 전 과정 테스트(수집/전송 생략)
"""
from __future__ import annotations
import argparse
import json
import os
import sys

import collect, analyze, score, render, notify


def run(offline: str | None = None):
    feeds_path = os.environ.get("FEEDS_PATH", "feeds.yaml")
    limit = int(os.environ.get("ANALYZE_LIMIT", "12"))
    meta = {"failures": []}

    # ① 수집
    if offline:
        with open(offline, encoding="utf-8") as f:
            news = json.load(f)
        news = collect.dedupe(news)
        print(f"[collect] offline sample: {len(news)}건")
    else:
        news, failures = collect.collect(feeds_path)
        meta["failures"] = failures
        print(f"[collect] {len(news)}건 수집, 실패 피드 {len(failures)}개")
        for fa in failures:
            print("  - 실패:", fa["feed"], fa["error"][:80])

    if not news:
        print("[collect] 수집된 뉴스 없음 — 종료(대시보드 갱신 안 함)")
        return 0

    # ② AI 분석
    api_key = os.environ.get("GEMINI_API_KEY")
    if offline == "MOCK" or (offline and not api_key):
        analyzed = _mock_analyze(news)
        print(f"[analyze] MOCK 분석 {len(analyzed)}건")
    else:
        if not api_key:
            print("[analyze] GEMINI_API_KEY 없음 — 중단")
            return 2
        analyzed = analyze.analyze(api_key, news, limit=limit)
        fb = sum(1 for a in analyzed if str(a.get("analysis_mode", "")).startswith("FALLBACK"))
        print(f"[analyze] {len(analyzed)}건 분석 (폴백 {fb}건)")

    # ③ 점수 + 히스토리
    history = score.load_history()
    prev = history[-1] if history else None
    record = score.compute(analyzed, prev)
    history = score.append_today(record)
    print(f"[score] {record['date']} " + " ".join(
        f"{k}={record['indices'][k]['raw']}" for k in record["indices"]))

    # ④ 대시보드
    out = render.write(record, analyzed, history, meta)
    print(f"[render] {out} 생성")

    # ⑤ 전송
    if offline:
        print("[notify] offline 모드 — 전송 생략")
        return 0
    if os.environ.get("KAKAO_REST_KEY") and os.environ.get("KAKAO_REFRESH_TOKEN"):
        try:
            res = notify.notify(record, os.environ.get("DASHBOARD_URL", ""))
            print("[notify] 카카오 전송 완료:", res)
        except Exception as e:
            print("[notify] 카카오 전송 실패(대시보드는 정상 갱신됨):", str(e)[:120])
    else:
        print("[notify] 카카오 키 없음 — 전송 생략(대시보드만 갱신)")
    return 0


def _mock_analyze(news):
    """테스트용 가짜 분석: 결정론적으로 방향을 흩뿌린다."""
    out = []
    for i, n in enumerate(news):
        sign = [1, -1, 2, 0, 1][i % 5]
        blk = lambda d, imp, c: {"direction": d, "importance": imp, "confidence": c}
        out.append({**n,
                    "title_ko": "[샘플] " + n["title"][:40],
                    "fact_ko": (n.get("summary") or n["title"])[:120],
                    "interpretation_ko": "샘플 해석입니다. 실제로는 Gemini가 한국어로 작성.",
                    "verification_ko": "원문 및 차주 익스포저 확인 필요.",
                    "include_in_index": (i % 4 != 3),
                    "personal": blk(sign, 2, 0.8),
                    "corporate": blk(min(2, sign + 1), 2, 0.85),
                    "bank_risk": blk(sign, 2, 0.9),
                    "bank_opportunity": blk(1 if sign >= 0 else 0, 1, 0.7),
                    "analysis_mode": "MOCK"})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", nargs="?", const="MOCK", default=None,
                    help="샘플 JSON 경로(없이 주면 내장 MOCK 분석)")
    args = ap.parse_args()
    sys.exit(run(args.offline))
