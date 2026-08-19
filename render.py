# -*- coding: utf-8 -*-
"""④ 대시보드 굽기: history + 오늘 분석으로 자체완결형 한국어 HTML 생성.
외부 라이브러리 0 (차트는 SVG 직접 그림). docs/index.html 로 출력 → GitHub Pages."""
from __future__ import annotations
import html
import os

from util import INDICES

OUT_PATH = os.environ.get("DASHBOARD_PATH", "index.html")

COLORS = {"personal": "#f59e0b", "corporate": "#ef4444",
          "bank_risk": "#8b5cf6", "bank_opportunity": "#10b981"}
STATUS_KO = {"ELEVATED": "상승 구간", "MATERIAL_RISE": "뚜렷한 상승", "MATERIAL_FALL": "뚜렷한 하락",
             "NEUTRAL": "중립", "HIGH": "높음", "WATCH": "주의"}


def esc(x): return html.escape(str(x or ""))


def _spark(vals, color, w=300, h=52, pad=6):
    if len(vals) < 2:
        vals = vals * 2 if vals else [50, 50]
    n = len(vals)
    x = lambda i: pad + (w - 2 * pad) * i / (n - 1)
    y = lambda v: h - pad - (h - 2 * pad) * v / 100
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    area = f"{pad},{h-pad} " + pts + f" {w-pad},{h-pad}"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark">'
            f'<polygon points="{area}" fill="{color}" opacity="0.10"/>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{x(n-1):.1f}" cy="{y(vals[-1]):.1f}" r="3.2" fill="{color}"/></svg>')


def _multiline(history, w=680, h=250, pad=34):
    dates = [h["date"] for h in history] or ["-"]
    n = max(len(dates), 2)
    x = lambda i: pad + (w - pad - 12) * i / (n - 1)
    y = lambda v: h - pad - (h - 2 * pad) * v / 100
    g = ""
    for gv in (0, 25, 50, 75, 100):
        yy = y(gv)
        g += f'<line x1="{pad}" y1="{yy:.1f}" x2="{w-12}" y2="{yy:.1f}" stroke="#1f2937"/>'
        g += f'<text x="{pad-6}" y="{yy+3:.1f}" text-anchor="end" fill="#6b7280" font-size="10">{gv}</text>'
    idxs = sorted({0, len(dates) // 2, len(dates) - 1})
    for i in idxs:
        if 0 <= i < len(dates):
            g += f'<text x="{x(i):.1f}" y="{h-12}" text-anchor="middle" fill="#6b7280" font-size="10">{dates[i][5:]}</text>'
    for key in INDICES:
        series = [rec["indices"].get(key, {}).get("raw", 50) for rec in history] or [50, 50]
        if len(series) < 2:
            series = series * 2
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(series))
        g += f'<polyline points="{pts}" fill="none" stroke="{COLORS[key]}" stroke-width="2.2" opacity="0.9"/>'
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{g}</svg>'


def _dir_tag(key, d):
    d = int(d)
    good_up = INDICES[key][1]
    if d == 0:
        return ("영향 없음", "neutral")
    if key == "bank_opportunity":
        return ("기회 ↑", "up-good") if d > 0 else ("기회 ↓", "down-bad")
    return ("압력 ↑", "up-bad") if d > 0 else ("압력 ↓ 완화", "down-good")


def _contrib(analyzed, key):
    rows = []
    for a in analyzed:
        if not a.get("include_in_index"):
            continue
        blk = a.get(key) or {}
        d = int(blk.get("direction", 0))
        if d == 0:
            continue
        w = abs(d) * float(blk.get("importance", 1)) * float(blk.get("confidence", 0))
        rows.append((w, d, blk, a))
    rows.sort(key=lambda t: -t[0])
    return rows


def _sig_block(analyzed, key):
    rows = _contrib(analyzed, key)
    if not rows:
        return '<div class="empty">이 지표를 움직인 반영 시그널이 없습니다.</div>'
    out = ""
    for w, d, blk, a in rows:
        tag, cls = _dir_tag(key, d)
        out += f"""
        <div class="ev">
          <div class="ev-top"><span class="tag {cls}">{tag}</span>
            <a href="{esc(a.get('url','#'))}" target="_blank" class="ev-title">{esc(a.get('title_ko') or a.get('title'))}</a></div>
          <div class="ev-meta">중요도 {blk.get('importance')} · 신뢰 {blk.get('confidence')} · {esc(a.get('source'))}</div>
          <div class="kv"><span class="k fact">사실</span><span class="v">{esc(a.get('fact_ko'))}</span></div>
          <div class="kv"><span class="k interp">AI 해석</span><span class="v">{esc(a.get('interpretation_ko'))}</span></div>
          <div class="kv"><span class="k verify">검증 필요</span><span class="v">{esc(a.get('verification_ko'))}</span></div>
        </div>"""
    return out


GUIDE = """
<details class="acc" open><summary>① 이 4개 지수가 뭔가요?</summary><div class="acc-body g">
<p><b>개인 부담 지수</b> — 가계·개인 차주가 받는 압력(물가·금리·실질소득). 높을수록 부담 큼.</p>
<p><b>기업 압력 지수</b> — 기업 차주의 비용·자금조달·현금흐름 압박.</p>
<p><b>은행 리스크 지수</b> — 은행이 떠안는 신용·자금조달 리스크.</p>
<p><b>은행 기회 지수</b> — 정식 명칭 <b>고객지원·상담 기회지수</b>. 자금지원·환/금리 리스크 관리·정책금융 안내 등 은행이 고객을 도울 여지(지원 수요). “위기=영업기회”가 아님.</p></div></details>
<details class="acc"><summary>② 어떻게 만들어진 숫자인가요?</summary><div class="acc-body g">
<p>AI는 각 뉴스에 <b>방향·중요도·신뢰도</b> 라벨만 답니다. <b>점수는 코드가 결정론적으로</b> 계산 — 같은 입력이면 언제나 같은 숫자.</p>
<p class="mono">가중치 = 중요도 × 신뢰도<br>가중방향 = Σ(방향 × 가중치) / Σ(가중치)<br>지수 = 50 + 25 × 가중방향 (0~100)</p>
<p><b>방향</b> −2·−1·0·+1·+2 | <b>중요도</b> 1·2·3 | <b>신뢰도</b> 0~1. 같은 사건은 지수에 한 번만 반영.</p></div></details>
<details class="acc"><summary>③ 이 수치, 그래서 높은 거예요?</summary><div class="acc-body g">
<p><b>50이 중립</b>. 모든 가중 신호가 +2면 100, −2면 0.</p>
<p>상태 기준: <span class="th">WATCH ≥ 55</span> <span class="th">ELEVATED ≥ 60</span> <span class="th">HIGH ≥ 70</span>, 전일 대비 <b>|Δ|≥5</b>면 뚜렷한 변화.</p></div></details>
<details class="acc"><summary>④ Raw vs Robust — 얼마나 믿어도 돼요?</summary><div class="acc-body g">
<p><b>Raw</b>는 방향만 반영. <b>Robust</b>는 근거가 부족할수록 50(중립)으로 끌어당겨 극단을 눌러줌.</p>
<p class="mono">Robust = 50 + (근거충분도/100) × (Raw − 50)</p>
<p>근거충분도 = 사건 수·출처 다양성·출처 등급(공식&gt;통신사&gt;주요언론…)으로 계산.</p></div></details>
<details class="acc"><summary>⑤ 한계 — 이걸로 뭘 하면 안 되나요?</summary><div class="acc-body g">
<p>부도확률이 아니라 그날 증거집합의 방향 요약. 매크로 뉴스는 <b>차주 개별 심사를 대체하지 못함</b>.</p></div></details>
"""


def render(record: dict, analyzed: list[dict], history: list[dict], meta: dict) -> str:
    idx = record["indices"]
    # cards
    cards = ""
    for key in INDICES:
        label = INDICES[key][0]
        good_up = INDICES[key][1]
        d = idx[key]
        val = d["raw"]
        delta = d["delta"]
        color = COLORS[key]
        series = [rec["indices"].get(key, {}).get("raw", 50) for rec in history]
        ncon = len(_contrib(analyzed, key))
        if delta is None:
            deltahtml = '<span class="status">기준일</span>'
        else:
            up = delta >= 0
            arrow = "▲" if up else "▼"
            dcolor = ("#34d399" if up else "#f87171") if good_up else ("#f87171" if up else "#34d399")
            st = STATUS_KO.get(d["status"], d["status"])
            deltahtml = f'<span style="color:{dcolor}">{arrow} {abs(delta):.1f}</span> <span class="status">{st}</span>'
        cards += f"""
        <div class="card">
          <div class="card-top"><span class="dot" style="background:{color}"></span><span class="label">{label}</span></div>
          <div class="value">{val:.1f}</div>
          <div class="delta">{deltahtml}</div>
          <div class="rob">Robust {d['robust']:.1f}</div>
          {_spark(series, color)}
          <details class="why"><summary>이 점수 왜 이래? · {ncon}건 →</summary>
            <div class="why-body">{_sig_block(analyzed, key)}</div></details>
        </div>"""

    legend = "".join(f'<span class="lg"><span class="dot" style="background:{COLORS[k]}"></span>{INDICES[k][0]}</span>' for k in INDICES)

    # news
    news_html = ""
    for a in analyzed:
        news_html += f"""
        <div class="nw"><div class="nw-top">
            <span class="cat">{esc(a.get('source'))}</span>
            <a href="{esc(a.get('url','#'))}" target="_blank" class="nw-title">{esc(a.get('title_ko') or a.get('title'))}</a></div>
          <div class="nw-fact">{esc(a.get('fact_ko'))}</div>
          <div class="nw-src">{esc(a.get('published_at','')[:16].replace('T',' '))} · 신뢰 {(a.get('bank_risk') or {}).get('confidence','')}</div></div>"""

    warn = ""
    if meta.get("failures"):
        warn = f'<div class="warn">⚠ 수집 실패 피드 {len(meta["failures"])}개 — 표시된 결과는 나머지 소스 기준</div>'
    fb = sum(1 for a in analyzed if str(a.get("analysis_mode", "")).startswith("FALLBACK"))
    if fb:
        warn += f'<div class="warn">⚠ AI 분석 폴백 {fb}건 (중립 처리, 신뢰도 낮춤)</div>'

    return _PAGE.format(
        date=esc(record["date"]), cards=cards, chart=_multiline(history),
        legend=legend, news=news_html, guide=GUIDE, warn=warn,
        suff=record.get("sufficiency", 0), ev=record.get("event_count", 0),
        nnews=len(analyzed),
    )


def write(record, analyzed, history, meta):
    html_str = render(record, analyzed, history, meta)
    os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_str)
    return OUT_PATH


_PAGE = """<!DOCTYPE html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 뱅킹 인텔리전스 · 아침 브리핑</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0b0f17;color:#e5e7eb;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;padding:16px;max-width:760px;margin:0 auto;-webkit-text-size-adjust:100%}}
.head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}}
.head h1{{font-size:18px;font-weight:700}} .date{{color:#9ca3af;font-size:13px}}
.sub{{color:#6b7280;font-size:12px;margin-bottom:14px}}
.warn{{background:#2a1c10;border:1px solid #4a3418;color:#fbbf24;font-size:11.5px;padding:8px 11px;border-radius:9px;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#131a26;border:1px solid #1f2937;border-radius:14px;padding:14px}}
.card-top{{display:flex;align-items:center;gap:7px;margin-bottom:8px}}
.dot{{width:9px;height:9px;border-radius:50%;display:inline-block}}
.label{{font-size:12.5px;color:#9ca3af;font-weight:600}}
.value{{font-size:30px;font-weight:800;letter-spacing:-1px}}
.delta{{font-size:12.5px;font-weight:700;margin:2px 0 1px}} .status{{color:#6b7280;font-weight:600;margin-left:3px}}
.rob{{font-size:10.5px;color:#6b7280;margin-bottom:7px}}
.spark{{width:100%;height:48px;display:block;margin-bottom:6px}}
.why{{border-top:1px solid #1f2937;padding-top:8px}}
.why>summary{{cursor:pointer;font-size:12px;color:#60a5fa;font-weight:600;list-style:none}}
.why>summary::-webkit-details-marker{{display:none}}
.ev{{background:#0e1521;border:1px solid #1c2534;border-radius:10px;padding:10px;margin:8px 0}}
.ev-top{{display:flex;gap:7px;align-items:flex-start;margin-bottom:5px}}
.ev-title{{color:#e5e7eb;font-size:12.5px;font-weight:600;text-decoration:none;line-height:1.4}}
.tag{{flex-shrink:0;font-size:10px;font-weight:700;padding:2px 6px;border-radius:6px;white-space:nowrap}}
.up-bad,.down-bad{{color:#fca5a5;background:#2a1515}} .down-good,.up-good{{color:#86efac;background:#132a1c}} .neutral{{color:#9ca3af;background:#1c2534}}
.ev-meta{{font-size:10.5px;color:#6b7280;margin-bottom:7px}}
.kv{{display:flex;gap:7px;margin:4px 0;font-size:11.5px;line-height:1.5}}
.k{{flex-shrink:0;font-weight:700;font-size:9.5px;padding:1px 5px;border-radius:5px;height:fit-content;margin-top:1px}}
.k.fact{{color:#93c5fd;background:#172033}} .k.interp{{color:#c4b5fd;background:#1e1a33}} .k.verify{{color:#fcd34d;background:#2a2410}}
.v{{color:#cbd5e1}}
.panel{{background:#131a26;border:1px solid #1f2937;border-radius:14px;padding:16px;margin-bottom:20px}}
.panel h2{{font-size:14px;margin-bottom:10px}}
.chart{{width:100%;height:auto;display:block}}
.legend{{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px}}
.lg{{font-size:11.5px;color:#9ca3af;display:flex;align-items:center;gap:6px}}
.nw{{border-top:1px solid #1f2937;padding:11px 0}} .nw:first-of-type{{border-top:none;padding-top:0}}
.nw-top{{display:flex;gap:8px;align-items:flex-start}}
.cat{{flex-shrink:0;font-size:10px;font-weight:700;color:#93c5fd;background:#172033;border:1px solid #24304a;padding:2px 7px;border-radius:20px;white-space:nowrap}}
.nw-title{{color:#e5e7eb;font-size:13px;font-weight:600;text-decoration:none;line-height:1.4}}
.nw-fact{{color:#9ca3af;font-size:12px;line-height:1.55;margin:6px 0 4px}}
.nw-src{{color:#6b7280;font-size:11px}}
.acc{{border:1px solid #1c2534;border-radius:10px;margin-bottom:8px;overflow:hidden}}
.acc>summary{{cursor:pointer;padding:11px 13px;font-size:13px;font-weight:600;color:#e5e7eb;list-style:none;background:#0e1521}}
.acc>summary::-webkit-details-marker{{display:none}}
.acc-body{{padding:6px 13px 12px}}
.g p{{color:#cbd5e1;font-size:12.5px;line-height:1.65;margin:7px 0}} .g b{{color:#e5e7eb}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;color:#93c5fd;background:#0e1521;border:1px solid #1c2534;border-radius:8px;padding:9px 11px;line-height:1.8}}
.th{{display:inline-block;font-size:10.5px;font-weight:700;color:#fcd34d;background:#2a2410;border-radius:6px;padding:2px 7px;margin:2px 3px 0 0}}
.empty{{color:#6b7280;font-size:12px;padding:4px}}
.foot{{color:#4b5563;font-size:11px;text-align:center;margin-top:8px;line-height:1.7}}
</style></head><body>
<div class="head"><h1>🏦 AI 뱅킹 인텔리전스</h1><span class="date">{date} · 아침 브리핑</span></div>
<div class="sub">요약을 먼저, 각 점수는 탭해서 “왜 이래?”까지 · 오늘 반영 사건 {ev}건 · 근거충분도 {suff}</div>
{warn}
<div class="grid">{cards}</div>
<div class="panel"><h2>📈 관측 추이 (0–100)</h2>{chart}<div class="legend">{legend}</div></div>
<div class="panel"><h2>📰 오늘의 뉴스 · {nnews}건</h2>
<div class="sub" style="margin:-2px 0 10px">위 지수의 근거가 된 원본 뉴스. 제목을 누르면 출처로 이동.</div>{news}</div>
<div class="panel"><h2>📖 이 화면 읽는 법 · 설명서</h2>{guide}</div>
<div class="foot">결정론적 스코어 · 소스 추적/검증 분리 · 서버 없이 매일 아침 새로 구워지는 정적 페이지 · 외부 라이브러리 0</div>
</body></html>"""
