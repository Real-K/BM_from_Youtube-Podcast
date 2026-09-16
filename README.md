# BM from YouTube · Podcast

주제 하나를 주면 **YouTube 영상과 팟캐스트를 찾아 자막(transcript)을 모으고, 자동 자막의 전사 오류를 맥락으로
교정하되 원문을 보존하고 교정마다 근거를 남기는** Claude Code 스킬.

문서는 홍보 검토를 거쳐 수치가 다듬어진다. 강연·팟캐스트에서는 연사가 분모와 기간을 구어로 말하고 Q&A에서
실패를 말한다. 대신 자막이 틀린다 — 인명·기업명·전문용어·숫자·부정어. 이 스킬은 그 둘을 맞바꾼다.
영상 260편을 읽으며 정한 규칙이 `references/tacit-knowledge.md`에 있다.

## 설치

```bash
git clone https://github.com/Real-K/BM_from_Youtube-Podcast
cd BM_from_Youtube-Podcast
pip install -r requirements.txt        # yt-dlp, insane-search 엔진 의존성(curl_cffi 등), feedparser
```

이 폴더를 Claude Code에서 열면 `.claude/skills/` 아래 두 스킬(`youtube-podcast-transcripts`, `insane-search`)이 잡힌다.
다른 프로젝트에서 쓰려면 두 디렉터리를 그 프로젝트의 `.claude/skills/`에 복사한다.

[insane-search](https://github.com/fivetaku/insane-search) 0.16.3이 `.claude/skills/insane-search/`에 **통째로 들어 있다**
(MIT, 출처·수정 내역은 `UPSTREAM.md`). 별도 플러그인 설치 없이 차단된 URL·비YouTube 호스트 접근에 쓴다.
YouTube 자체는 yt-dlp면 된다 — insane-search도 YouTube에는 yt-dlp를 쓴다.

## 쓰기

```bash
python run.py "agentic AI in banking operations" --out out/agentic-banking --industry bank insurance --max-videos 10
```

```
out/agentic-banking/
  candidates.jsonl     발견 결과 전부 + 이유
  INDEX.md             영상별 한 줄 · 접근 실패
  <video_id>/
    raw.vtt            원문 — 불변
    meta.json          서지 · 자막 종류(수동/자동) · 화자(미확인)
    clean.md           중복 제거 · 문단 · MM:SS
    flags.jsonl        의심 지점 (기계가 표시만)
    corrections.jsonl  교정 (Claude가 근거와 함께)
    corrected.md       교정 적용본 — 교정 자리 ⟦원문 → 교정 (근거)⟧
```

그다음 Claude Code에서 "out/agentic-banking의 flags를 보고 교정해 줘" — 스킬이 규칙대로 `corrections.jsonl`을 쓰고
`apply_corrections.py`로 교정본을 만든다.

## 세 불변식

1. **원문 VTT는 손대지 않는다.** 교정본은 별도 파일이고 원문으로 되돌아갈 수 있다.
2. **교정은 근거가 있을 때만.** 산술(절대값으로 검산) · 외부(제목·공개 정보) · 문맥(같은 영상의 다른 발언).
   근거가 없으면 `[sic]`이지 교정이 아니다.
3. **자막이 말하지 않은 것을 만들어 넣지 않는다.** 끊긴 문장·사라진 수치·미상 화자는 그대로.

## 무엇이 표시되나 (기계) · 무엇을 고치나 (사람)

| 기계가 표시 | 예 | 사람이 하는 것 |
|---|---|---|
| `pct_mismatch` | "20,000 → 3,000 … over 9%" (실제 85%) | 절대값 채택, 비율 불채택 |
| `adjacent_conflict` | "216 petabytes" / "206 petabytes" | 둘 다 적고 고르지 않음 |
| `number_unit_broken` | "100,000memes", "4 millions 10", "90 95%" | 같은 영상에 단위 설명이 있을 때만 교정 |
| `spelling_cluster` | "Edison" / "Alison" | 공개 정보로 확인되면 교정, 아니면 `[sic: A/B]` |
| `intra_repeat` · `host_insert` · `truncated` | "That's the best That's the best", ">> Yeah. >>" | 그대로 둔다 |
| — (기계가 못 잡음) | "I don't trust **deterministic**…"(non- 누락) | 앞뒤 논리로 후보, 확신도 medium 이하 |

전체 규칙은 `references/correction-rules.md`, 관찰 기록은 `references/tacit-knowledge.md`.

## 한계

- 수동 자막은 드물다. 최근 두 배치 161편 중 32편(20%)이었고 나머지는 자동 자막이다.
- 자동 자막은 화자를 구분하지 않는다. 화자 귀속은 항상 추정·미확인이다.
- 오디오만 있는 팟캐스트(자막 없음)는 ASR이 필요하다. `--asr`은 `faster-whisper`가 설치된 경우에만 동작하며 이
  저장소는 설치하지 않는다.
- 검색 수율: 일반 키워드는 벤더 쇼츠·튜토리얼이 대부분이다. 산업어·실패어를 붙이거나 채널 목록을 쓰라.

## 예시

`examples/`에 실제 실행 결과 한 건(공개 영상)이 있다 — `flags.jsonl`이 무엇을 잡고 `corrections.jsonl`이 어떻게 생겼는지.
