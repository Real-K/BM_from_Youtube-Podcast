# 출력 스키마

## `candidates.jsonl` (발견)

```json
{"id": "1GnbsGhRC4o", "url": "https://www.youtube.com/watch?v=1GnbsGhRC4o", "title": "...", "channel": "...",
 "duration_sec": 3019, "upload_date": "20260212", "matched_queries": ["..."], "source_kind": "ytsearch|channel|rss",
 "format_guess": "session", "selected": true, "skip_reason": ""}
```

## `<id>/meta.json` (수집)

```json
{"id": "...", "url": "...", "title": "...", "channel": "...", "uploader": "...", "duration_sec": 3019,
 "upload_date": "20260212", "description_head": "...(앞 500자)",
 "transcript_auto": true, "transcript_lang": "en", "transcript_track": "en (auto)", "manual_tracks": [], "auto_tracks": ["en", "ko"],
 "transcript_status": "ok|no_captions|audio_only|blocked",
 "fetched_at": "2026-09-15", "tool": "yt-dlp 2026.08.19",
 "speaker": {"host": "", "guests": [], "attribution": "미확인|추정|확인", "note": ""},
 "speaker_role": "adopter|vendor|vendor_for_customer|analyst|mixed|unknown",
 "format": "session|keynote|podcast|interview|panel|webinar|demo|other",
 "reciting": [], "notes": ""}
```

`speaker`·`speaker_role`·`format`·`reciting`은 수집 시 비어 있고 **판독(Claude)이 채운다.**

## `<id>/clean.md` (정리)

```
# <title>
<channel> · <duration> · 자막: 자동(en) · 원문 raw.vtt

**[00:12]** you think about the speed to which a gap can lead to a very significant problem…
**[00:41]** …
```

문단 시작 시각만 남긴다. 문장 중간 시각이 필요하면 `raw.vtt`.

## `<id>/flags.jsonl` (의심 지점, 기계)

```json
{"ts": "18:46", "kind": "pct_mismatch", "text": "…20,000 … 3,000 … over 9%", "detail": {"a": 20000, "b": 3000, "stated_pct": 9, "computed_pct": 85.0}}
{"ts": "19:52", "kind": "adjacent_conflict", "text": "216 petabytes", "detail": {"other_ts": "20:24", "other": "206 petabytes"}}
{"ts": "03:12", "kind": "spelling_cluster", "text": "", "detail": {"variants": {"Edison": 2, "Alison": 3}}}
{"ts": "09:37", "kind": "intra_repeat", "text": "That's the best That's the best reasoning", "detail": {"phrase": "That's the best"}}
{"ts": "31:52", "kind": "host_insert", "text": "… >> Yeah. >> …", "detail": {}}
{"ts": "24:50", "kind": "truncated", "text": "…and then we", "detail": {"gap_sec": 6.2}}
```

`kind`: pct_mismatch · adjacent_conflict · number_unit_broken · spelling_cluster · intra_repeat · host_insert · gap · truncated

## `<id>/corrections.jsonl` (교정, Claude)

```json
{"ts": "18:46", "kind": "number", "original": "over 9%", "corrected": "over 90%", "basis": "arithmetic", "confidence": "high",
 "note": "20,000→3,000 = 85% 감소. 절대값 채택, 비율 불채택", "flag_ref": "pct_mismatch@18:46"}
{"ts": "05:10", "kind": "proper_noun", "original": "Enthropic", "corrected": "Anthropic", "basis": "external", "confidence": "high", "note": "제품·기업명"}
{"ts": "22:03", "kind": "negation", "original": "I don't trust deterministic software agents", "corrected": "I don't trust non-deterministic software agents",
 "basis": "context", "confidence": "medium", "note": "앞뒤 발언이 in-the-loop 선호 이유를 말함"}
{"ts": "14:20", "kind": "proper_noun", "original": "Sadiq Issu", "corrected": "", "basis": "none", "confidence": "none", "note": "자막에만 근거. [sic]"}
```

`kind`: proper_noun · number · unit · negation · term · speaker · repeat · host_insert · reciting · other
`basis`: arithmetic · external · context · none  ·  `confidence`: high · medium · low · none

**`basis: none`이면 `corrected`는 비어 있어야 한다.** `apply_corrections.py`가 검사한다.

## `<id>/corrected.md`

`clean.md`에 교정을 적용한 것. 교정 자리는 `⟦원문 → 교정 (basis)⟧`, `[sic]`은 `⟦원문 [sic]⟧`.

## `INDEX.md`

| id | 제목 | 채널 | 길이 | 자막 | 의심 | 교정 | 화자 | 형식 | 비고 |
|---|---|---|---|---|---|---|---|---|---|

그리고 `## 접근 실패` — url · 단계(discover/fetch) · 이유 · 시도한 것.
