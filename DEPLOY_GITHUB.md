# Local Dub LLM v1 - run in the cloud, get the file in your Google Drive

Runs on GitHub's free cloud (your PC can be off). When it finishes, the dubbed
video lands **automatically in your Google Drive**. You only need a free GitHub
account (no credit card).

## A) One-time GitHub setup (~5 min)
1. Make a free account at https://github.com
2. Create a new repository (any name, e.g. `local-dub-llm`) and set it to
   **Public** (unlimited free minutes). The code shows no vendor name, your
   secrets stay private, and error logs are scrubbed of the endpoint - see
   "Public repo safety" below.
3. Upload everything in this folder into the repo (Add file -> Upload files ->
   drag it all in, including the hidden `.github` and the `engine` folder ->
   Commit).

## B) One-time Google Drive hookup (~5 min) - so files auto-land in Drive
This uses **rclone** (free) to let the cloud job write to your Drive.

1. On your PC, download rclone: https://rclone.org/downloads/ (unzip it).
2. Open a terminal in that folder and run:  `rclone config`
   - `n` (new remote) -> name it exactly **gdrive**
   - storage type: choose **drive** (Google Drive)
   - client_id / secret: just press Enter (leave blank)
   - scope: choose **1** (full access)
   - press Enter through the rest; when it asks "Use auto config?" choose **y** -
     a browser opens, sign in to your Google account, allow access.
   - "Configure this as a team drive?" -> **n** ;  then **y** to confirm ; **q** to quit.
3. Find your config file:  run  `rclone config file`  (it prints the path).
   Open that file, copy **all** of its text.
4. In your GitHub repo: **Settings -> Secrets and variables -> Actions -> New
   repository secret**:
   - Name: `RCLONE_CONF`  ->  Value: paste the whole config text -> Save.
   - (Optional) Add another secret `DRIVE_FOLDER` with the Drive folder name you
     want files saved into (default is `LocalDub`).

## C) Every time you want a dub
1. Put your source video somewhere with a link (easiest: Google Drive -> Share ->
   "Anyone with the link" -> copy link). A direct URL / Dropbox / YouTube link
   also works.
2. Repo -> **Actions** tab -> **Local Dub LLM** -> **Run workflow**.
3. Paste the link, set languages / genre / speakers, tick **turbo** if you want
   max speed, **Run workflow**.
4. Close your laptop. When the run finishes (green check), the dubbed
   `... DUB.mp4` is in your Google Drive `LocalDub` folder. (A copy is also under
   the run's **Artifacts** for 30 days, as backup.)

## Public repo safety
- **Unlimited minutes** on public repos (no monthly cap).
- **Secrets stay private.** `RCLONE_CONF` (and any `DUB_BASE_URL`) are encrypted
  and never shown, even on a public repo. Drive auto-upload keeps working.
- **Logs are scrubbed.** The run log is public, but the endpoint host and the
  vendor name are stripped from all error/retry text, so nothing leaks there.
- The only thing visible is the generic code and the video link you paste at run
  time - so use a Drive "anyone with the link" URL you're fine being seen, or
  flip the repo Private (2,000 min/mo) if a link must stay secret.

## Notes
- 6 hours max per run (a turbo ~60-90 min video fits fine).
- If you skip step B, it still works - the file just stays in **Artifacts** to
  download manually instead of going to Drive.
- Cloud IPs get rate-limited more than home, so expect some "retry" lines; the
  script retries automatically.
