# -*- coding: utf-8 -*-
"""① 뉴스 수집: RSS 피드(한국 + 글로벌)에서 최근 뉴스를 긁고, 최근 N시간 것만
남긴 뒤 같은 사건을 중복 제거한다. 무료·안정적. 피드 실패는 조용히 건너뛴다."""
from __future__ import annotations
import datetime as _dt
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests
import yaml

from util import KST, now_kst, tier_kind

UA = {"User-Agent": "banking-monitor/1.0 (personal morning brief)"}


def _load_feeds(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("feeds", [])


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _fetch_feed(feed: dict, since: _dt.datetime) -> list[dict]:
    r = requests.get(feed["url"], headers=UA, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        if not title or not pub:
            continue
        try:
            dt = parsedate_to_datetime(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
        except Exception:
            continue
        if dt.astimezone(KST) < since:
            continue
        out.append({
            "title": title,
            "url": link,
            "source": feed.get("name", "RSS"),
            "source_tier": feed.get("tier", "SECONDARY"),
            "source_tier_kind": tier_kind(feed.get("tier", "SECONDARY")),
            "source_domain": _domain(link),
            "published_at": dt.astimezone(KST).isoformat(),
            "summary": desc[:600],
            "lang": feed.get("lang", "en"),
        })
    return out


def collect(feeds_path: str, hours: int = 28) -> tuple[list[dict], list[dict]]:
    """반환: (뉴스 리스트, 실패 목록). 최근 `hours` 시간 내 발행분만."""
    since = now_kst() - _dt.timedelta(hours=hours)
    rows, failures = [], []
    for feed in _load_feeds(feeds_path):
        if not feed.get("enabled", True):
            continue
        try:
            rows.extend(_fetch_feed(feed, since))
        except Exception as e:  # 개별 피드 실패는 전체를 죽이지 않음
            failures.append({"feed": feed.get("name"), "error": str(e)})
    return dedupe(rows), failures


def dedupe(rows: list[dict]) -> list[dict]:
    """제목 정규화 기준으로 같은 사건 묶기. 대표는 출처 등급이 높은 것.
    나머지는 corroborating(교차확인) 소스로 기록."""
    import re
    pri = {"OFFICIAL": 0, "PRIMARY_CORPORATE": 1, "WIRE": 2, "MAJOR_MEDIA": 3, "SECONDARY": 4}
    groups: dict[str, list[dict]] = {}
    for r in rows:
        key = re.sub(r"[^a-z0-9가-힣]+", "", r["title"].lower())[:60] or r["url"]
        groups.setdefault(key, []).append(r)
    out = []
    for key, g in groups.items():
        g.sort(key=lambda x: (pri.get(x.get("source_tier_kind", "SECONDARY"), 9), x.get("published_at", "")))
        rep = dict(g[0])
        rep["event_key"] = key
        rep["corroborating_source_count"] = len(g)
        rep["corroborating_sources"] = " | ".join(sorted({x["source"] for x in g}))
        rep["corroborating_domains"] = " | ".join(sorted({x["source_domain"] for x in g if x.get("source_domain")}))
        out.append(rep)
    # 최신 발행 우선
    out.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return out
