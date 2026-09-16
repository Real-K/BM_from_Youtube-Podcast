# -*- coding: utf-8 -*-
"""자막이 없는 영상·오디오를 음성 전사(ASR)한다. whisper.cpp 바인딩(pywhispercpp) 사용.

**ASR 결과는 자동 자막과 같은 등급이다.** 사람이 만든 전사본이 아니다. 인명·기업명·숫자가 틀린다.
`references/tacit-knowledge.md`의 교정 규칙을 그대로 적용한다. 원문 보존을 위해 `raw.vtt`로 저장하고,
그다음은 기존 경로(`correct_transcript.py` → 판독 → `apply_corrections.py`)를 그대로 쓴다.

사용:
  python transcribe.py <YouTube URL 또는 id> --out out/<slug>/<id> [--model small] [--lang ko]
  python transcribe.py <오디오 URL(mp3 등)> --out out/pod/<ep> --title "..." [--model small]
  python transcribe.py <로컬 오디오·영상 파일> --out <dir>

모델: tiny · base · small · medium · large-v3. 실측(CPU, 2026-09):

| 모델 | 속도 | 한국어 고유명사 |
|---|---|---|
| base | 실시간의 12.6배 | "롯데 이노베이트"를 "못돼 이노베이트"로 |
| small | 실시간의 3.4배 | "롯데 이노베이트"로 옳게 옮김 |

**한국어는 small 이상을 쓴다.** base는 빠르지만 조직명이 무너져 사례 수집에 쓸 수 없다.

백엔드: 기본은 `whispercpp`(pywhispercpp). `--backend faster-whisper`도 있으나
**Python 3.14 + ctranslate2 4.8에서는 세그폴트로 죽는다**(2026-09 확인). 3.12 이하에서만 쓴다.
"""
import argparse, datetime, glob, io, json, os, shutil, subprocess, sys, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (transcript-collector)"}


def vtt_ts(sec):
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return "%02d:%02d:%02d.%03d" % (h, m, s, int(round((sec - int(sec)) * 1000)))


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit("ffmpeg가 필요하다: pip install imageio-ffmpeg")


def fetch_audio(target, out):
    """YouTube면 yt-dlp로, http면 직접, 로컬 파일이면 그대로. (경로, 메타)"""
    if os.path.isfile(target):
        return target, {}
    if target.startswith("http") and not any(h in target for h in ("youtube.com", "youtu.be")):
        path = os.path.join(out, "audio.bin")
        with urllib.request.urlopen(urllib.request.Request(target, headers=UA), timeout=300) as r, open(path, "wb") as f:
            shutil.copyfileobj(r, f)
        return path, {"url": target}
    url = target if target.startswith("http") else ("https://www.youtube.com/watch?v=" + target)
    base = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist"]
    p = subprocess.run(base + ["--dump-single-json", "--skip-download", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    info = json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else {}
    subprocess.run(base + ["-f", "bestaudio", "-o", os.path.join(out, "audio.%(ext)s"), url],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    got = [g for g in sorted(glob.glob(os.path.join(out, "audio.*"))) if not g.endswith(".wav")]
    if not got:
        raise SystemExit("오디오를 받지 못했다: " + url)
    return got[0], {"url": url, "id": info.get("id"), "title": info.get("title"),
                    "channel": info.get("channel") or info.get("uploader"),
                    "duration_sec": info.get("duration"), "upload_date": info.get("upload_date"),
                    "description_head": (info.get("description") or "")[:500]}


def to_wav16k(src, out):
    """whisper는 16kHz 모노를 받는다. 변환은 항상 한다 — 원본 컨테이너를 그대로 넘기면 디코더가 죽는 경우가 있다."""
    dst = os.path.join(out, "audio16k.wav")
    p = subprocess.run([ffmpeg_exe(), "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "wav", dst],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    if p.returncode != 0 or not os.path.isfile(dst):
        raise SystemExit("오디오 변환 실패: " + (p.stderr or "")[-300:])
    return dst


def run_whispercpp(wav, model, lang, threads):
    from pywhispercpp.model import Model
    kw = {"print_progress": False, "print_realtime": False, "redirect_whispercpp_logs_to": False}
    if threads:
        kw["n_threads"] = threads
    m = Model(model, **kw)
    detected, prob = lang, None
    if not lang or lang == "auto":
        try:
            best, _ = m.auto_detect_language(wav)
            detected, prob = best[0], float(best[1])
        except Exception:
            detected = None
    segs = m.transcribe(wav, language=detected) if detected else m.transcribe(wav)
    # t0·t1은 10ms 단위다
    return [(s.t0 / 100.0, s.t1 / 100.0, (s.text or "").strip()) for s in segs], detected, prob


def run_faster_whisper(wav, model, lang, threads):
    from faster_whisper import WhisperModel
    kw = {"device": "cpu", "compute_type": "int8"}
    if threads:
        kw["cpu_threads"] = threads
    m = WhisperModel(model, **kw)
    segs, info = m.transcribe(wav, language=(None if lang in (None, "auto") else lang), beam_size=1, vad_filter=True)
    return [(s.start, s.end, (s.text or "").strip()) for s in segs], info.language, float(info.language_probability or 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default=None)
    ap.add_argument("--id", dest="target_id", default=None, help="'-'로 시작하는 id를 넘길 때")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", default="auto", help="ko·en 등. auto면 판별한다")
    ap.add_argument("--backend", default="whispercpp", choices=("whispercpp", "faster-whisper"))
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--title", default="")
    ap.add_argument("--keep-audio", action="store_true")
    argv = sys.argv[1:]
    if argv and argv[0].startswith("-") and not argv[0].startswith("--") and len(argv[0]) == 11:
        argv = ["--id=" + argv[0]] + argv[1:]
    a = ap.parse_args(argv)
    target = a.target_id or a.target
    if not target:
        ap.error("영상 URL·id 또는 오디오 파일이 필요하다")
    os.makedirs(a.out, exist_ok=True)

    t0 = time.time()
    audio, info = fetch_audio(target, a.out)
    wav = to_wav16k(audio, a.out)
    t_prep = time.time() - t0

    t1 = time.time()
    runner = run_whispercpp if a.backend == "whispercpp" else run_faster_whisper
    segs, lang, prob = runner(wav, a.model, a.lang, a.threads)
    t_asr = time.time() - t1

    vtt = ["WEBVTT", "Kind: captions", "Source: ASR %s %s" % (a.backend, a.model), ""]
    last = 0.0
    for s, e, txt in segs:
        if not txt:
            continue
        vtt += ["%s --> %s" % (vtt_ts(s), vtt_ts(e)), txt, ""]
        last = max(last, e)
    open(os.path.join(a.out, "raw.vtt"), "w", encoding="utf-8").write("\n".join(vtt) + "\n")

    meta = {"id": info.get("id") or os.path.basename(os.path.abspath(a.out)), "url": info.get("url") or target,
            "title": info.get("title") or a.title, "channel": info.get("channel"),
            "duration_sec": info.get("duration_sec") or int(last), "upload_date": info.get("upload_date"),
            "description_head": info.get("description_head", ""),
            "transcript_auto": True, "transcript_source": "asr (%s %s)" % (a.backend, a.model),
            "transcript_lang": lang, "language_probability": (round(prob, 3) if prob else None),
            "transcript_track": "asr", "transcript_status": "asr", "segments": len([1 for _, _, t in segs if t]),
            "asr_seconds": round(t_asr, 1), "audio_seconds": round(last, 1),
            "realtime_factor": (round(last / t_asr, 1) if t_asr else None), "prep_seconds": round(t_prep, 1),
            "fetched_at": datetime.date.today().isoformat(), "tool": "pywhispercpp" if a.backend == "whispercpp" else "faster-whisper",
            "speaker": {"host": "", "guests": [], "attribution": "미확인", "note": "ASR은 화자를 구분하지 않는다"},
            "speaker_role": "unknown", "format": "", "reciting": [],
            "notes": "기계 전사다. 사람이 만든 전사본이 아니며 인명·기업명·숫자 오류가 있다. 교정 규칙을 적용한다."}
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if not a.keep_audio:
        for p in [audio, wav]:
            if os.path.basename(p).startswith(("audio.", "audio16k")):
                try:
                    os.remove(p)
                except OSError:
                    pass
    print("%s | %s | 언어 %s | 구간 %d | 오디오 %.0f초 · 전사 %.0f초 (%.1fx 실시간) · 준비 %.0f초"
          % (meta["id"], (meta["title"] or "")[:45], lang, meta["segments"], last, t_asr,
             meta["realtime_factor"] or 0, t_prep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
