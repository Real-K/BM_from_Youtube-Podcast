# -*- coding: utf-8 -*-
"""팟캐스트 찾기 — Apple Podcasts 디렉터리(키 불필요) → RSS 피드 → 전사 경로 판정.

팟캐스트에는 유튜브 같은 단일 플랫폼이 없다. **배포는 RSS이고 Apple·Spotify·Overcast는 그 위의 디렉터리·앱이다.**
그래서 프로그램을 찾는 일과 전사본을 얻는 일이 나뉜다. 이 스크립트는 앞쪽만 한다.

  python find_podcasts.py --shows shows.txt --out out/pods          # 이름으로 저명 프로그램 조회
  python find_podcasts.py --search "agentic AI" "AI CIO" --out out/pods   # 주제어로 발굴
  python find_podcasts.py --shows shows.txt --out out/pods --probe 20     # 피드마다 최신 20회차 경로 판정

출력:
  feeds.jsonl   프로그램명·피드 URL·회차 수·장르·조회한 질의
  routes.md     피드별 전사 경로(전사 태그 / 유튜브 링크 / 오디오뿐) 요약

Apple 검색 API는 키가 없어도 되지만 **적중률이 낮다.** 이름을 정확히 아는 프로그램은 `--shows`로 조회하는 편이 낫다.
Spotify는 공개 피드를 주지 않는다. Podcast Index는 API 키가 필요하다.
"""
import argparse, io, json, os, re, sys, time, urllib.parse, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (podcast-finder)"}
API = "https://itunes.apple.com/search?"


def search(term, limit=5, country="US"):
    u = API + urllib.parse.urlencode({"media": "podcast", "term": term, "limit": limit, "country": country})
    raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=45).read()
    return json.loads(raw.decode("utf-8", "replace")).get("results", [])


def probe(feed, n):
    """최신 n회차에서 전사 경로를 센다. (총회차, 전사태그, 유튜브, 오디오, 오류)"""
    try:
        import feedparser
    except ImportError:
        return None, 0, 0, 0, "feedparser 미설치"
    try:
        fp = feedparser.parse(feed)
    except Exception as e:
        return None, 0, 0, 0, str(e)[:80]
    es = fp.entries[:n]
    if not es:
        return len(fp.entries), 0, 0, 0, "항목 0"
    tr = sum(1 for e in es if isinstance(e.get("podcast_transcript"), dict) and e["podcast_transcript"].get("url"))
    yt = sum(1 for e in es if re.search(r"youtu\.?be", " ".join([e.get("summary", "")] + [l.get("href", "") for l in e.get("links", [])])))
    au = sum(1 for e in es if any(l.get("rel") == "enclosure" for l in e.get("links", [])))
    return len(fp.entries), tr, yt, au, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shows", help="프로그램 이름 파일(한 줄에 하나)")
    ap.add_argument("--search", nargs="*", default=[], help="주제어로 발굴")
    ap.add_argument("--out", required=True)
    ap.add_argument("--country", default="US")
    ap.add_argument("--limit", type=int, default=5, help="질의당 결과 수")
    ap.add_argument("--probe", type=int, default=20, help="피드당 확인할 최신 회차 수. 0이면 확인 안 함")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    terms = []
    if a.shows and os.path.isfile(a.shows):
        terms += [("show", l.strip()) for l in open(a.shows, encoding="utf-8") if l.strip() and not l.startswith("#")]
    terms += [("search", t) for t in a.search]
    if not terms:
        ap.error("--shows 또는 --search가 필요하다")

    feeds, fails = {}, []
    for kind, term in terms:
        lim = 1 if kind == "show" else a.limit          # 이름 조회는 최상위 하나만
        try:
            res = search(term, max(lim, 3), a.country)
        except Exception as e:
            fails.append({"term": term, "reason": str(e)[:120]}); print("%-30s 조회 실패" % term[:30]); continue
        hit = 0
        for r in res[: lim if kind == "show" else a.limit]:
            f = r.get("feedUrl")
            if not f or f in feeds:
                continue
            feeds[f] = {"feed": f, "name": r.get("collectionName"), "publisher": r.get("artistName"),
                        "episodes": r.get("trackCount"), "genres": r.get("genres") or [],
                        "found_by": kind, "query": term, "itunes_id": r.get("collectionId")}
            hit += 1
        print("%-30s %s → 피드 %d" % (term[:30], kind, hit))
        time.sleep(0.2)

    rows = []
    if a.probe:
        print()
        for f, m in feeds.items():
            total, tr, yt, au, err = probe(f, a.probe)
            m.update(total_entries=total, n_transcript_tag=tr, n_youtube=yt, n_audio=au, probe_error=err)
            route = ("전사 태그" if tr else ("유튜브" if yt else ("오디오뿐(ASR 필요)" if au else "확인 불가")))
            m["route"] = route
            rows.append(m)
            print("%-38s %-14s 전사 %2d · 유튜브 %2d · 오디오 %2d %s" % ((m["name"] or "")[:38], route, tr, yt, au, err))

    with open(os.path.join(a.out, "feeds.jsonl"), "w", encoding="utf-8") as fh:
        for m in feeds.values():
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    if rows:
        by = {}
        for m in rows:
            by.setdefault(m["route"], []).append(m)
        L = ["# 팟캐스트 전사 경로", "", "피드 %d개 · 최신 %d회차 기준" % (len(rows), a.probe), ""]
        for route in ("전사 태그", "유튜브", "오디오뿐(ASR 필요)", "확인 불가"):
            if route not in by:
                continue
            L += ["## %s (%d)" % (route, len(by[route])), ""]
            for m in sorted(by[route], key=lambda x: -(x.get("n_transcript_tag") or 0)):
                L.append("- **%s** — 총 %s회차 · 전사 %d · 유튜브 %d · `%s`" % (
                    m["name"], m.get("episodes"), m.get("n_transcript_tag") or 0, m.get("n_youtube") or 0, m["feed"]))
            L.append("")
        open(os.path.join(a.out, "routes.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    if fails:
        with open(os.path.join(a.out, "lookup_failures.jsonl"), "w", encoding="utf-8") as fh:
            for x in fails:
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("\n피드 %d개 → %s" % (len(feeds), os.path.join(a.out, "feeds.jsonl")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
