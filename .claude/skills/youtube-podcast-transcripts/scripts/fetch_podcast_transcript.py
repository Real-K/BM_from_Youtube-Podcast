# -*- coding: utf-8 -*-
"""팟캐스트 RSS의 `podcast:transcript`(Podcasting 2.0) → 발행자 전사본 수집. 유튜브가 없어도 된다.

자동 자막과 다른 점: **발행자가 만든 전사본은 화자 이름이 붙어 있다.** 유튜브 자동 자막은 화자를 구분하지 않으므로
귀속이 늘 추정이었다(references/tacit-knowledge.md §4). 대신 발행자 전사본도 ASR 기반일 수 있으니 오류가 없다는 뜻은 아니다.

사용:
  python fetch_podcast_transcript.py --feed <RSS URL> --out out/<slug> [--limit 20] [--match 키워드 ...]
  python fetch_podcast_transcript.py --feed-file feeds.txt --out out/<slug> [--limit 10]

출력(회차마다 한 폴더):
  meta.json   서지 · 전사 출처 · 오디오 URL(있으면)
  raw.<ext>   발행자 전사본 원문 — 불변
  clean.md    화자·시각을 살린 문단
전사 태그가 없으면 폴더를 만들지 않고 `no_transcript.jsonl`에 사유와 함께 남긴다. 그 회차는 ASR이 필요하다.
"""
import argparse, datetime, html, io, json, os, re, sys, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (transcript-collector)"}
TS = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")
# "Chris Benson: 00:01 ..." 형태. 발행자 전사본에서 가장 흔하다.
SPEAKER_TS = re.compile(r"(?m)([A-Z][\w .'’-]{1,40}?):\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*")
EXT = {"text/vtt": "vtt", "application/x-subrip": "srt", "text/srt": "srt",
       "application/json": "json", "text/html": "html", "text/plain": "txt"}


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def strip_html(raw):
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", raw)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"[ \t]+", " ", txt)


def to_clean(text, kind, title, show):
    """발행자 전사본 → 문단. 화자와 시각을 그대로 남긴다."""
    head = ["# " + (title or "episode"), " · ".join(x for x in [show, "발행자 전사본(%s)" % kind, "원문 raw 파일 보존"] if x), ""]
    if kind == "json":                                   # Podcasting 2.0 JSON
        try:
            segs = json.loads(text).get("segments") or []
        except Exception:
            segs = []
        if segs:
            out, cur, spk, start = [], [], None, None
            for s in segs:
                sp, body = s.get("speaker"), (s.get("body") or "").strip()
                st = s.get("startTime")
                if spk is None or sp != spk:
                    if cur:
                        out.append((spk, start, " ".join(cur)))
                    cur, spk, start = [], sp, st
                cur.append(body)
            if cur:
                out.append((spk, start, " ".join(cur)))
            body = []
            for sp, st, tx in out:
                m = "**%s**" % sp if sp else ""
                t = " **[%02d:%02d]**" % (int(st) // 60, int(st) % 60) if isinstance(st, (int, float)) else ""
                body.append(("%s%s %s" % (m, t, tx)).strip())
            return head + body
    if kind in ("vtt", "srt"):
        lines = [l.strip() for l in text.splitlines()]
        keep, ts = [], ""
        for l in lines:
            if "-->" in l:
                ts = (TS.search(l).group(1) if TS.search(l) else "")
                continue
            if not l or l.isdigit() or l.startswith("WEBVTT") or l.startswith("Kind:") or l.startswith("Language:"):
                continue
            keep.append(("**[%s]** " % ts if ts else "") + l)
            ts = ""
        return head + keep
    # html / txt
    txt = strip_html(text) if kind == "html" else text
    txt = re.sub(r"\n{2,}", "\n", txt)
    parts = SPEAKER_TS.split(txt)
    body = []
    if len(parts) > 3:                                   # [앞부분, 화자, 시각, 본문, 화자, 시각, 본문, ...]
        for i in range(1, len(parts) - 2, 3):
            spk, ts, seg = parts[i].strip(), parts[i + 1], " ".join(parts[i + 2].split())
            if seg:
                body.append("**%s** **[%s]** %s" % (spk, ts, seg))
    else:
        body = [" ".join(p.split()) for p in txt.split("\n") if p.strip()]
    return head + body


def pick(entry):
    """feedparser 항목에서 transcript 태그를 고른다. vtt·json을 html보다 먼저."""
    cands = []
    t = entry.get("podcast_transcript")
    if isinstance(t, dict):
        cands.append(t)
    for k in ("podcast_transcripts", "transcripts"):
        v = entry.get(k)
        if isinstance(v, list):
            cands += [x for x in v if isinstance(x, dict)]
    order = {"text/vtt": 0, "application/json": 1, "application/x-subrip": 2, "text/plain": 3, "text/html": 4}
    cands = [c for c in cands if c.get("url")]
    cands.sort(key=lambda c: order.get((c.get("type") or "").lower(), 9))
    return cands[0] if cands else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feed"); ap.add_argument("--feed-file"); ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=20, help="피드당 최신 N회차")
    ap.add_argument("--match", nargs="*", default=None, help="제목·요약에 이 단어가 있는 회차만")
    a = ap.parse_args()
    try:
        import feedparser
    except ImportError:
        print("feedparser가 필요하다: pip install feedparser"); return 2
    feeds = [a.feed] if a.feed else []
    if a.feed_file:
        feeds += [l.strip() for l in open(a.feed_file, encoding="utf-8") if l.strip() and not l.startswith("#")]
    if not feeds:
        ap.error("--feed 또는 --feed-file이 필요하다")
    os.makedirs(a.out, exist_ok=True)
    miss, got = [], 0

    for feed in feeds:
        fp = feedparser.parse(feed)
        show = (fp.feed.get("title") or "")[:80]
        entries = fp.entries[: a.limit]
        print("%-46s 항목 %d (최신 %d건 확인)" % (show[:46] or feed[:46], len(fp.entries), len(entries)))
        for e in entries:
            title = e.get("title") or ""
            blob = (title + " " + (e.get("summary") or "")).lower()
            if a.match and not any(w.lower() in blob for w in a.match):
                continue
            eid = re.sub(r"\W+", "", (e.get("id") or e.get("link") or title))[-24:] or ("ep%d" % got)
            tr = pick(e)
            audio = next((l.get("href") for l in e.get("links", []) if l.get("rel") == "enclosure"), None)
            if not tr:
                miss.append({"show": show, "title": title, "link": e.get("link"), "audio_url": audio,
                             "reason": "podcast:transcript 없음 — ASR 필요"})
                continue
            d = os.path.join(a.out, eid)
            os.makedirs(d, exist_ok=True)
            kind = EXT.get((tr.get("type") or "").lower(), "txt")
            try:
                raw = get(tr["url"]).decode("utf-8", "replace")
            except Exception as ex:
                miss.append({"show": show, "title": title, "link": e.get("link"), "audio_url": audio,
                             "reason": "전사본 접근 실패: %s" % str(ex)[:120]})
                continue
            open(os.path.join(d, "raw." + kind), "w", encoding="utf-8").write(raw)
            open(os.path.join(d, "clean.md"), "w", encoding="utf-8").write("\n".join(to_clean(raw, kind, title, show)) + "\n")
            json.dump({"id": eid, "show": show, "title": title, "url": e.get("link"), "feed": feed,
                       "published": e.get("published"), "audio_url": audio,
                       "transcript_source": "publisher (podcast:transcript)", "transcript_url": tr["url"],
                       "transcript_type": tr.get("type"), "transcript_auto": None,
                       "note": "발행자 전사본. ASR 기반일 수 있어 오류가 없다는 뜻은 아니다. 화자 표기는 발행자가 붙인 것이다.",
                       "fetched_at": datetime.date.today().isoformat()},
                      open(os.path.join(d, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            got += 1
            print("   확보 %-22s %s" % (eid, title[:60]))
    with open(os.path.join(a.out, "no_transcript.jsonl"), "w", encoding="utf-8") as f:
        for m in miss:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print("전사본 확보 %d · 전사 없음 %d (no_transcript.jsonl — ASR 필요)" % (got, len(miss)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
