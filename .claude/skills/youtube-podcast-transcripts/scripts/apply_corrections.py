# -*- coding: utf-8 -*-
"""corrections.jsonl을 clean.md에 적용해 corrected.md를 만든다. 원문은 손대지 않는다.

교정 자리: ⟦원문 → 교정 (basis)⟧ · 근거 없음: ⟦원문 [sic]⟧
검사: basis=none이면 corrected가 비어 있어야 한다. 원문 어구가 clean.md에 없으면 적용하지 않고 보고한다.

사용: python apply_corrections.py <dir>
"""
import io, json, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
KINDS = {"proper_noun", "number", "unit", "negation", "term", "speaker", "repeat", "host_insert", "reciting", "other"}
BASIS = {"arithmetic", "external", "context", "none"}
CONF = {"high", "medium", "low", "none"}


def main():
    d = sys.argv[1]
    clean = open(os.path.join(d, "clean.md"), encoding="utf-8").read()
    path = os.path.join(d, "corrections.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.isfile(path) else []
    bad, applied, missing = [], 0, []
    text = clean
    for i, r in enumerate(rows, 1):
        if r.get("kind") not in KINDS or r.get("basis") not in BASIS or r.get("confidence") not in CONF:
            bad.append("%d: 어휘 밖 %s/%s/%s" % (i, r.get("kind"), r.get("basis"), r.get("confidence")))
            continue
        if r["basis"] == "none" and (r.get("corrected") or "").strip():
            bad.append("%d: basis=none인데 corrected가 있다 — 근거 없는 교정" % i)
            continue
        if r["basis"] == "context" and r.get("confidence") == "high":
            bad.append("%d: context 근거는 high를 줄 수 없다" % i)
            continue
        orig = r.get("original") or ""
        if not orig or orig not in text:
            missing.append("%d: 원문 어구를 clean.md에서 찾지 못함: %r" % (i, orig[:60]))
            continue
        rep = ("⟦%s [sic]⟧" % orig) if r["basis"] == "none" else ("⟦%s → %s (%s)⟧" % (orig, r["corrected"], r["basis"]))
        text = text.replace(orig, rep, 1)
        applied += 1
    open(os.path.join(d, "corrected.md"), "w", encoding="utf-8").write(text)
    print("교정 %d 적용 · 못 찾음 %d · 오류 %d" % (applied, len(missing), len(bad)))
    for m in missing + bad:
        print("  ", m)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
