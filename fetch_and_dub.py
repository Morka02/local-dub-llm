#!/usr/bin/env python3
"""
Front-end for Local Dub LLM v1.

Accepts EITHER:
  * a local video file / chunk folder  -> dubs it, or
  * a URL: a single YouTube video, a PLAYLIST, or a whole CHANNEL
           -> yt-dlp downloads every video, then each is dubbed.

All dubbed files are written to --dir (so the caller can upload that folder).
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEXT = (".mp4", ".mkv", ".webm", ".m4v", ".mov", ".avi", ".ts")


def is_url(s):
    return s.lower().startswith(("http://", "https://"))


def yt_download(url, dldir, cookies=None, limit=0, playlist=False):
    dldir.mkdir(parents=True, exist_ok=True)
    # Default download settings (your preferred flags).
    cmd = ["yt-dlp",
           "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
           "--merge-output-format", "mp4",
           "--concurrent-fragments", "18",
           "--no-mtime",
           "-o", str(dldir / "%(playlist_index)03d-%(title).100s-%(id)s.%(ext)s"),
           "--ignore-errors", "--no-overwrites", "--no-warnings",
           "--yes-playlist" if playlist else "--no-playlist"]
    if limit and limit > 0:
        cmd += ["--playlist-items", f"1-{limit}"]
    # Use cookies if given, else auto-pick a cookies.txt sitting next to this script.
    if not cookies:
        local_c = HERE / "cookies.txt"
        if local_c.exists():
            cookies = str(local_c)
    if cookies and Path(cookies).exists():
        cmd += ["--cookies", str(cookies)]
        print(f"[fetch] using cookies: {cookies}", flush=True)
    cmd.append(url)
    print(f"[fetch] yt-dlp downloading: {url}", flush=True)
    subprocess.run(cmd, check=False)
    return sorted(p for p in dldir.glob("*") if p.suffix.lower() in VIDEXT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Local file/folder OR a video/playlist/channel URL")
    ap.add_argument("--src", default="Hindi")
    ap.add_argument("--target", default="English")
    ap.add_argument("--genre", default="monologue")
    ap.add_argument("--speakers", default="1")
    ap.add_argument("--dir", required=True, help="Output folder for dubbed files")
    ap.add_argument("--turbo", action="store_true")
    ap.add_argument("--gaming", action="store_true")
    ap.add_argument("--cookies", default=None, help="cookies.txt for YouTube (optional)")
    ap.add_argument("--playlist", action="store_true",
                    help="Expand a playlist/channel link to ALL its videos (default: just the one link)")
    ap.add_argument("--limit", type=int, default=0, help="Max videos when --playlist is used")
    a = ap.parse_args()

    out = Path(a.dir); out.mkdir(parents=True, exist_ok=True)

    if is_url(a.input):
        files = yt_download(a.input, HERE / "_dl", a.cookies, a.limit, a.playlist)
        if not files:
            print("[fetch] Nothing downloaded. The link may be private, empty, or "
                  "blocked from this server (try cookies, or use a Drive link).")
            sys.exit(1)
    else:
        files = [Path(a.input)]

    print(f"[fetch] {len(files)} video(s) to dub.", flush=True)
    failed = 0
    for n, f in enumerate(files, 1):
        print(f"\n===== [{n}/{len(files)}] {f.name} =====", flush=True)
        cmd = [sys.executable, str(HERE / "dub_video.py"), str(f),
               "--src", a.src, "--target", a.target, "--genre", a.genre,
               "--speakers", str(a.speakers), "--dir", str(out)]
        if a.gaming:
            cmd.append("--gaming")
        elif a.turbo:
            cmd.append("--turbo")
        if subprocess.run(cmd).returncode != 0:
            failed += 1
    if failed:
        print(f"[fetch] {failed}/{len(files)} failed.")
    sys.exit(1 if failed == len(files) else 0)


if __name__ == "__main__":
    main()
