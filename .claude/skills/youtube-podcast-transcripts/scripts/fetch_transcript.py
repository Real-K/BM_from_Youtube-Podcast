# -*- coding: utf-8 -*-
"""URL/ID → raw.vtt + meta.json. id가 '-'로 시작하면 --id로 넘기거나 URL을 쓴다. 수동 자막을 먼저, 없으면 자동 자막. 어느 쪽인지 기록한다.

사용: python fetch_transcript.py <url-or-id> --out <dir> [--langs en ko] [--asr]
  --asr  자막이 전혀 없을 때 faster_whisper가 설치돼 있으면 오디오를 받아 전사한다(선택, 느림)
"""
import argparse, datetime, glob, io, json, os, shutil, subprocess, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist"]


def run(args, timeout=180):
    p = subprocess.run(YTDLP + args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def norm_url(x):
    if x.startswith("http"):
        return x
    return "https://www.youtube.com/watch?v=" + x


def main():
    ap = argparse.ArgumentParser()
    # 영상 id는 '-'나 '_'로 시작할 수 있다. '-'로 시작하면 argparse가 옵션으로 읽어 죽으므로
    # 위치 인자 앞에 '--'가 없어도 되도록 먼저 분리한다. URL을 넘기는 쪽이 항상 안전하다.
    ap.add_argument("target", nargs="?", default=None)
    ap.add_argument("--id", dest="target_id", default=None, help="영상 id를 명시적으로 넘길 때 ('-'로 시작하는 id에 사용)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--langs", nargs="+", default=["en", "ko"])
    ap.add_argument("--asr", action="store_true")
    argv = sys.argv[1:]
    if argv and argv[0].startswith("-") and not argv[0].startswith("--") and len(argv[0]) == 11:
        argv = ["--id", argv[0]] + argv[1:]          # '-B__O2eqRYc' 같은 id
    a = ap.parse_args(argv)
    target = a.target_id or a.target
    if not target:
        ap.error("영상 URL 또는 id가 필요하다")
    url = norm_url(target)
    os.makedirs(a.out, exist_ok=True)

    rc, out, err = run(["--dump-single-json", "--skip-download", url])
    if rc != 0 or not out.strip():
        meta = {"url": url, "transcript_status": "blocked", "error": err.strip()[-600:],
                "fetched_at": datetime.date.today().isoformat(),
                "note": "yt-dlp 실패. 비YouTube 호스트·차단이면 .claude/skills/insane-search에서 python -m engine <URL> --trace 로 넘긴다."}
        json.dump(meta, open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("BLOCKED", url, err.strip()[-200:])
        return 2
    info = json.loads(out)
    manual = sorted((info.get("subtitles") or {}).keys())
    auto = sorted((info.get("automatic_captions") or {}).keys())
    vid = info.get("id") or a.target

    def pick(tracks):
        for l in a.langs:
            for t in tracks:
                if t == l or t.startswith(l + "-") or t.startswith(l + "."):
                    return t
        return None

    track, is_auto, status = pick(manual), False, "ok"
    if track is None:
        track, is_auto = pick(auto), True
    vtt_path = os.path.join(a.out, "raw.vtt")
    if track:
        tmpl = os.path.join(a.out, "sub.%(ext)s")
        flag = "--write-auto-subs" if is_auto else "--write-subs"
        rc, _, err = run(["--skip-download", flag, "--sub-lang", track, "--sub-format", "vtt", "-o", tmpl, url], timeout=300)
        got = sorted(glob.glob(os.path.join(a.out, "sub.*.vtt")))
        if got:
            shutil.move(got[0], vtt_path)
            for g in got[1:]:
                os.remove(g)
        else:
            status = "no_captions"
            track = None
    else:
        status = "no_captions"

    if status == "no_captions" and a.asr:
        try:
            import faster_whisper  # noqa: F401
            audio_tmpl = os.path.join(a.out, "audio.%(ext)s")
            rc, _, err = run(["-f", "bestaudio", "-o", audio_tmpl, url], timeout=900)
            aud = sorted(glob.glob(os.path.join(a.out, "audio.*")))
            if aud:
                from faster_whisper import WhisperModel
                model = WhisperModel("small")
                segs, _ = model.transcribe(aud[0])
                with open(vtt_path, "w", encoding="utf-8") as f:
                    f.write("WEBVTT\nKind: captions (ASR faster-whisper small)\n\n")
                    for s in segs:
                        def t(x):
                            h, r = divmod(int(x), 3600); m, se = divmod(r, 60)
                            return "%02d:%02d:%02d.%03d" % (h, m, se, int((x - int(x)) * 1000))
                        f.write("%s --> %s\n%s\n\n" % (t(s.start), t(s.end), s.text.strip()))
                status, is_auto, track = "asr", True, "asr"
        except ImportError:
            pass

    meta = {
        "id": vid, "url": url, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
        "uploader": info.get("uploader"), "duration_sec": info.get("duration"), "upload_date": info.get("upload_date"),
        "description_head": (info.get("description") or "")[:500],
        "transcript_auto": bool(is_auto) if track else None, "transcript_lang": (track or "").split("-")[0].split(".")[0] or None,
        "transcript_track": (track + (" (auto)" if is_auto else " (manual)")) if track else None,
        "manual_tracks": manual, "auto_tracks": auto[:12], "transcript_status": status,
        "fetched_at": datetime.date.today().isoformat(), "tool": "yt-dlp",
        "speaker": {"host": "", "guests": [], "attribution": "미확인", "note": ""},
        "speaker_role": "unknown", "format": "", "reciting": [], "notes": "",
    }
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("%s | %s | %s | 자막 %s (manual %d · auto %d)" % (vid, (info.get("title") or "")[:60], status, meta["transcript_track"], len(manual), len(auto)))
    return 0 if status in ("ok", "asr") else 1


if __name__ == "__main__":
    sys.exit(main())
