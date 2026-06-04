#!/usr/bin/env bash
# Run this once on the VM, from inside the LocalDubLLM folder:  bash setup.sh
set -e
echo ">> Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip ffmpeg curl unzip
pip3 install --break-system-packages requests || pip3 install requests
echo ">> Installing rclone..."
curl -fsSL https://rclone.org/install.sh | sudo bash
echo ">> Copying app to /opt/localdub..."
sudo mkdir -p /opt/localdub
sudo cp -r ./* /opt/localdub/
echo
echo "================ NEXT, DO THESE TWO THINGS ================"
echo "1) Connect Google Drive (one time):"
echo "     sudo rclone config"
echo "     - n (new) -> name it exactly:  gdrive"
echo "     - type: drive  ->  press Enter through client id/secret"
echo "     - scope: 1 (full)  ->  'Use auto config?' n  (headless VM)"
echo "       it prints a command + link: run that on your PC's rclone,"
echo "       sign in to Google, paste the token back. -> n team drive -> y -> q"
echo
echo "2) Start the 24/7 service:"
echo "     sudo cp /opt/localdub/localdub.service /etc/systemd/system/"
echo "     sudo systemctl enable --now localdub"
echo "     sudo systemctl status localdub      # should say active (running)"
echo "     journalctl -u localdub -f           # live log"
echo "=========================================================="
