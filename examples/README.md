# 예시 — 공개 영상 2편의 실제 실행 결과

원문 VTT와 전체 정리본은 싣지 않는다(재생성 가능). 여기 있는 것은 **기계가 무엇을 표시하고, 교정 파일이 어떻게 생겼는지**다.

## `0wYScALIxI4/` — 팟캐스트 인터뷰 (CAIO AI Leadership Podcast, Truist 최고개인정보책임자, 29:51)

- `meta.json` — 수동 자막 0, 자동 자막만. 화자는 `미확인`으로 남아 있다(판독 전).
- `flags.jsonl` — 의심 42건. 거의 전부 `host_insert`: 진행자와 게스트가 서로 말을 끊는 구간이 많고, 자막 중반부는 구두점이
  없어 `>>`가 문장 중간에 놓인 것으로 보인다. 표시만 하고 고치지 않는다.
- `corrections.jsonl` — 교정 예 3건: 외부 근거(제목의 Truist ← 자막 "tourists"), 근거 없음(`[sic]`), 문맥 근거(medium).
- `corrected.excerpt.md` — 교정 적용본 앞 4문단. `⟦원문 → 교정 (근거)⟧` 표기.

## `ZxE9nh0wkGI/` — 컨퍼런스 세션 (AWS FSI NYC 2026, Itaú 메인프레임 현대화)

- `flags.jsonl` — `pct_mismatch` 2건 중 하나가 이 스킬이 생긴 이유다:

  > "In 2022, we had around 20,000 MIPS … In 2025, we had only 3,000 mips, which means is a reduction … **over 9%**"

  20,000→3,000은 85% 감소. 자막의 "9%"는 "90%"에서 0이 떨어진 것으로 추정된다. 절대값을 채택하고 비율은 불채택.
  같은 문단에 `adjacent_conflict`("216 petabytes" / "206 petabytes")도 있다 — 둘 다 적고 고르지 않는다.
- 나머지: `gap`·`truncated` — 문장이 끝나기 전 4초 이상 공백. 이어 붙이지 않는다.
