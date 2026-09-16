# 전사 교정의 암묵지 — 260편을 읽으며 생긴 규칙

영상 260편(컨퍼런스 세션·팟캐스트·기업 발표)을 읽으면서 마주친 오류와, 그때 정한 처리 규칙이다.
1차 99편에서 statement 255건을 뽑을 때 만든 규칙에, 2026-09 두 배치 161편을 판정하며 얻은 것을 더했다.
예시는 전부 실제 관찰이다. 규칙은 "이렇게 하면 맞다"가 아니라 **"이렇게 하면 틀린 것을
맞다고 쓰지 않는다"**를 목표로 한다.

## 0. 원칙 셋

| | |
|---|---|
| **원문 보존** | VTT는 append-only. 정리본·교정본은 별도 파일. 교정 자리는 표시해 되돌릴 수 있게 |
| **근거 없는 교정은 교정이 아니다** | 산술·같은 영상의 다른 발언·제목/설명·공개 정보 중 하나가 있어야 고친다. 없으면 `[sic]` |
| **없는 것은 없는 채로** | 끊긴 문장·사라진 수치·미상 화자를 복원하지 않는다. "그럴듯함"은 근거가 아니다 |
| **채워진 칸은 값이 아니다** | 결손은 `MISSING` 하나로만 적는다. `n/a`·`prior year`·`this is the baseline` 같은 산문을 칸에 넣으면 나중 집계가 그것을 값으로 센다. 실제로 그렇게 세어 "완전한 측정 21건"이 나왔고 규칙을 고치니 2건이었다 |

## 1. 수치 — 가장 위험하고, 가장 교정 가능한 곳

### 1-1. 절대값이 있으면 비율을 검산한다

> `src_v1_007` 18:46 — "In 2022, we had around 20,000 MIPS… In 2025, we had only 3,000 mips, which means is a
> reduction of consumption mips **over 9%**."

20,000→3,000은 **85%** 감소다. "90%"에서 0이 떨어진 전사 누락으로 추정. **절대값(20,000·3,000)을 근거로 채택하고
비율은 불채택.** 절대값과 연도가 함께 나왔기 때문에 교정 가능했다 — 비율만 있었다면 검증 불가였다.

같은 유형: "200건→300건 … increased over **53%** faster"(실제 50%) · "62분→29분 … **52.2%**"(실제 53.2%, 그리고
그 값이 문서의 '최대 감소율 52.2%'와 같아 어느 쪽이 전사 오류인지 판별 불가) · "60분→35분 … 41.8%"(실제 41.7%).

**규칙**: 절대값 쌍 + 비율이 함께 나오면 산술을 돌린다. 3%p 이상 어긋나면 `pct_mismatch`. 교정은 절대값 쪽으로.
비율 하나만 있으면 검산 불가 — 그대로 두고 `usable_as_evidence: low`.

### 1-2. 인접 발언에서 값이 다르면 둘 다 적고 어느 쪽도 고르지 않는다

> "**216** petabytes"(19:52) / "**206** petabytes"(20:24) · 제목 "450 million events" / 본문 "500 millions events"

**규칙**: `adjacent_conflict` — 양쪽 병기. 인용할 때 둘 다 쓴다.

### 1-3. 숫자와 단위가 깨진 것은 단위를 복원하지 않는다

> "100,000**memes**"(10만 뒤 단위 단어가 깨짐) · "4 millions **10**"(400만 텡게 — 통화 단위 tenge가 10으로) ·
> "90 95% accuracy"(90~95% 구간인지 두 값의 병렬인지 발화만으로 구분 불가) · "these models find **40 out of 15**"(분모<분자)

**규칙**: `number_unit_broken`. 발표자가 같은 영상에서 단위를 설명했으면 그것으로 교정(Bank CenterCredit는 "10 is
the local Kazak currency"라고 말해 역추적 가능했다 → basis=context). 아니면 분모·단위를 확정하지 않고 인용에서
그 수치를 뺀다.

### 1-4. 화면을 읽는 발언은 신뢰도가 낮다

> "it's uh how many 9% for Russian" — 발표자가 슬라이드를 보며 읽는 정황

**규칙**: 슬라이드 낭독으로 보이는 수치는 `confidence: low`. 슬라이드 자체를 확보하지 않는 한 인용하지 않는다.

### 1-5. 추정치가 실측으로 둔갑한다

> `src_v1_012` 36:00 — AWS 발표자 "based on the numbers that we've been seeing, they've been able to save 345 hours".
> 345시간은 병원 실측이 아니라 **벤더가 단가 가정으로 환산한 추정치**. 345h ÷ 2만 콜 ≈ 62초로 병원 측의 "통화당
> 1분 초과"와 정합 — **병원 실측은 건당 값이고 총량은 벤더 산출**이다.

**규칙**: 총량(시간·금액)이 나오면 누가 어떻게 계산했는지 발화에서 찾는다. 벤더·파트너가 말한 총량은 `estimate`로
표시하고, 도입 조직이 말한 건당 값과 분리한다.

### 1-6. 목표치를 기저선으로 오인하게 만드는 표현

> "우리는 60%를 목표로 시작했고…" 뒤에 "지금 60%" — 목표인지 실측인지 문맥으로만 구분된다.

**규칙**: 수치마다 `기저선 / 목표 / 실측 / 전망` 중 어느 것인지 적는다. 진행자가 재확인 질문을 했는데도 기간이
안 나오면(Citizens Bank 31:10) **없는 것**이다 — 채워 넣지 않는다.

## 2. 고유명사 — 가장 흔하고, 대부분 교정 불가

### 2-1. 같은 대상이 한 영상에서 여러 표기로 나온다

> 같은 인물 "Edison" / "Alison"(Alison Carneiro) · 같은 제품 "Sizzling" / "CIZZY" · 같은 인물 "Piyush Gupta" /
> "Bijou Das" / "Bidew"(DBS 혁신 총괄 Bidyut Dumra 추정 — 첫머리 내레이션은 CEO 이름으로 나오나 내용상 CEO가 아니다)

**규칙**: `spelling_cluster`로 묶는다. 제목·설명란·채널명·공개 정보로 **확인되면** 교정(basis=external). 확인 안 되면
표기 중 하나를 고르지 않고 `[sic: A/B]`로 병기.

### 2-2. 흔한 오전사 — 확인되면 교정, 아니면 두기

| 자막 | 실제(확인됨) | 근거 |
|---|---|---|
| Andre Carpathy / Andre Papancha | Andrej Karpathy / 미확인 | 전자는 공개 인물, 후자는 확인 불가 |
| Enthropic · chart GPT · GPD 4.1 · cloud senate 4.5 | Anthropic · ChatGPT · GPT-4.1 · Claude Sonnet 4.5 | 제품명 — external |
| Nurips · webcon · McKenzie · GitLar | NeurIPS · The Web Conference · McKinsey · GitClear | 학회·기관·출처명 — external |
| closure · rack · posgress · cobalt · perspectus | Clojure · RAG · Postgres · COBOL · prospectus | 문맥상 기술 용어 — context |
| enic world · AI genic · aenic · aents | agentic · agents | 이 주제에서 가장 흔한 오전사 |
| Bug Center credit · CVA · Tan Suan · Sam Alman | Bank CenterCredit · CBA · Tan Su Shan · Sam Altman | 제목·공개 정보 — external |
| Jackie Kinney · Ricky · Vinit | Jacqui Canney · Rik Coeckelbergs · Vineet | 본인 이름인데도 깨진다 |
| Sadiq Issu · Brian Felchuk · Salonus · U S AN | **미확인** | 자막에만 근거한 성명은 교정하지 않는다 |

**규칙**: 인명·기업명은 **자막 밖의 근거**가 있을 때만 고친다. 게스트 성명이 자막에만 나오면 `speaker: 미확인(자막 표기 "…")`.

### 2-3. 부정어·의미 반전 — 가장 조용한 오류

> "I don't trust **deterministic** software agents" — 문맥상 in-the-loop를 선호하는 이유이므로 **non-deterministic**이
> 맞다. 부정어 누락으로 의미가 뒤집힌다. · "human experience" ← Xpeers(Nubank 상담사 호칭) — 반대로 읽힐 수 있다.
> · "we realized too **bad**" ← too late

**규칙**: 앞뒤 발언과 논리가 어긋나면 `negation` 후보. 교정은 basis=context로 하되 `confidence: medium` 이하.
근거가 앞뒤 문맥뿐이면 원문을 남기고 `⟦…⟧` 안에 추정을 적는다.

## 3. 구조 — 자막의 모양이 만드는 오류

- **롤링 중복**: 각 cue가 직전 줄을 반복한다. 줄 단위 중복 제거 후에야 인용 가능. (스크립트가 한다)
- **문장이 중간에서 끊긴 채 다음 화면으로 넘어간다**(`src_v1_003` 24:50 등). 이어 붙이지 않는다. `truncated` 표시.
- **진행자의 맞장구가 문장 한가운데 들어간다**(`">> Yeah. >>"`). 원문 그대로 보존하고 `host_insert` 표시. 인용 시 `[…]`.
- **자막 중복과 연사의 실제 반복이 구별되지 않는다**("That's the best That's the best reasoning"). `intra_repeat`. 고치지 않는다.
- **줄이 한 줄씩 누락되고 본문이 2회 중복되는 손상**(AIPCon 8 계열 3편) — 성과 수치가 사라졌다. 복원 불가. 등급 유지,
  수치 미보고.
- **자막 붕괴**('팔란티어 국가', '공연배 FD' 등 문장 자체가 무너짐) — 기제 판별 불가로 **미정** 처리. 억지로 읽지 않는다.
- **`en-orig`와 `en`이 같은 자동 생성본**인 경우가 대부분이다. 수동 자막이 있는지는 트랙 목록으로 확인한다.
  최근 두 배치 161편에서는 수동 자막이 32편(20%)이었다. 드물지만 없지는 않다 — 먼저 확인하라.
- **번역 자막은 축어 인용이 불가능하다.** 독일어 행사의 영어 자막은 수동이지만 번역본이었다. 화자 레이블이 없고
  용어가 체계적으로 바뀐다(Lager → camp). 인용하려면 원어 자막이나 영상 자체가 필요하다.
- **타임스탬프가 통째로 무너지는 영상이 있다.** 정리본 전체가 `[00:00]` 한 문단이 되어 모든 인용이 같은 시각을
  가리킨다. 이때 `MM:SS`는 위치를 보장하지 못한다. 원문 VTT에서 직접 찾거나 "위치 미상"으로 적는다.
- **설명란·슬라이드에만 있는 수치는 자막에 없다.** 제목이 "247% ROI"라고 해도 발화에는 없을 수 있다.
  자막에 없으면 그 수치의 출처는 자막이 아니다. 확인 경로를 따로 적는다.
- **cp949 콘솔에서 VTT 출력 시 인코딩 오류.** UTF-8 강제.

## 4. 화자 — 자막은 누가 말했는지 모른다

- 자동 자막은 **화자 분리를 하지 않는다.** 누가 말했는지는 문맥으로만 추정된다 → `speaker` 값은 `추정` 또는 `미확인`.
  12명이 이어 말하는 몽타주에서는 귀속이 가장 약하다.
- **발행자 전사본에는 화자 이름이 있다.** 팟캐스트 RSS의 `podcast:transcript`로 받은 것은 "Chris Benson: 00:01" 형태로
  화자와 시각이 붙어 있어 이 약점이 사라진다. 다만 그 전사본도 ASR로 만들었을 수 있다 — 화자 표기는 발행자가 붙인 것이고,
  숫자·고유명사 오류는 자동 자막과 같은 규칙으로 다룬다. 발행자가 화자를 잘못 붙였을 가능성도 남는다.
- **진행자의 요약을 게스트 발언으로 옮기지 않는다.** "You had to downsize dramatically. It didn't work for a year."는
  진행자 요약이고 게스트는 "Right."로 동의했을 뿐이다(04:36).
- **벤더가 고객 대신 말한다.** AWS 발표자가 은행 사례 수치를 전부 읽은 세션, NVIDIA 단일 발표자가 여섯 기업 사례를
  말한 세션 — 도입 조직의 발언이 아니다. `speaker_role: vendor_for_customer`. 세션 앞부분은 은행 임원, 뒷부분은
  파트너인 경우도 있다 — 구간마다 적는다.
- **벤치마크·조사 기업이 진행하는 원탁**의 데이터는 그 기업의 집계다("our use case tracker data is based on publicly
  disclosed use cases, it tends to lag"). 기업 발언만 사례로 취급.

## 5. 재인용 — 강연은 남의 숫자를 자기 것처럼 말한다

> "MIT 보고서의 AI 파일럿 95% 실패" · "McKinsey 조사 15%/70%/71%" · "조직의 16%만 AI 투자에서 양의 수익" —
> 출처를 자막에서 확인할 수 없는 재인용.

**규칙**: 외부 조사·타사 사례를 인용한 발언은 `reciting`에 적고 **독립 근거로 세지 않는다.** 같은 사례가
보도자료·블로그·강연에 반복되면 origin 하나다.

## 6. 발견 — 무엇이 실제로 나왔나

- **일반 키워드 검색은 수율이 낮다.** "AI agents in production podcast lessons mistakes" 5회 → 벤더 쇼츠·튜토리얼.
  유효했던 것은 **산업 한정 + 실패어**: `bank AI agents deployment interview CTO lessons learned`,
  `insurance AI agents podcast what did not work` → 여기서만 실제 사례 4편.
- **채널 목록이 키워드보다 낫다.** AWS Events·MIT SMR·Latent Space·a16z·Sequoia·11:FS 같은 채널을 `--flat-playlist`로
  훑는 쪽이 세션·인터뷰를 낸다.
- **실패 서술은 Q&A·즉흥 발언에서 나온다.** 준비된 발표부에는 없다. 자막의 뒷부분을 버리지 않는다.
- **형식이 축 정의와 어긋날 수 있다** — 컨퍼런스 발표가 "팟캐스트" 검색에 잡힌다. `format` 필드를 따로 둔다.
- **채널이 없을 수 있다** — "This channel does not have a videos tab". 팟캐스트가 유튜브에 없으면 RSS로.
- **국내 금융사 자체 발표 영상은 0건이었다.** 한국어 검색은 영어 영상의 자동번역 제목이거나 벤더 제품 영상이었다.

## 7. 도구 — 막혔던 이유

- 배치 1·2가 "YouTube는 안 된다"고 DEAD END로 적었다. 원인은 **yt-dlp 미설치**였다. 실패는 원인까지 적는다.
- yt-dlp가 매 호출 `No supported JavaScript runtime could be found` 경고를 낸다 — 자막 추출에는 영향 없음.
- **영상 id는 `-`나 `_`로 시작할 수 있다.** 두 번 데인 자리다.
  `-B__O2eqRYc`를 그대로 인자로 넘기면 명령행이 옵션으로 읽어 스크립트가 죽는다. URL을 넘기거나 `--id=값` 형태를 쓴다.
  폴더명도 같다 — `--out=-B__O2eqRYc`처럼 `=`로 붙인다.
  더 위험한 쪽은 **이름 접두사로 자료를 거르는 코드**다. 보조 폴더(`_work`, `_search`)를 거르려고 `_`로 시작하는
  이름을 건너뛰면 `_IZR66PaJbM` 같은 실제 영상이 조용히 사라진다. 실제로 한 배치에서 3편이 판독조차 받지 못했다.
  **건너뛸 폴더는 이름을 명시적으로 나열한다.**
- **실패가 조용히 전파되는 구조를 피한다.** 위 사고에서 수집 루프는 한 편에서 죽었고, 그 뒤 5편은 시도조차 되지
  않았는데 로그에는 아무 표시가 없었다. 처리 건수를 선별 건수와 대조하면 드러난다.
- VTT 타임스탬프는 정확하다. **시간 위치가 자막에서 유일하게 믿을 수 있는 것**이다. 항상 `MM:SS`를 남긴다.
