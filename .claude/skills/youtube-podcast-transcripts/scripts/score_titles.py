# -*- coding: utf-8 -*-
"""candidates.jsonl → 제목 점수로 거른 판독 대상 + 분할 파일.

발견이 수천 건을 내면 전부 판독할 수 없다. 제목과 채널만 보고 기계로 점수를 매겨 상위만 남긴다.
**점수는 판정이 아니다.** 남은 것을 사람(또는 판독 작업)이 다시 읽어야 한다.

사용:
  python score_titles.py out/<slug>/candidates.jsonl --out out/<slug>/screen \
      [--min-score 4] [--top 660] [--groups 6] [--max-minutes 120] [--exclude ids.txt]

출력:
  <out>/scored.jsonl      점수와 사유가 붙은 전체 후보(채택·탈락 모두)
  <out>/titles_N.tsv      판독용 분할 파일 (id, channel, min, title, matched_query)
"""
import argparse, io, json, os, re, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 사례·임원·산업·에이전트 어휘. 한국어·일본어·스페인어도 같이 본다.
AGENT = re.compile(r"agentic|ai agent|agents?\b|copilot|genai|generative ai|에이전트|자동화|エージェント|agentes", re.I)
CASE = re.compile(r"case stud|customer stor|how (we|they)|inside|deploy|rollout|in production|at scale|lessons|journey|results|사례|도입|事例|caso", re.I)
EXEC = re.compile(r"\bC[EITDOFHM]O\b|chief|head of|\bEVP\b|\bSVP\b|president|managing director|vice president|\bVP\b|founder|임원|대표|사장", re.I)
ORG = re.compile(r"bank|insur|health|hospital|payer|retail|manufactur|telecom|logistics|airline|utility|government|pharma|energy|은행|보험|병원|제조|금융", re.I)
# 튜토리얼·강좌·수익 영상. 이 어휘가 있으면 사실상 탈락시킨다.
NEG = re.compile(r"tutorial|how to build|course|crash course|\bdemo\b|getting started|n8n|make\.com|langchain|langgraph|beginners|step by step|build (a|an|your)|template|prompt engineering|make money|earn \$", re.I)
SKIP_TITLE = re.compile(r"#shorts|\btrailer\b|\bteaser\b|\bpromo\b", re.I)


def score(r):
    """점수와 사유. NEG는 -5로 사실상 탈락."""
    t = ((r.get("title") or "") + " " + (r.get("channel") or ""))
    why = []
    if NEG.search(t):
        return -5, ["tutorial/강좌 어휘"]
    s = 0
    if AGENT.search(t): s += 2; why.append("agent")
    if CASE.search(t): s += 2; why.append("case")
    if EXEC.search(t): s += 2; why.append("exec")
    if ORG.search(t): s += 1; why.append("industry")
    d = r.get("duration_sec") or 0
    if 900 <= d <= 5400: s += 1; why.append("15~90분")
    if d > 7200: s -= 1; why.append("2시간 초과")
    if r.get("source_kind") == "channel": s += 1; why.append("채널 목록")
    return s, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-score", type=int, default=4)
    ap.add_argument("--top", type=int, default=660, help="점수 순 상위 N건만 판독에 넘긴다")
    ap.add_argument("--groups", type=int, default=6)
    ap.add_argument("--max-minutes", type=float, default=120, help="이보다 긴 종일 키노트는 뺀다")
    ap.add_argument("--exclude", default=None, help="이미 본 영상 id 파일")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rows = [json.loads(l) for l in open(a.candidates, encoding="utf-8")]
    excl = set()
    if a.exclude and os.path.isfile(a.exclude):
        excl = {l.strip() for l in open(a.exclude, encoding="utf-8") if l.strip()}

    kept = []
    for r in rows:
        s, why = score(r)
        r["score"], r["score_why"] = s, why
        r["screen_skip"] = ""
        vid = r.get("id") or ""
        # 팟캐스트 RSS의 오디오 전용 회차는 자막을 받을 수 없다
        if vid.startswith("rss_"):
            r["screen_skip"] = "오디오 전용(유튜브 링크 없음)"
        elif vid in excl:
            r["screen_skip"] = "이미 수집함"
        elif not r.get("selected", True):
            r["screen_skip"] = r.get("skip_reason") or "발견 단계에서 제외"
        elif SKIP_TITLE.search(r.get("title") or ""):
            r["screen_skip"] = "trailer/shorts"
        elif (r.get("duration_sec") or 0) > a.max_minutes * 60:
            r["screen_skip"] = "%.0f분 초과" % a.max_minutes
        elif s < a.min_score:
            r["screen_skip"] = "점수 %d < %d" % (s, a.min_score)
        else:
            kept.append(r)

    kept.sort(key=lambda r: (-r["score"], -(r.get("duration_sec") or 0)))
    over = kept[a.top:]
    for r in over:
        r["screen_skip"] = "상위 %d건 밖" % a.top
    kept = kept[: a.top]

    with open(os.path.join(a.out, "scored.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = a.groups
    per = (len(kept) + n - 1) // n if kept else 0
    for i in range(n):
        part = kept[i * per:(i + 1) * per] if per else []
        if not part:
            continue
        with open(os.path.join(a.out, "titles_%d.tsv" % (i + 1)), "w", encoding="utf-8") as f:
            f.write("id\tchannel\tmin\ttitle\tmatched_query\n")
            for r in part:
                f.write("%s\t%s\t%d\t%s\t%s\n" % (
                    r["id"], (r.get("channel") or "")[:30], (r.get("duration_sec") or 0) // 60,
                    (r.get("title") or "").replace("\t", " ")[:140],
                    ((r.get("matched_queries") or [""])[0])[:60]))
    dist = collections.Counter(r["score"] for r in rows)
    skips = collections.Counter(r["screen_skip"] for r in rows if r["screen_skip"])
    print("후보 %d → 판독 대상 %d (분할 %d개)" % (len(rows), len(kept), min(n, (len(kept) + per - 1) // per if per else 0)))
    print("점수 분포", dict(sorted(dist.items(), reverse=True)))
    print("제외 사유", dict(skips.most_common(8)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
