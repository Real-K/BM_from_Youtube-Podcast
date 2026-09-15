---
name: youtube-podcast-transcripts
description: 주제를 입력받아 YouTube 영상·팟캐스트를 찾고 자막(transcript)을 수집한 뒤, 자동 자막의 전사 오류를 맥락으로 교정하되 원문을 보존하고 모든 교정을 근거와 함께 기록한다. insane-search가 있으면 차단된 URL 접근에 그것을 쓴다. Korean triggers: 유튜브 팟캐스트 수집, 자막 뽑아서 정리, 전사 교정, 강연 transcript 수집, 팟캐스트에서 사례 찾기. English triggers: collect youtube transcripts on a topic, podcast transcript corpus, fix auto-caption errors, transcript correction log.
---

# YouTube · Podcast Transcript Collector

주제 하나를 받아 **영상·팟캐스트를 찾고 → 자막을 받고 → 기계적으로 정리하고 → 사람 판단으로 교정**한다.
네 단계 중 앞의 셋은 스크립트가, 마지막 하나는 Claude가 `references/tacit-knowledge.md`의 규칙으로 한다.

핵심 불변식 셋. 이것을 어기면 이 스킬을 쓸 이유가 없다.

1. **원문(VTT)은 손대지 않는다.** 정리본·교정본은 별도 파일이고 원문으로 되돌아갈 수 있어야 한다.
2. **교정은 근거가 있을 때만 한다.** 근거 없는 의심은 교정이 아니라 `[sic]` 표시다. 모든 교정은 `corrections.jsonl`에 원문·교정·근거·확신도가 남는다.
3. **자막이 말하지 않은 것을 만들어 넣지 않는다.** 끊긴 문장, 사라진 수치, 미상 화자는 그대로 미상이다.

## 언제 이 스킬을 쓰나

- "X 주제로 유튜브·팟캐스트에서 사례를 모아 줘"
- 특정 영상·채널·팟캐스트 피드의 transcript를 코퍼스로 쌓을 때
- 이미 받은 VTT의 전사 오류를 정리·교정할 때

## 절차

### 0. 도구 확인

```bash
python -m yt_dlp --version          # 없으면 pip install yt-dlp
python -c "import feedparser"       # 팟캐스트 RSS를 쓸 때만. 없으면 pip install feedparser
```

**insane-search가 설치돼 있으면** 차단·비YouTube 호스트 접근은 그쪽에 맡긴다. 위치는 프로젝트 `config/local.json`의
`insane_search_skill_dir` 또는 플러그인 캐시(`~/.claude/plugins/cache/gptaku-plugins/insane-search/<ver>/skills/insane-search`).
YouTube 자체는 insane-search도 yt-dlp를 쓰므로 이 스킬이 직접 yt-dlp를 호출한다. 그 밖의 호스트(팟캐스트 사이트,
차단된 페이지)가 실패하면 insane-search의 규칙대로 `python3 -m engine "<URL>" --trace`를 그 스킬 디렉터리에서 실행한다 —
즉흥 curl·헤더 조합으로 우회하지 않는다. insane-search가 없으면 실패를 그대로 기록하고 넘어간다.

### 1. 발견 — `scripts/discover.py`

```bash
python scripts/discover.py "<주제>" --out out/<slug> [--industry 은행 보험] [--channels channels.txt] [--rss feeds.txt] [--per-query 15] [--min-minutes 8] [--since 2024-01-01]
```

주제에서 검색 격자를 만든다(`references/search-grid.md`). **일반 키워드는 수율이 낮다** — 벤더 마케팅 쇼츠와 튜토리얼이
대부분이다. 산업어를 붙이고(`bank`, `insurance`), 실패어를 붙인 검색(`what did not work`, `lessons learned`,
`postmortem`)이 실제 사례를 낸다. 채널 목록(`--channels`)은 키워드 검색보다 낫다 — 컨퍼런스 채널·팟캐스트 채널을 직접 훑는다.

출력 `candidates.jsonl`: id·url·title·channel·duration·date·매칭된 질의·형식 추정(session/podcast/panel/short).

### 2. 수집 — `scripts/fetch_transcript.py`

```bash
python scripts/fetch_transcript.py <url-or-id> --out out/<slug>/<id> [--langs en ko]
```

**수동 자막이 있으면 그것을, 없으면 자동 자막을** 받는다. 어느 쪽인지 `meta.json`의 `transcript_auto`에 남긴다.
자동 자막에는 인명·기업명·전문용어·숫자 오류가 있다 — 지금까지 받은 영상 99편 중 수동 자막이 있는 것은 0편이었다.
그래서 이 스킬의 나머지 전부가 필요하다.

### 3. 정리 — `scripts/correct_transcript.py` (기계)

```bash
python scripts/correct_transcript.py out/<slug>/<id>/raw.vtt --out out/<slug>/<id>
```

스크립트가 하는 것은 **판단이 필요 없는 것뿐**이다.

| 하는 것 | 왜 |
|---|---|
| 롤링 중복 제거 | 자동 자막은 각 cue가 직전 줄을 반복한다. 그대로 읽으면 모든 문장이 두 번 나온다 |
| 단어 타이밍 태그·`[music]`·정렬 속성 제거 | 텍스트가 아니다 |
| 문단화 + `MM:SS` locator | 인용 위치는 정확하다 — 시간은 자막이 틀리지 않는 유일한 것이다 |
| **의심 지점 표시(`flags.jsonl`)** — 고치지 않는다 | 아래 표 |

표시하는 의심 지점:

- `pct_mismatch` — "20,000 → 3,000 … over 9%"처럼 절대값 쌍과 비율이 같이 나왔는데 산술이 안 맞는다(실제 85%). 계산값을 함께 적는다
- `adjacent_conflict` — 같은 단위의 값이 인접 발언에서 다르다("216 petabytes" / "206 petabytes")
- `number_unit_broken` — 숫자와 단위가 깨졌다("100,000memes", "4 millions 10", "90 95%")
- `spelling_cluster` — 비슷한 철자의 대문자 토큰이 여럿이다(같은 인물이 "Edison"/"Alison"으로)
- `intra_repeat` — 한 줄 안에서 어구가 반복된다("That's the best That's the best") — 자막 중복인지 실제 반복인지 구분 불가
- `host_insert` — `>>` 같은 화자 전환 표식이 문장 한가운데 있다
- `gap` — cue 사이 공백이 크다. 침묵일 수도, 줄 누락일 수도 있다
- `truncated` — 문장이 끝나지 않은 채 큰 공백이 온다

### 4. 교정 — Claude (판단)

`clean.md`와 `flags.jsonl`을 읽고 **`references/tacit-knowledge.md`의 규칙으로** `corrections.jsonl`을 쓴다.
한 줄에 한 교정:

```json
{"ts": "18:46", "kind": "number", "original": "over 9%", "corrected": "over 90% [산술: 20,000→3,000 = 85%]",
 "basis": "arithmetic", "confidence": "high", "note": "절대값을 채택하고 비율은 불채택"}
```

`kind`: proper_noun · number · unit · negation · term · speaker · repeat · host_insert · reciting · other
`basis`: arithmetic(절대값이 있어 계산됨) · external(제목·설명·공개 정보로 확인) · context(같은 영상 안의 다른 발언) ·
**none(근거 없음 → 이것은 교정이 아니라 `[sic]` 표시다. `corrected`를 비운다)**

그다음 `python scripts/apply_corrections.py out/<slug>/<id>`로 `corrected.md`를 만든다. 교정된 자리는
`⟦원문 → 교정 (근거)⟧`로 남아 되돌릴 수 있다.

**절대 하지 않는 것**
- 근거 없이 "그럴듯한" 이름·숫자로 바꾸기 — 미확인은 미확인
- 끊긴 문장을 이어 붙이기, 사라진 수치를 복원하기
- 진행자의 요약을 게스트의 발언으로 옮기기
- 벤더가 고객 대신 말한 수치를 고객 발언으로 적기
- 원문 VTT 수정

### 5. 기록 — `INDEX.md`

`run.py`가 영상마다 한 줄씩 낸다: id · 제목 · 채널 · 길이 · 자막 종류(수동/자동) · 의심 지점 수 · 교정 수 · 화자 확인 상태.
그리고 **접근 실패 목록** — 채널 없음, 자막 없음, 차단. 실패는 이유까지 적는다. 막힌 경로를 "안 된다"로만 적으면
다음 사람이 같은 곳에서 막힌다 — 이전에 "YouTube는 안 된다"고 적힌 것이 yt-dlp 미설치였다.

## 한 번에 돌리기

```bash
python run.py "<주제>" --out out/<slug> --industry 은행 보험 --per-query 15 --max-videos 20
```

발견 → 수집 → 정리까지 돌고, 교정(4단계)은 Claude 몫으로 남긴다. `INDEX.md`의 의심 지점 수가 많은 영상부터 본다.

## 이 자료가 문서와 다른 점 — 왜 모으나

문서는 홍보 검토를 거쳐 수치가 다듬어진다. 강연·팟캐스트에서는 연사가 **분모와 기간을 구어로** 말하고,
Q&A에서 **실패를 말한다.** 이전 코퍼스에서 문서 4,907건 중 측정 3요소(분모·기저선·기간)를 갖춘 것은 13건이었고,
그 결손의 최다 항목이 측정 기간이었다. 같은 조직의 강연에서는 문서에 없던 값이 나왔다("상담당 35분" vs 문서의 30분).
**대신 자막이 틀린다.** 그 두 가지를 맞바꾸는 것이 이 스킬이다.

## 출력 구조

```
out/<slug>/
  candidates.jsonl        발견 결과 전부(채택·미채택 포함, 이유)
  INDEX.md                영상별 한 줄 + 접근 실패
  <video_id>/
    meta.json             제목·채널·길이·날짜·자막 종류·언어·화자(미상이면 미상)
    raw.vtt               원문. 불변
    clean.md              중복 제거·문단화·MM:SS
    flags.jsonl           의심 지점 (기계)
    corrections.jsonl     교정 (Claude) — 근거·확신도
    corrected.md          교정 적용본. 교정 자리 표시
```

스키마는 `references/output-schema.md`.
