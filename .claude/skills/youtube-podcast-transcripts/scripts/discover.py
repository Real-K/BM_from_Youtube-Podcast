# -*- coding: utf-8 -*-
"""주제 → candidates.jsonl. ytsearch 격자 + 채널 목록 + 팟캐스트 RSS.

사용: python discover.py "<주제>" --out <dir> [--industry 은행 보험] [--channels channels.txt] [--rss feeds.txt]
                          [--per-query 15] [--min-minutes 8] [--since YYYY-MM-DD] [--no-grid]
"""
import argparse, datetime, io, json, os, re, subprocess, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings"]
FORMAT_WORDS = ["podcast", "interview", "keynote", "fireside chat", "panel", "lessons learned"]
FAIL_WORDS = ["what did not work", "postmortem", "went wrong", "we stopped", "hidden cost"]
SKIP_TITLE = re.compile(r"#shorts|\btrailer\b|\bteaser\b|\bpromo\b", re.I)


def ytdlp_json(target, n=None, timeout=120):
    args = ["--flat-playlist", "--dump-single-json", target]
    if n:
        args = ["--playlist-end", str(n)] + args
    p = subprocess.run(YTDLP + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode != 0 or not p.stdout.strip():
        return None, p.stderr.strip()[-300:]
    try:
        return json.loads(p.stdout), ""
    except json.JSONDecodeError:
        return None, "json parse error"


def guess_format(title, channel):
    t = (title or "").lower() + " " + (channel or "").lower()
    for k, v in (("podcast", "podcast"), ("fireside", "podcast"), ("interview", "interview"), ("keynote", "keynote"),
                 ("panel", "panel"), ("roundtable", "panel"), ("webinar", "webinar"), ("demo", "demo"), ("session", "session"),
                 ("summit", "session"), ("conference", "session"), ("talk", "session")):
        if k in t:
            return v
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--out", required=True)
    ap.add_argument("--industry", nargs="*", default=[])
    ap.add_argument("--channels", default=None)
    ap.add_argument("--rss", default=None)
    ap.add_argument("--per-query", type=int, default=15)
    ap.add_argument("--min-minutes", type=float, default=8)
    ap.add_argument("--since", default=None)
    ap.add_argument("--no-grid", action="store_true", help="주제 그대로만 검색")
    ap.add_argument("--max-queries", type=int, default=12)
    ap.add_argument("--queries", default=None, help="질의 파일(한 줄에 하나). 격자에 추가된다")
    ap.add_argument("--exclude", default=None, help="이미 수집한 영상 id 파일(한 줄에 하나) → 채택 제외")
    ap.add_argument("--channel-kw", nargs="*", default=None, help="채널 목록에서 제목에 이 단어가 있는 것만 (기본: 주제의 4자 이상 단어)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    queries = [a.topic]
    if not a.no_grid:
        inds = a.industry or [""]
        for ind in inds:
            for fw in FORMAT_WORDS[:3]:
                queries.append(" ".join(x for x in [a.topic, ind, fw] if x))
            for fl in FAIL_WORDS[:2]:
                queries.append(" ".join(x for x in [a.topic, ind, fl] if x))
    if a.queries and os.path.isfile(a.queries):
        queries += [l.strip() for l in open(a.queries, encoding="utf-8") if l.strip() and not l.startswith("#")]
    queries = list(dict.fromkeys(queries))[: a.max_queries]
    exclude = set()
    if a.exclude and os.path.isfile(a.exclude):
        exclude = {l.strip() for l in open(a.exclude, encoding="utf-8") if l.strip()}

    cands, failures = {}, []
    since = a.since.replace("-", "") if a.since else None

    def add(e, q, kind):
        vid = e.get("id")
        if not vid:
            return
        title = e.get("title") or ""
        dur = e.get("duration") or 0
        url = e.get("url") or e.get("webpage_url") or ("https://www.youtube.com/watch?v=" + vid)
        if "youtube.com" not in url and "youtu.be" not in url and kind != "rss":
            url = "https://www.youtube.com/watch?v=" + vid
        rec = cands.setdefault(vid, {"id": vid, "url": url, "title": title, "channel": e.get("channel") or e.get("uploader"),
                                     "duration_sec": dur, "upload_date": e.get("upload_date"), "matched_queries": [],
                                     "source_kind": kind, "format_guess": guess_format(title, e.get("channel") or e.get("uploader")),
                                     "selected": True, "skip_reason": ""})
        if q not in rec["matched_queries"]:
            rec["matched_queries"].append(q)

    for q in queries:
        d, err = ytdlp_json("ytsearch%d:%s" % (a.per_query, q))
        if d is None:
            failures.append({"stage": "discover", "target": "ytsearch:" + q, "reason": err})
            continue
        for e in d.get("entries") or []:
            add(e, q, "ytsearch")
        print("검색 %-70s %d건" % (q[:70], len(d.get("entries") or [])))

    if a.channels and os.path.isfile(a.channels):
        for line in open(a.channels, encoding="utf-8"):
            ch = line.strip()
            if not ch or ch.startswith("#"):
                continue
            d, err = ytdlp_json(ch, n=200, timeout=240)
            if d is None:
                failures.append({"stage": "discover", "target": ch, "reason": err})
                continue
            kw = [w.lower() for w in (a.channel_kw or re.findall(r"\w{4,}", a.topic))]
            n = 0
            for e in d.get("entries") or []:
                t = (e.get("title") or "").lower()
                if any(w in t for w in kw):
                    add(e, "channel:" + ch, "channel"); n += 1
            print("채널 %-60s 목록 %d · 주제어 일치 %d" % (ch[:60], len(d.get("entries") or []), n))

    if a.rss and os.path.isfile(a.rss):
        try:
            import feedparser
        except ImportError:
            failures.append({"stage": "discover", "target": "rss", "reason": "feedparser 미설치 (pip install feedparser)"})
            feedparser = None
        if feedparser:
            for line in open(a.rss, encoding="utf-8"):
                feed = line.strip()
                if not feed or feed.startswith("#"):
                    continue
                fp = feedparser.parse(feed)
                if fp.bozo and not fp.entries:
                    failures.append({"stage": "discover", "target": feed, "reason": str(fp.bozo_exception)[:200]})
                    continue
                for e in fp.entries:
                    blob = " ".join([e.get("title", ""), e.get("summary", "")] + [l.get("href", "") for l in e.get("links", [])])
                    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})", blob)
                    if m:
                        add({"id": m.group(1), "title": e.get("title"), "channel": fp.feed.get("title"), "duration": 0}, "rss:" + feed, "rss")
                    else:
                        enc = next((l.get("href") for l in e.get("links", []) if l.get("rel") == "enclosure"), None)
                        tr = e.get("podcast_transcript")
                        tr = tr if isinstance(tr, dict) and tr.get("url") else None
                        rid = "rss_" + re.sub(r"\W+", "", (e.get("id") or e.get("link") or e.get("title") or ""))[:24]
                        cands.setdefault(rid, {"id": rid, "url": e.get("link") or enc, "title": e.get("title"), "channel": fp.feed.get("title"),
                                               "duration_sec": 0, "upload_date": None, "matched_queries": ["rss:" + feed], "source_kind": "rss",
                                               "format_guess": "podcast", "selected": True,
                                               "skip_reason": "", "audio_url": enc,
                                               "transcript_url": (tr or {}).get("url"), "transcript_type": (tr or {}).get("type"),
                                               "note": ("발행자 전사본 있음 — fetch_podcast_transcript.py로 받는다"
                                                        if tr else "유튜브 링크·발행자 전사본 없음 — 오디오뿐이라 ASR 필요")})
                print("RSS %-60s 항목 %d" % (feed[:60], len(fp.entries)))

    for r in cands.values():
        if r["id"] in exclude:
            r["selected"], r["skip_reason"] = False, "already collected"
        elif SKIP_TITLE.search(r["title"] or ""):
            r["selected"], r["skip_reason"] = False, "trailer/shorts"
        elif r["source_kind"] != "rss" and r["duration_sec"] and r["duration_sec"] < a.min_minutes * 60:
            r["selected"], r["skip_reason"] = False, "short (<%.0f min)" % a.min_minutes
        elif since and r.get("upload_date") and r["upload_date"] < since:
            r["selected"], r["skip_reason"] = False, "before " + a.since
    rows = sorted(cands.values(), key=lambda r: (-int(r["selected"]), -len(r["matched_queries"]), -(r["duration_sec"] or 0)))
    with open(os.path.join(a.out, "candidates.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(a.out, "discover_failures.jsonl"), "w", encoding="utf-8") as f:
        for r in failures:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("후보 %d · 채택 %d · 실패 %d → %s" % (len(rows), sum(1 for r in rows if r["selected"]), len(failures), os.path.join(a.out, "candidates.jsonl")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
