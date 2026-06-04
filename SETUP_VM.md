# Local Dub LLM v1 - run it 24/7, unlimited, files via Google Drive

After setup you NEVER touch the server again. You just:
  drop a video in Google Drive `DubInbox`  ->  get the dub in `DubOutbox`.
Your PC can be off. No size cap, no time cap, no minute cap.

## What you log into
- A free cloud VM (Oracle Cloud "Always Free") - keeps running 24/7.
- Your Google account (once, to link Drive).
(The VM signup asks for a card for identity only; the Always-Free machine is
never billed.)

---

## STEP 1 - Make the free 24/7 server
1. Go to https://www.oracle.com/cloud/free/ -> Start for free -> sign up.
2. In the console: Menu -> Compute -> Instances -> Create instance.
   - Image: Ubuntu 22.04.  Shape: pick an **Always Free eligible** shape
     (Ampere A1, 1-2 OCPU / 6-12 GB is plenty; or the AMD Micro free shape).
   - Under "Add SSH keys" choose "Generate a key pair" and **download** both keys.
   - Create. Note the instance's **Public IP**.
3. Connect: easiest is the browser console (Instance page -> "Cloud Shell" or
   "Console connection"), or from your PC: `ssh -i <key> ubuntu@<PUBLIC_IP>`.

## STEP 2 - Put the code on the server
Easiest path - a private GitHub repo as the delivery pipe:
1. Make a free GitHub account, create a **Private** repo (e.g. `localdub`).
2. Upload everything in this folder to it (Add file -> Upload files -> Commit).
3. On the VM:
       sudo apt-get update && sudo apt-get install -y git
       git clone https://github.com/<you>/localdub.git
       cd localdub
   (Or skip GitHub: upload this zip to Drive, and `wget` its link on the VM.)

## STEP 3 - Install + connect Drive
1. On the VM, inside the folder:   `bash setup.sh`
2. Connect Google Drive when it tells you:   `sudo rclone config`
   - new remote -> name it exactly **gdrive** -> type **drive**
   - press Enter through client id/secret -> scope **1** (full)
   - "Use auto config?" -> **n** (it's a headless server). It prints a command;
     run that on your own PC's rclone, sign into Google, paste the token back.
   - team drive -> **n** -> confirm **y** -> **q** to quit.

## STEP 4 - Make the Drive folders
In your Google Drive, create two folders (exact names):
   - **DubInbox**   (you drop videos here)
   - **DubOutbox**  (dubbed files appear here)

## STEP 5 - Start it 24/7
       sudo cp /opt/localdub/localdub.service /etc/systemd/system/
       sudo systemctl enable --now localdub
       systemctl status localdub        # active (running)
       journalctl -u localdub -f        # watch it work

Done. Drop a video into **DubInbox** and within a minute it starts; the dubbed
file lands in **DubOutbox**, the original moves to **DubInbox/done**.

---

## Your questions answered
- **Where do I put big videos?**  Google Drive -> `DubInbox`. No size/time limit
  (VM disk is large; Drive does the transfer).
- **Where do my finished files go?**  Google Drive -> `DubOutbox`.
- **Where do I log into Drive?**  Once, via `sudo rclone config` on the VM.
- **Unlimited / 24/7?**  Yes - it's a normal always-on machine running a service
  that watches Drive forever. No GitHub minutes, no 6-hour cap.
- **Watermark?**  None. It uses your ORIGINAL video + only the dubbed audio, so
  nothing from the service's rendered (watermarked) video is ever used.

## Change languages / settings
Edit `/opt/localdub/localdub.env` (DUB_SRC, DUB_TGT, DUB_GENRE, DUB_SPEAKERS,
DUB_TURBO, DUB_POLL) then:  `sudo systemctl restart localdub`.

## Tips
- Free Drive is 15 GB - clear `DubOutbox`/`done` now and then.
- Cloud IPs get rate-limited by the engine more than home; the script retries
  automatically, just give it time.
- Oracle's free ARM shape is sometimes "out of capacity" - retry in another
  region or a bit later; the AMD Micro free shape is usually available.
