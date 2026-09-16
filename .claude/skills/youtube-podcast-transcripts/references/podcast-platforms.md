# 팟캐스트 플랫폼 — 어디서 찾고 어디서 전사본을 얻나

**팟캐스트에는 유튜브 같은 단일 플랫폼이 없다.** 배포는 RSS이고, Apple·Spotify·Overcast·Pocket Casts는 그 위에 얹힌
디렉터리이자 앱이다. 그래서 두 문제가 나뉜다. **프로그램을 찾는 문제**와 **전사본을 얻는 문제**다.

## 1. 찾기 — 디렉터리

| 경로 | 키 | 쓸모 |
|---|---|---|
| **Apple Podcasts Search API** (`itunes.apple.com/search?media=podcast`) | 불필요 | **이 스킬의 기본값.** 결과에 `feedUrl`이 들어 있다. 이름을 알면 거의 정확히 찾는다 |
| Podcast Index | API 키·시크릿 | 오픈 색인. 키가 있으면 주제어 발굴에 Apple보다 낫다 |
| Listen Notes · Podchaser · Podscan | API 키 | 메타데이터 중심. 무료 한도가 낮다 |
| Spotify | — | **공개 RSS를 주지 않는다.** Spotify 독점 프로그램은 이 경로로 얻을 수 없다 |
| YouTube | — | 영상이 있는 프로그램만. `discover.py`가 담당한다 |

실측(2026-09-16): 저명 프로그램 이름 34개를 Apple API로 조회해 **34개 모두 피드를 찾았다.**
반면 주제어 검색(`agentic AI enterprise`, `AI CIO`)은 질의당 결과가 2~4건에 그쳤다.
**이름을 알면 이름으로, 모르면 Podcast Index 키를 얻는 편이 낫다.**

```bash
python scripts/find_podcasts.py --shows shows.txt --out out/pods --probe 20
python scripts/find_podcasts.py --search "agentic AI" "AI CIO" --out out/pods
```

## 2. 전사본 얻기 — 네 경로의 사다리

위에서부터 시도한다. 아래로 갈수록 품질이 낮고 비용이 크다.

| 순위 | 경로 | 품질 | 실측 (저명 프로그램 34개, 최신 20회차) |
|---|---|---|---|
| 1 | **`podcast:transcript` 태그** (Podcasting 2.0) | 화자 이름과 시각이 붙는다. 가장 좋다 | **4개 프로그램** |
| 2 | 회차 설명의 **유튜브 링크** → 유튜브 자막 | 자동 자막. 화자 구분 없음 | 7개 프로그램 |
| 3 | 회차 페이지 본문에 실린 전사본 | 발행자가 올린 것. 형식이 제각각 | Latent Space·Dwarkesh에서 확인 |
| 4 | **오디오 + 음성 전사(ASR)** | 기계 전사. 고유명사·숫자 오류 | **22개 프로그램이 여기뿐**. `transcribe.py`로 처리 가능 |

즉 **저명 프로그램의 3분의 2는 오디오만 제공한다.** 전사본을 주는 곳이 예외다.

### 1순위가 되는 프로그램 (실측)

| 프로그램 | 총 회차 | 최신 20회차 중 전사 태그 |
|---|---:|---:|
| Practical AI | 373 | 20 |
| Odd Lots | 1,278 | 20 |
| CXOTalk | 557 | 10 |
| Acquired | 217 | 5 |

호스팅 업체가 갈린다. Transistor와 Omny는 태그를 붙이고, Megaphone·Simplecast·Libsyn 계열은 대체로 붙이지 않는다.
**피드 URL의 호스트만 봐도 전사본 유무를 어느 정도 예측할 수 있다.**

## 3. 순서

```bash
# 1) 프로그램 찾기 + 경로 판정
python scripts/find_podcasts.py --shows shows.txt --out out/pods --probe 20   # routes.md 생성

# 2) 전사 태그가 있는 피드에서 회차 수집
python scripts/fetch_podcast_transcript.py --feed <URL> --out out/pods/<show> --limit 60 --match agent enterprise

# 3) 태그가 없으면 유튜브 경로로
python scripts/discover.py "<프로그램명> <주제>" --out out/<slug>

# 4) 그래도 없으면 오디오 + ASR
python scripts/transcribe.py <오디오 URL> --out out/pods/<show>/<ep> --model small
```

`fetch_podcast_transcript.py`는 태그가 없는 회차를 `no_transcript.jsonl`에 오디오 URL과 함께 남긴다.
**그 파일이 곧 ASR 대기열이다.** 한 시간짜리 회차가 small 모델에서 약 18분 걸린다(실시간의 3.4배).

## 4. 주의

- **전사본이 있다고 정확한 것은 아니다.** 발행자 전사본도 ASR로 만든 것이 많다. 화자 표기는 발행자가 붙인 것이다.
  숫자·고유명사 규칙(`tacit-knowledge.md`)을 그대로 적용한다.
- **주제어 일치는 느슨하다.** 제목·요약으로 거르면 다른 주제가 섞인다. 실측에서 Odd Lots와 Acquired는
  `--match`에 걸렸으나 내용은 술집 운영과 기업사였다. 수집 뒤 판독이 필요하다.
- **한국어 팟캐스트는 이 경로에서 얇다.** Apple 검색의 한국어 결과는 뉴스 요약 프로그램이 대부분이고
  전사 태그를 붙인 곳은 없었다.
