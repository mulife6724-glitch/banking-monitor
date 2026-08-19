# -*- coding: utf-8 -*-
"""[최초 1회, 내 컴퓨터에서 실행] 카카오 refresh_token 발급 도우미.

준비물: 카카오 개발자 앱의 REST API 키.
설정: 카카오 개발자 콘솔 > 내 애플리케이션 > 카카오 로그인 > 활성화 ON,
      Redirect URI에 https://localhost 추가, '동의항목'에서 '카카오톡 메시지 전송(talk_message)' 사용 설정.

실행:  python tools/get_kakao_token.py
그러면 안내에 따라: ①브라우저에서 로그인 → ②주소창의 code= 값 복붙 → ③refresh_token 출력.
그 refresh_token을 GitHub Secret(KAKAO_REFRESH_TOKEN)에 넣으면 끝.
"""
import sys
import requests

REDIRECT = "https://localhost"


def main():
    rest_key = input("카카오 REST API 키: ").strip()
    secret = input("client_secret (안 쓰면 그냥 Enter): ").strip()

    auth_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={rest_key}&redirect_uri={REDIRECT}"
        "&response_type=code&scope=talk_message"
    )
    print("\n[1] 아래 주소를 브라우저에서 열고 로그인·동의하세요:\n")
    print(auth_url)
    print("\n[2] 로그인하면 https://localhost/?code=XXXX 로 이동합니다(페이지는 안 열려도 정상).")
    print("    주소창의 code= 뒤 값을 복사해 붙여넣으세요.\n")
    code = input("code 값: ").strip()

    data = {
        "grant_type": "authorization_code",
        "client_id": rest_key,
        "redirect_uri": REDIRECT,
        "code": code,
    }
    if secret:
        data["client_secret"] = secret

    r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=20)
    if r.status_code != 200:
        print("\n[실패]", r.status_code, r.text)
        sys.exit(1)
    j = r.json()
    print("\n===== 성공! GitHub Secrets에 아래 값들을 등록하세요 =====")
    print("KAKAO_REST_KEY        =", rest_key)
    if secret:
        print("KAKAO_CLIENT_SECRET   =", secret)
    print("KAKAO_REFRESH_TOKEN   =", j.get("refresh_token"))
    print("\n(access_token은 매일 자동 갱신되므로 저장할 필요 없습니다.)")


if __name__ == "__main__":
    main()
