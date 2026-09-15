# -*- coding: utf-8 -*-
"""주제 → 발견 → 수집 → 정리. 교정(판단)은 Claude가 한다.

사용: python run.py "<주제>" --out out/<slug> [--industry 은행 보험] [--channels channels.txt] [--rss feeds.txt]
                   [--per-query 15] [--max-queries 12] [--max-videos 20] [--min-minutes 8] [--since YYYY-MM-DD] [--langs en ko]
"""
import argparse, io, json, os, subprocess, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SK = os.path.join(HERE, ".claude", "skills", "youtube-podcast-transcripts", "scripts")


def sh(args, timeout=600):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic"); ap.add_argument("--out", required=True)
    ap.add_argument("--industry", nargs="*", default=[]); ap.add_argument("--channels"); ap.add_argument("--rss")
    ap.add_argument("--per-query", type=int, default=15); ap.add_argument("--max-videos", type=int, default=20)
    ap.add_argument("--min-minutes", type=float, default=8); ap.add_argument("--since"); ap.add_argument("--max-queries", type=int, default=12); ap.add_argument("--langs", nargs="+", default=["en", "ko"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    args = [os.path.join(SK, "discover.py"), a.topic, "--out", a.out, "--per-query", str(a.per_query), "--min-minutes", str(a.min_minutes), "--max-queries", str(a.max_queries)]
    if a.industry: args += ["--industry"] + a.industry
    if a.channels: args += ["--channels", a.channels]
    if a.rss: args += ["--rss", a.rss]
    if a.since: args += ["--since", a.since]
    rc, out = sh(args); print(out)

    cands = [json.loads(l) for l in open(os.path.join(a.out, "candidates.jsonl"), encoding="utf-8")]
    todo = [c for c in cands if c["selected"]][: a.max_videos]
    rows, fails = [], []
    for c in todo:
        d = os.path.join(a.out, c["id"])
        rc, out = sh([os.path.join(SK, "fetch_transcript.py"), c["url"], "--out", d, "--langs"] + a.langs, timeout=400)
        print(out.splitlines()[-1] if out else "")
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8")) if os.path.isfile(os.path.join(d, "meta.json")) else {}
        if meta.get("transcript_status") not in ("ok", "asr"):
            fails.append({"id": c["id"], "url": c["url"], "stage": "fetch", "reason": meta.get("transcript_status") or "unknown",
                          "detail": (meta.get("error") or "")[:200]})
            continue
        rc, out = sh([os.path.join(SK, "correct_transcript.py"), os.path.join(d, "raw.vtt"), "--out", d,
                      "--title", meta.get("title") or "", "--channel", meta.get("channel") or ""])
        nflag = sum(1 for _ in open(os.path.join(d, "flags.jsonl"), encoding="utf-8")) if os.path.isfile(os.path.join(d, "flags.jsonl")) else 0
        rows.append((c["id"], meta.get("title") or "", meta.get("channel") or "", meta.get("duration_sec") or 0,
                     "자동" if meta.get("transcript_auto") else "수동", nflag, c.get("format_guess", "")))

    L = ["# " + a.topic, "", "발견 %d · 채택 %d · 수집 대상 %d · 수집 성공 %d · 실패 %d" % (len(cands), sum(1 for c in cands if c["selected"]), len(todo), len(rows), len(fails)), "",
         "| id | 제목 | 채널 | 길이 | 자막 | 의심 | 교정 | 화자 | 형식(추정) |", "|---|---|---|---:|---|---:|---:|---|---|"]
    for vid, t, ch, dur, sub, nf, fmt_ in sorted(rows, key=lambda r: -r[5]):
        L.append("| `%s` | %s | %s | %d:%02d | %s | %d | — | 미확인 | %s |" % (vid, t[:60].replace("|", "/"), (ch or "")[:24], dur // 60, dur % 60, sub, nf, fmt_))
    L += ["", "교정 열은 Claude가 `corrections.jsonl`을 쓴 뒤 `apply_corrections.py`로 채운다.", "", "## 접근 실패", ""]
    df = os.path.join(a.out, "discover_failures.jsonl")
    n0 = len(L)
    if os.path.isfile(df):
        for l in open(df, encoding="utf-8"):
            r = json.loads(l); L.append("- discover · `%s` — %s" % (r["target"], r["reason"]))
    for r in fails:
        L.append("- fetch · `%s` — %s %s" % (r["url"], r["reason"], r["detail"]))
    if len(L) == n0:
        L.append("- 없음")
    open(os.path.join(a.out, "INDEX.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("→", os.path.join(a.out, "INDEX.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
