# -*- coding: utf-8 -*-
"""VTT → clean.md + flags.jsonl. 판단이 필요 없는 정리만 한다. 단어를 바꾸지 않는다.

  - 롤링 중복 제거 (자동 자막은 각 cue가 직전 줄을 반복한다)
  - <c> 단어 타이밍 태그·[music]·정렬 속성 제거
  - 문단화 + MM:SS locator
  - 의심 지점 표시: pct_mismatch · adjacent_conflict · number_unit_broken · spelling_cluster ·
    intra_repeat · host_insert · gap · truncated

사용: python correct_transcript.py raw.vtt --out <dir> [--title "..."] [--channel "..."]
"""
import argparse, difflib, html, io, json, os, re, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
NL = "\n"
TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
TAG_RE = re.compile(r"<[^>]+>")
NOISE_RE = re.compile(r"\[(?:music|applause|laughter|inaudible|__)\]", re.I)


def ts_to_sec(s):
    m = TS_RE.match(s)
    if not m:
        return None
    h, mi, se, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000.0


def fmt(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))


def parse_vtt(text):
    """[(start, end, [lines])]"""
    cues, block = [], []
    for line in text.splitlines() + [""]:
        if line.strip() == "":
            if block:
                cues.append(block)
                block = []
            continue
        block.append(line)
    out = []
    for b in cues:
        if b[0].startswith("WEBVTT") or b[0].startswith("Kind:") or b[0].startswith("Language:"):
            continue
        hdr = None
        for i, l in enumerate(b):
            if "-->" in l:
                hdr = i
                break
        if hdr is None:
            continue
        a, _, rest = b[hdr].partition("-->")
        start = ts_to_sec(a.strip())
        end = ts_to_sec(rest.strip().split()[0]) if rest.strip() else start
        lines = []
        for l in b[hdr + 1:]:
            l = html.unescape(TAG_RE.sub("", l))
            l = NOISE_RE.sub("", l)
            l = " ".join(l.split())
            if l:
                lines.append(l)
        out.append((start, end, lines))
    return out


def dedupe_rolling(cues):
    """롤링 윈도 자막의 직전 줄 반복을 없앤다. 반환: [(start, end, line)]"""
    seg, prev = [], set()
    for start, end, lines in cues:
        fresh = [l for l in lines if l not in prev]
        for l in fresh:
            seg.append((start, end, l))
        prev = set(lines) if lines else prev
    return seg


def paragraphs(seg, max_gap=2.5, target_chars=520):
    """cue 간격이 크면 문단을 끊는다. 길어지면 문장 끝에서 끊는다. 시각은 그 줄의 cue 시작."""
    paras, cur, cur_start, last_end = [], [], None, None
    for start, end, line in seg:
        gap = (start - last_end) if last_end is not None else 0
        if cur and gap > max_gap:
            paras.append((cur_start, last_end, " ".join(cur)))
            cur, cur_start = [], None
        if cur_start is None:
            cur_start = start
        if cur and len(" ".join(cur)) >= target_chars:
            m = None
            for m in re.finditer(r"[.?!][\"'”]?\s+(?=[A-Z>\"'“])", line):
                pass
            if m:
                cur.append(line[:m.end()].rstrip())
                paras.append((cur_start, end, " ".join(cur)))
                cur, cur_start = [line[m.end():]], start
                last_end = end
                continue
        cur.append(line)
        last_end = end
    if cur:
        paras.append((cur_start, last_end, " ".join(cur)))
    return [(s, e, t) for s, e, t in paras if t.strip()]


NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
PAIR_RE = re.compile(NUM + r"\s*(?:to|→|->|down to|up to|into)\s*" + NUM, re.I)
FROM_RE = re.compile(r"from\s*" + NUM + r"\s*(?:to|→|->|down to)\s*" + NUM, re.I)
PCT_RE = re.compile(r"(?:over|about|around|nearly|almost|roughly)?\s*(\d+(?:\.\d+)?)\s*%")
UNIT_WORDS = r"(percent|million|millions|billion|billions|thousand|k|m|b|hours?|minutes?|seconds?|days?|weeks?|months?|years?|petabytes?|terabytes?|gigabytes?|requests?|calls?|events?|customers?|users?|agents?|mips|dollars?|usd|eur|gbp)"
UNIT_NUM_RE = re.compile(r"\b" + NUM + r"\s*" + UNIT_WORDS + r"\b", re.I)
GLUED_RE = re.compile(r"\b\d[\d,\.]*[a-zA-Z]{3,}\b")           # 100,000memes
DOUBLE_NUM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*%")   # 90 95%
MILLIONS_TAIL_RE = re.compile(r"\b(millions?|billions?)\s+(\d{1,3})\b", re.I)  # 4 millions 10
REPEAT_RE = re.compile(r"\b((?:\w+[\s'’]+){1,4}\w+)\s+\1\b", re.I)
HOST_RE = re.compile(r">>")
CAP_RE = re.compile(r"\b[A-Z][a-zA-Z]{3,}\b")
STOP = set("""The This That These Those There Then They Their Them When Where What Which While With Without
Because Before After About Above Again Also Always Another Anyone Anything Around Being Between Both Could Should Would
Every Everything First Second Third Great Here However Just Like Look Maybe Might More Most Much Never Next Nothing Only
Other Over People Please Pretty Really Right Same Since Some Something Still Such Sure Thank Thanks Thing Things Think
Those Through Today Under Until Very Well Were Will Yeah Yes Your Okay Actually Basically Obviously Question Questions
Answer Number Percent Company Companies Customer Customers Business Model Models Agent Agents Team Teams Data Product
Products System Systems Process Time Year Years Month Months Week Weeks Day Days Hour Hours Minute Minutes""".split())


def to_num(s):
    return float(s.replace(",", ""))


def flag_numbers(paras):
    flags = []
    seen_pairs = set()
    units_seen = []  # (ts, value, unit, text)
    for start, end, text in paras:
        ts = fmt(start)
        # 비율 검산
        for rex in (FROM_RE, PAIR_RE):
            for m in rex.finditer(text):
                try:
                    a, b = to_num(m.group(1)), to_num(m.group(2))
                except ValueError:
                    continue
                if a <= 0 or a == b:
                    continue
                if re.match(r"\s*%", text[m.end():m.end() + 3]):      # "80 to 85%" — 구간이지 변화가 아니다
                    continue
                win = text[max(0, m.start() - 160): m.end() + 200]
                for pm in PCT_RE.finditer(win):
                    if 160 - 10 <= pm.start() <= 160 + (m.end() - m.start()) + 2 and m.start() >= 160:
                        continue                                          # 쌍 자체에 붙은 %
                    stated = float(pm.group(1))
                    comp = abs(a - b) / a * 100.0
                    if abs(stated - comp) >= 3.0 and stated < 1000:
                        flags.append({"ts": ts, "kind": "pct_mismatch",
                                      "text": " ".join(win.split())[:220],
                                      "detail": {"a": a, "b": b, "stated_pct": stated, "computed_pct": round(comp, 1)}})
        # 숫자·단위 깨짐
        for m in GLUED_RE.finditer(text):
            flags.append({"ts": ts, "kind": "number_unit_broken", "text": m.group(0), "detail": {"pattern": "glued"}})
        for m in DOUBLE_NUM_RE.finditer(text):
            flags.append({"ts": ts, "kind": "number_unit_broken", "text": m.group(0), "detail": {"pattern": "two numbers before %"}})
        for m in MILLIONS_TAIL_RE.finditer(text):
            flags.append({"ts": ts, "kind": "number_unit_broken", "text": m.group(0), "detail": {"pattern": "unit word then number"}})
        # 같은 단위의 값 두 개 + 뒤따르는 비율 ("20,000 MIPS … 3,000 mips … over 9%")
        ums = list(UNIT_NUM_RE.finditer(text))
        for m1, m2 in zip(ums, ums[1:]):
            if m1.group(2).lower().rstrip("s") != m2.group(2).lower().rstrip("s"):
                continue
            try:
                a, b = to_num(m1.group(1)), to_num(m2.group(1))
            except ValueError:
                continue
            if a <= 0 or a == b or m2.start() - m1.end() > 260:
                continue
            tail = text[m2.end(): m2.end() + 200]
            for pm in PCT_RE.finditer(tail):
                stated = float(pm.group(1))
                comp = abs(a - b) / a * 100.0
                if abs(stated - comp) >= 3.0 and stated < 1000:
                    key = (ts, a, b, stated)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    flags.append({"ts": ts, "kind": "pct_mismatch",
                                  "text": " ".join(text[m1.start(): m2.end() + pm.end()].split())[:260],
                                  "detail": {"a": a, "b": b, "unit": m1.group(2), "stated_pct": stated, "computed_pct": round(comp, 1)}})
        # 같은 단위의 값 수집
        for m in UNIT_NUM_RE.finditer(text):
            try:
                units_seen.append((ts, to_num(m.group(1)), m.group(2).lower().rstrip("s"), m.group(0)))
            except ValueError:
                pass
    # 인접 발언(≤3분)에서 같은 단위, 다른 값, 비율 차 ≤25% → 충돌 후보
    def sec_of(t):
        p = [int(x) for x in t.split(":")]
        return p[0] * 60 + p[1] if len(p) == 2 else p[0] * 3600 + p[1] * 60 + p[2]
    seen = set()
    for i, (t1, v1, u1, s1) in enumerate(units_seen):
        for t2, v2, u2, s2 in units_seen[i + 1:i + 40]:
            if u1 != u2 or v1 == v2 or v1 == 0:
                continue
            if abs(sec_of(t2) - sec_of(t1)) > 180:
                continue
            if abs(v1 - v2) / max(v1, v2) <= 0.25 and (s1, s2) not in seen:
                seen.add((s1, s2))
                flags.append({"ts": t1, "kind": "adjacent_conflict", "text": s1, "detail": {"other_ts": t2, "other": s2}})
    return flags


def flag_structure(seg, paras):
    flags = []
    for start, end, text in paras:
        ts = fmt(start)
        for m in REPEAT_RE.finditer(text):
            ph = m.group(1)
            if len(ph.split()) >= 3:
                flags.append({"ts": ts, "kind": "intra_repeat", "text": m.group(0)[:160], "detail": {"phrase": ph}})
        for hm in HOST_RE.finditer(text):
            i = hm.start()
            before = text[:i].rstrip()
            if not before or re.search(r"[.?!][\"'”)]?$", before):
                continue                                  # 문장 끝의 화자 전환은 정상
            flags.append({"ts": ts, "kind": "host_insert", "text": text[max(0, i - 60): i + 60],
                          "detail": {"cut_before": before[-40:]}})
    # 공백·절단
    for (s1, e1, l1), (s2, e2, l2) in zip(seg, seg[1:]):
        gap = s2 - e1
        if gap >= 4.0:
            kind = "truncated" if not re.search(r"[.?!]\s*$", l1) else "gap"
            flags.append({"ts": fmt(e1), "kind": kind, "text": l1[-120:], "detail": {"gap_sec": round(gap, 1)}})
    return flags


def flag_spelling(paras):
    cnt = collections.Counter()
    for _, _, text in paras:
        for m in CAP_RE.finditer(text):
            w = m.group(0)
            if w not in STOP:
                cnt[w] += 1
    words = [w for w, c in cnt.items() if c >= 1]
    groups, used = [], set()
    for i, w in enumerate(words):
        if w in used:
            continue
        g = [w]
        for v in words[i + 1:]:
            if v in used:
                continue
            wl, vl = w.lower(), v.lower()
            if wl == vl or wl.startswith(vl) or vl.startswith(wl):
                continue                                  # 굴절형(India/Indian)은 오철자가 아니다
            if difflib.SequenceMatcher(None, wl, vl).ratio() >= 0.8:
                g.append(v)
        if len(g) >= 2 and sum(cnt[x] for x in g) >= 3:
            used.update(g)
            groups.append({x: cnt[x] for x in g})
    return [{"ts": "", "kind": "spelling_cluster", "text": "", "detail": {"variants": g}} for g in groups]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vtt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--channel", default="")
    a = ap.parse_args()
    with open(a.vtt, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    cues = parse_vtt(text)
    seg = dedupe_rolling(cues)
    paras = paragraphs(seg)
    flags = flag_numbers(paras) + flag_structure(seg, paras) + flag_spelling(paras)
    os.makedirs(a.out, exist_ok=True)
    total = fmt(seg[-1][1]) if seg else "00:00"
    head = ["# " + (a.title or os.path.basename(a.vtt)),
            " · ".join(x for x in [a.channel, "길이 " + total, "원문 raw.vtt", "정리 correct_transcript.py"] if x), ""]
    body = ["**[%s]** %s" % (fmt(s), t) for s, e, t in paras]
    with open(os.path.join(a.out, "clean.md"), "w", encoding="utf-8") as fh:
        fh.write(NL.join(head + body) + NL)
    with open(os.path.join(a.out, "flags.jsonl"), "w", encoding="utf-8") as f:
        for fl in flags:
            f.write(json.dumps(fl, ensure_ascii=False) + NL)
    kinds = collections.Counter(f["kind"] for f in flags)
    print("cues %d → 줄 %d → 문단 %d | 의심 %d %s" % (len(cues), len(seg), len(paras), len(flags), dict(kinds)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
