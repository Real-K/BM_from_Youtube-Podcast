# 검색 격자 — 주제에서 질의를 만드는 법

`discover.py`는 주제 하나를 **핵심어 × 산업어 × 형식어 × 실패어**로 펼친다. 곱집합을 다 돌지 않고 빈칸을 채운다.

| 축 | 예 | 왜 |
|---|---|---|
| 핵심어 | 주제 그대로 + 동의어 2~3개 | |
| 산업어 (`--industry`) | bank, insurance, hospital, retail … | **산업어가 붙은 검색만 실제 사례를 냈다.** 일반어는 벤더 쇼츠·튜토리얼 |
| 형식어 | podcast, interview, keynote, fireside chat, panel, "lessons learned" | 형식이 발언의 성격을 정한다 — 준비된 발표 vs Q&A |
| 실패어 | "what did not work", postmortem, "went wrong", rollback, "we stopped" | 실패 서술은 찾지 않으면 나오지 않는다 |

기본 조합: `핵심어 + 산업어 + 형식어`, `핵심어 + 산업어 + 실패어`. 각 질의당 `--per-query`(기본 15)건.

## 채널 목록이 낫다

`--channels channels.txt`에 채널 URL을 한 줄씩. `--flat-playlist`로 전체 목록을 받아 제목·길이로 거른다.
컨퍼런스 채널(AWS Events, Google Cloud, Salesforce, ServiceNow…)과 팟캐스트 채널(MIT SMR, Latent Space, a16z,
Sequoia, No Priors, 11:FS…)이 키워드 검색보다 세션·인터뷰를 잘 낸다.

## 팟캐스트 RSS

`--rss feeds.txt`에 피드 URL을 한 줄씩(`feedparser` 필요). 에피소드마다:

1. 설명·링크에 YouTube 링크가 있으면 → YouTube 경로로 자막
2. 없으면 에피소드 페이지 URL을 yt-dlp에 넘긴다 — 지원 호스트면 메타는 나오지만 **자막은 거의 없다**
3. 오디오만 있고 자막이 없으면 `transcript_status: audio_only` — ASR(whisper 계열)이 필요하다. 이 스킬은 ASR을
   설치하지 않는다. 있으면 `--asr` 훅으로 붙일 수 있다(`fetch_transcript.py` 참조)

## 거르기

- `--min-minutes 8` — 쇼츠·예고편 제외 (기본)
- `--since` — 날짜. **검색·채널 목록(flat)에는 업로드 날짜가 없다** — 날짜가 있는 항목(RSS 등)에만 걸리고, 나머지는 `fetch_transcript.py`의 `meta.json`에서 확인한다
- 제목에 "trailer", "teaser", "#shorts" → 제외
- 같은 영상이 여러 질의에 잡히면 하나로, `matched_queries`에 전부 기록

## 형식 추정 (`format`)

제목·채널·설명에서 `session / keynote / podcast / interview / panel / webinar / demo / short` 추정.
**추정이다.** 컨퍼런스 발표가 "podcast" 검색에 잡힌다 — 판독 뒤 `meta.json`에서 고친다.
