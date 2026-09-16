# 검색 격자 — 주제에서 질의를 만드는 법

`discover.py`는 주제 하나를 **핵심어 × 산업어 × 형식어 × 실패어**로 펼친다. 곱집합을 다 돌지 않고 빈칸을 채운다.

| 축 | 예 | 왜 |
|---|---|---|
| 핵심어 | 주제 그대로 + 동의어 2~3개 | |
| 산업어 (`--industry`) | bank, insurance, hospital, retail … | **산업어가 붙은 검색만 실제 사례를 냈다.** 일반어는 벤더 쇼츠·튜토리얼 |
| 형식어 | podcast, interview, keynote, fireside chat, panel, "lessons learned" | 형식이 발언의 성격을 정한다 — 준비된 발표 vs Q&A |
| 실패어 | "what did not work", postmortem, "went wrong", rollback, "we stopped" | 실패 서술은 찾지 않으면 나오지 않는다 |

기본 조합: `핵심어 + 산업어 + 형식어`, `핵심어 + 산업어 + 실패어`. 각 질의당 `--per-query`(기본 15)건.

## 질의 파일과 제외 목록

`--queries queries.txt` — 한 줄에 질의 하나(`#` 주석). 조직명·직함을 넣은 질의는 격자로 만들 수 없으므로 파일로 준다.
예: `Erste Group COO AI agents interview`, `US Bank chief AI officer interview 2026`.
`--exclude ids.txt` — 이미 수집한 영상 id. 후보에는 남고 `skip_reason: already collected`로 채택만 제외된다.
`--channel-kw agent agentic CEO CIO …` — 채널 목록을 제목 단어로 거를 때 주제어 대신 쓸 단어.

실측(2026-09-15, 질의 75 + 채널 16): 후보 1,382 → 10분 이상 704 → 제목 선별 95 → 자막 확보 79. 임원 직함을 넣은
질의는 팟캐스트 인터뷰(CXOTalk, CAIO, Metis Strategy)를, 채널 목록은 벤더 고객 세션(OpenAI Customer Ignite,
AWS FSI, Salesforce customer keynote)을 냈다. 채널 9개는 404·videos 탭 없음·API 차단으로 실패했다.

## 2차 실측 (2026-09-16) — 축을 넓히면 무엇이 늘어나나

질의 144(업무 프로세스명·임원 직함·컨퍼런스명·팟캐스트 프로그램명·실패어·비영어권) + 채널 60 + RSS 8.

| | |
|---|---:|
| 후보 | 3,992 |
| 10분 이상 | 2,838 |
| 유튜브 id 보유 | 1,727 |
| RSS 오디오 전용(자막 불가) | 1,111 |

**업무 프로세스 이름이 조직명보다 넓게 긁는다.** 1차의 조직명 질의는 이미 아는 기업만 냈다. "claims adjudication",
"prior authorization", "IT service desk ticket triage" 같은 프로세스명은 모르던 조직의 세션을 낸다.

**RSS는 이 스킬에서 수율이 낮다.** 팟캐스트 피드 1,139 회차 중 설명란에 유튜브 링크가 있어 자막을 받을 수 있는 것은
28건뿐이었다. 나머지는 오디오만이고 ASR 없이는 쓸 수 없다. 피드 8개 중 2개는 XML 파싱 실패, 3개는 항목 0이었다.
**팟캐스트는 RSS보다 유튜브 채널로 찾는 편이 낫다.**

**채널 핸들은 자주 틀린다.** 1차 9개, 2차 20개가 실패했다. 두 유형이다. `This channel does not have a videos tab`
(@Pega, @EY, @theCUBE, @EyeOnAI, @NICELtd, @Intercom)은 핸들이 다르거나 영상 탭이 없는 것이고,
`Unable to download API page: HTTP Error`(@Gartner_inc, @money2020, @DBSBank, @WalmartGlobalTech 등)는 접근 차단이다.
**핸들을 바꿔 재시도해도 같은 실패가 반복될 수 있다** — 1차에서 실패한 7개는 2차에 다른 주소로 넣었으나 4개가 또 실패했다.

**제목 점수로 줄여야 판독이 감당된다.** 2,838건을 다 읽힐 수는 없다. 튜토리얼 어휘(how to build, course, n8n,
step by step, beginners)에 큰 감점을 주고 agent·사례·임원 직함·산업어에 가점을 주면 744건이 남고, 상위 660건만 판독에 넘겼다.

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
