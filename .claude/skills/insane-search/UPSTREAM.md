# Vendored: insane-search

| | |
|---|---|
| Upstream | https://github.com/fivetaku/insane-search (marketplace: fivetaku/gptaku_plugins) |
| Version | 0.16.3 (2026-09-08); marketplace commit f9fe95475ba89ffd2928ecc61f011a0d19b5245d |
| License | MIT — `LICENSE` and `DISCLAIMER.md` are copied verbatim. Copyright (c) 2026 fivetaku |
| Copied | `SKILL.md`, `engine/`, `references/`, `tests/` |
| Not copied | `setup/` (GitHub-star prompt, SessionStart update-notifier hook that edits `~/.claude/settings.json`), `assets/` (4.8 MB images), `observations/` (runtime logs), `.claude-plugin/plugin.json`, `__pycache__` |

## Local modifications

1. `SKILL.md`: the "Step 0" first-run block (star prompt via `setup.sh`) is removed; `${CLAUDE_PLUGIN_ROOT}` paths are
   rewritten to `.claude/skills/insane-search`. No engine code is changed.
2. `observations/` is created at runtime by `engine/observations_log.py` inside this directory and is gitignored.
   Override with `INSANE_OBSERVATIONS_DIR`. Route learning still goes to `~/.insane_search/learned.json` (upstream default).

## Python dependencies

Required for the fetch chain: `curl_cffi`, `pyyaml`, `markdownify`. Optional: `pypdf`/`pdfplumber` (PDF), `resiliparse`
(main-content extraction), `nodriver`/`patchright` + Node + system Chrome (browser fallback lanes). yt-dlp for media.
Without `curl_cffi` the engine reports `curl_cffi not installed` and only Phase 0 official-API routes work.

## Updating

Re-copy the four items above from a newer marketplace cache, re-apply modification 1, bump this file.
