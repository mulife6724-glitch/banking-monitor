# 🏦 AI 뱅킹 인텔리전스 — 매일 아침 카톡 브리핑 세팅 가이드 (평평한 버전)

이 파일들을 GitHub에 올리면 **매일 아침 7시(KST)** 에 자동으로
뉴스 수집 → AI 분석 → 점수 → 대시보드(GitHub Pages) → **카카오톡 '나에게 보내기'** 까지 돌아갑니다.
서버 필요 없음 · 전부 무료.

> 이 버전은 **폴더가 거의 없어서** 드래그 업로드가 안 꼬입니다.
> 폴더가 꼭 필요한 파일(`.github/workflows/daily.yml`) 하나만 웹에서 만들면 됩니다.

---

## STEP 0. 파일 올리기

### 0-A. 나머지 파일 전부 드래그 업로드
저장소 > **Add file > Upload files** → 아래 파일들을 **한꺼번에 드래그**해서 올리고 **Commit changes**:

```
main.py  util.py  collect.py  analyze.py  score.py  render.py  notify.py
get_kakao_token.py  feeds.yaml  requirements.txt  index.html  README_SETUP.md  .gitignore
```

> 폴더가 없으니 이번엔 납작해질 일이 없습니다. (`daily.yml`은 여기서 올리지 말고 0-B에서 따로 만듭니다.)

### 0-B. 워크플로우 파일만 웹에서 만들기 (폴더 자동 생성)
자동 실행의 핵심 파일입니다. 드래그 대신 이렇게:

1. 저장소 > **Add file > Create new file**.
2. 파일 이름 칸에 정확히 이렇게 입력: **`.github/workflows/daily.yml`**
   - `/` 를 칠 때마다 폴더가 자동으로 만들어집니다.
3. 아래 내용(함께 받은 `daily.yml` 파일 내용)을 **전부 복사해 붙여넣기**.
4. **Commit changes**.

이제 저장소에 `main.py` 들과 `.github/workflows/daily.yml` 이 보이면 준비 끝.

---

## STEP 1. Gemini 무료 API 키 (구글 계정)
1. https://aistudio.google.com/apikey → 로그인 → **Create API key** → 키 복사(`AIza...`).
2. 카드 불필요. STEP 4에서 `GEMINI_API_KEY` 로 등록.

---

## STEP 2. 카카오 '나에게 보내기' 준비 (카카오 계정)

### 2-1. 앱 + 키
1. https://developers.kakao.com → **내 애플리케이션 > 애플리케이션 추가하기**.
2. 앱 > **앱 키** 에서 **REST API 키** 복사.

### 2-2. 로그인·메시지 권한
1. **카카오 로그인 > 활성화 ON**.
2. **Redirect URI** 에 `https://localhost` 추가 → 저장.
3. **카카오 로그인 > 동의항목** 에서 **카카오톡 메시지 전송(talk_message)** 사용 ON.

### 2-3. refresh token 받기 (최초 1회, 내 컴퓨터에서)
```bash
pip install requests
python get_kakao_token.py
```
안내대로 REST 키 입력 → 출력된 주소 로그인·동의 → 주소창 `code=` 값 붙여넣기
→ **KAKAO_REFRESH_TOKEN** 값 복사.

---

## STEP 3. GitHub Pages 켜기 (대시보드 주소)
1. **Settings > Pages**.
2. **Source: Deploy from a branch** → Branch: **`main`** / 폴더: **`/ (root)`** → **Save**.
3. 뜨는 주소 `https://<내아이디>.github.io/banking-monitor/` 복사 → STEP 4의 `DASHBOARD_URL`.

---

## STEP 4. Secrets · Variables 등록
**Settings > Secrets and variables > Actions**.

**Secrets 탭 → New repository secret**
| 이름 | 값 |
|---|---|
| `GEMINI_API_KEY` | STEP 1 키 |
| `KAKAO_REST_KEY` | STEP 2-1 REST 키 |
| `KAKAO_REFRESH_TOKEN` | STEP 2-3 토큰 |
| `KAKAO_CLIENT_SECRET` | (client secret 켠 경우만) |

**Variables 탭 → New repository variable**
| 이름 | 값 |
|---|---|
| `DASHBOARD_URL` | STEP 3 주소 |
| `GEMINI_MODEL` | (선택) 기본 `gemini-2.5-flash` |

---

## STEP 5. (선택·권장) 토큰 자동 갱신용 GH_PAT
1. https://github.com/settings/tokens?type=beta → Fine-grained token, 이 저장소만, **Secrets: Read and write**.
2. Secret `GH_PAT` 로 등록. → 카카오 토큰이 만료 직전 자동 교체됨(안 넣으면 약 2개월마다 STEP 2-3 재실행).

---

## STEP 6. 실행 테스트
1. **Actions** 탭 > "아침 뱅킹 브리핑" > **Run workflow**.
2. 로그에 `[collect]…[analyze]…[score]…[render]…[notify] 카카오 전송 완료` 나오면 성공.
3. 카톡 도착 + `DASHBOARD_URL` 에 대시보드 표시.

이후 매일 아침 7시(KST) 자동 실행. 시간 변경은 `.github/workflows/daily.yml` 의 `cron` 숫자만.

---

## 문제 해결
- **카톡만 안 옴** → `KAKAO_REFRESH_TOKEN` 재발급(STEP 2-3). Actions 로그 `[notify]` 확인.
- **뉴스 0건** → `feeds.yaml` 에 피드 추가.
- **AI 폴백 많음** → `GEMINI_MODEL` 을 `gemini-2.0-flash` 등으로 변경.
- **대시보드 404** → Pages 소스가 `main /(root)` 인지, 첫 실행 후 `index.html` 이 갱신됐는지 확인.

## 나중에 수정
- 대시보드 모양 → `render.py`
- 뉴스 소스 → `feeds.yaml`
- 아침 시간 → `.github/workflows/daily.yml` 의 cron
