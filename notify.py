# -*- coding: utf-8 -*-
"""⑤ 카카오톡 '나에게 보내기' 전송.
- refresh_token으로 access_token을 갱신(access token 6시간, refresh 약 2개월).
- 카카오가 새 refresh_token을 주면(만료 1개월 미만일 때만) GitHub Secret을 자동 갱신
  (GH_PAT가 있을 때). 없으면 로그로만 알림 → 사용자가 수동 교체.
- 메시지 텍스트는 200자 제한 → 짧은 요약 + 대시보드 링크."""
from __future__ import annotations
import base64
import json
import os

import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_access_token(rest_key: str, refresh_token: str, client_secret: str | None):
    data = {"grant_type": "refresh_token", "client_id": rest_key, "refresh_token": refresh_token}
    if client_secret:
        data["client_secret"] = client_secret
    r = requests.post(TOKEN_URL, data=data, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j["access_token"], j.get("refresh_token")  # 새 refresh는 없을 수도 있음


def send_memo(access_token: str, text: str, link_url: str | None):
    template = {
        "object_type": "text",
        "text": text[:200],
        "link": {"web_url": link_url or "", "mobile_web_url": link_url or ""},
        "button_title": "대시보드 열기",
    }
    r = requests.post(MEMO_URL,
                      headers={"Authorization": f"Bearer {access_token}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)},
                      timeout=20)
    r.raise_for_status()
    return r.json()


def _update_github_secret(new_refresh: str):
    """GH_PAT가 있으면 KAKAO_REFRESH_TOKEN 시크릿을 자동 갱신. (public repo에서 토큰을
    파일로 저장하지 않기 위함.) 실패해도 조용히 넘어감."""
    pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not pat or not repo:
        print("[kakao] 새 refresh_token 수신 — GH_PAT 없음. 수동으로 KAKAO_REFRESH_TOKEN 교체 필요.")
        return
    try:
        from nacl import encoding, public  # pynacl
        h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
        pk = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=h, timeout=20).json()
        sealed = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder))
        enc = base64.b64encode(sealed.encrypt(new_refresh.encode())).decode()
        requests.put(f"https://api.github.com/repos/{repo}/actions/secrets/KAKAO_REFRESH_TOKEN",
                     headers=h, json={"encrypted_value": enc, "key_id": pk["key_id"]}, timeout=20)
        print("[kakao] KAKAO_REFRESH_TOKEN 자동 갱신 완료.")
    except Exception as e:
        print(f"[kakao] refresh_token 자동 갱신 실패: {e} — 수동 교체 필요.")


SHORT = {"personal": "개인부담", "corporate": "기업압력", "bank_risk": "은행리스크", "bank_opportunity": "은행기회"}


def build_message(record: dict, link_url: str) -> str:
    idx = record["indices"]
    lines = [f"🏦 뱅킹 브리핑 {record['date']}"]
    for k in SHORT:
        d = idx[k]
        arrow = ""
        if d["delta"] is not None:
            arrow = f" {'▲' if d['delta']>=0 else '▼'}{abs(d['delta']):.0f}"
        lines.append(f"· {SHORT[k]} {d['raw']:.0f}{arrow}")
    return "\n".join(lines)


def notify(record: dict, link_url: str) -> dict:
    rest_key = os.environ["KAKAO_REST_KEY"]
    refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET")
    access, new_refresh = refresh_access_token(rest_key, refresh_token, client_secret)
    if new_refresh and new_refresh != refresh_token:
        _update_github_secret(new_refresh)
    text = build_message(record, link_url)
    return send_memo(access, text, link_url)
