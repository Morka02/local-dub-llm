#!/usr/bin/env python3
"""
Local Dub LLM v1 - 24/7 worker.

Watches a Google Drive folder (DubInbox), dubs every new video it finds, drops
the result in DubOutbox, and archives the source to DubInbox/done. Runs forever;
managed by systemd so it survives reboots and crashes.

All settings come from environment variables (see localdub.env).
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REMOTE   = os.environ.get("DUB_REMOTE", "gdrive")
INBOX    = os.environ.get("DUB_INBOX", "DubInbox")
OUTBOX   = os.environ.get("DUB_OUTBOX", "DubOutbox")
DONE     = f"{INBOX}/done"
SRC      = os.environ.get("DUB_SRC", "Hindi")
TGT      = os.environ.get("DUB_TGT", "English")
GENRE    = os.environ.get("DUB_GENRE", "monologue")
SPEAKERS = os.environ.get("DUB_SPEAKERS", "1")
TURBO    = os.environ.get("DUB_TURBO", "1") == "1"     # turbo ON by default
POLL     = int(os.environ.get("DUB_POLL", "60"))       # seconds between checks
VIDEXT   = (".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".ts")

WORK = HERE / "_inbox"
OUT  = HERE / "_out"


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def rclone(*args, check=False):
    return subprocess.run(["rclone", *args], capture_output=True, text=True, check=check)


def list_inbox():
    r = rclone("lsf", f"{REMOTE}:{INBOX}", "--files-only")
    if r.returncode != 0:
        log(f"rclone lsf error: {r.stderr.strip()[:200]}")
        return []
    return [n.strip() for n in r.stdout.splitlines()
            if n.strip().lower().endswith(VIDEXT)]


def process(name):
    WORK.mkdir(exist_ok=True)
    if OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(exist_ok=True)
    local = WORK / name

    log(f"Downloading: {name}")
    r = rclone("copyto", f"{REMOTE}:{INBOX}/{name}", str(local))
    if r.returncode != 0 or not local.exists():
        log(f"  download failed: {r.stderr.strip()[:200]}"); return

    cmd = [sys.executable, str(HERE / "dub_video.py"), str(local),
           "--src", SRC, "--target", TGT, "--genre", GENRE,
           "--speakers", SPEAKERS, "--dir", str(OUT)]
    if TURBO:
        cmd.append("--turbo")
    log(f"Dubbing: {name}  ({SRC} -> {TGT}, turbo={TURBO})")
    rc = subprocess.run(cmd).returncode
    results = list(OUT.glob("*.mp4"))
    if rc != 0 or not results:
        log(f"  dub failed (exit {rc}); leaving source in inbox to retry later")
        local.unlink(missing_ok=True); return

    log(f"Uploading {len(results)} file(s) to {OUTBOX}")
    up = rclone("copy", str(OUT), f"{REMOTE}:{OUTBOX}", "--transfers", "1",
                "--drive-chunk-size", "64M")
    if up.returncode != 0:
        log(f"  upload failed: {up.stderr.strip()[:200]}"); return

    rclone("moveto", f"{REMOTE}:{INBOX}/{name}", f"{REMOTE}:{DONE}/{name}")
    local.unlink(missing_ok=True)
    shutil.rmtree(OUT, ignore_errors=True)
    log(f"DONE: {name} -> {OUTBOX}")


def main():
    log(f"Worker up. Watching {REMOTE}:{INBOX} every {POLL}s. "
        f"{SRC}->{TGT}, turbo={TURBO}.")
    while True:
        try:
            for name in list_inbox():
                process(name)
        except Exception as e:
            log(f"loop error: {e}")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
