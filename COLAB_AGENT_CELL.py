# ============================================================================
#  COLAB AGENT  (perfect build)  —  paste this whole cell into Colab and run.
#
#  Transport design (chosen after real speed-testing):
#    * CONTROL  -> cloudflared tunnel to Flask :CTRL_PORT  (exec/shell/health)
#    * FILES    -> bore.pub tunnel to a threaded file server :FILE_PORT
#                  (bore is ~10x faster than a cloudflared quick-tunnel for big
#                   files, free, unlimited, no signup). curl on the client side
#                   pulls through it reliably.
#    * INTO COLAB -> aria2c (installed here) at 16x16 from the internet. Blazing
#                    on Colab's datacenter network.
#
#  Free-port logic: servers run as THREADS in the kernel, so we can't kill a
#  squatting port. Instead each run binds the next FREE port, so a re-run always
#  serves THIS run's code (no stale-server problem).
#
#  Runtime > Change runtime type > GPU.  Keep this cell RUNNING.
# ============================================================================
import subprocess, threading, time, os, re, sys, io, contextlib, traceback, glob, json, socket
import http.server, socketserver

TOKEN    = "sarvam-colab-7Qx2"     # shared secret; must match the MCP server's COLAB_TOKEN
FILE_DIR = "/content"              # root the file server serves / accepts uploads under
CTRL_PORT_BASE, FILE_PORT_BASE = 8000, 8011

# --- TAILSCALE (native-speed direct link, free) -----------------------------
# Paste your REUSABLE auth key here (https://login.tailscale.com/admin/settings/keys).
# When set, Colab joins your Tailscale network on launch and the file server is
# reachable directly at Colab's 100.x.x.x IP - native speed, no bore for transfers.
TAILSCALE_AUTHKEY = ""   # e.g. "tskey-auth-xxxxxxxxxxxx"

def _start_tailscale():
    if not TAILSCALE_AUTHKEY:
        print("tailscale: no authkey set (skipping; using bore only)")
        return None
    try:
        # install if missing
        if subprocess.run("which tailscale", shell=True, capture_output=True).returncode != 0:
            subprocess.run("curl -fsSL https://tailscale.com/install.sh | sh", shell=True,
                           capture_output=True)
        # Colab has no TUN device -> userspace networking mode
        subprocess.Popen("tailscaled --tun=userspace-networking "
                         "--socks5-server=localhost:1055 --outbound-http-proxy-listen=localhost:1056",
                         shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        subprocess.run(f"tailscale up --authkey={TAILSCALE_AUTHKEY} --hostname=colab-gpu "
                       f"--accept-routes", shell=True, capture_output=True, text=True, timeout=60)
        ip = subprocess.run("tailscale ip -4", shell=True, capture_output=True, text=True).stdout.strip()
        return ip or None
    except Exception as e:
        print("tailscale setup failed:", e)
        return None

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "flask"])
# aria2 (for fast pulls FROM the internet INTO Colab) + cloudflared + bore
subprocess.run("which aria2c >/dev/null 2>&1 || (apt-get -qq update && apt-get -qq install -y aria2)", shell=True)
CF = os.path.abspath("./cloudflared")
if not os.path.exists(CF):
    subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/"
                   "cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared", shell=True)
    CF = os.path.abspath("./cloudflared")
BORE = os.path.abspath("./bore")
if not os.path.exists(BORE):
    subprocess.run("wget -q https://github.com/ekzhang/bore/releases/download/v0.5.1/"
                   "bore-v0.5.1-x86_64-unknown-linux-musl.tar.gz -O /tmp/bore.tgz "
                   "&& tar xzf /tmp/bore.tgz -C . && chmod +x ./bore", shell=True)
    BORE = os.path.abspath("./bore")

subprocess.run("pkill -f 'cloudflared tunnel' 2>/dev/null; pkill -f 'bore local' 2>/dev/null", shell=True)

def free_port(start):
    p = start
    while p < start + 60:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as t:
            t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                t.bind(("0.0.0.0", p)); return p
            except OSError:
                p += 1
    return start

CTRL_PORT = free_port(CTRL_PORT_BASE)
FILE_PORT = free_port(FILE_PORT_BASE)
print(f"binding control:{CTRL_PORT}  file:{FILE_PORT}")

STATE = {"file_url": None, "ts_ip": None}   # tunnel addrs + tailscale IP

# bring up tailscale early (so its IP is known by the time we print the banner)
STATE["ts_ip"] = _start_tailscale()

# ----------------------------- CONTROL SERVER (Flask) -----------------------
from flask import Flask, request, jsonify, send_file
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024 * 1024  # 32 GB
NS = {}   # persistent namespace for /exec

def _auth(req):
    return req.headers.get("X-Token") == TOKEN

@app.post("/exec")
def _exec():
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    code = (request.get_json(force=True, silent=True) or {}).get("code", "")
    buf = io.StringIO(); out = {"ok": True, "stdout": "", "error": None}
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(code, NS)
    except Exception:
        out["ok"] = False; out["error"] = traceback.format_exc()
    out["stdout"] = buf.getvalue()[-200000:]
    return jsonify(out)

@app.post("/shell")
def _shell():
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    cmd = (request.get_json(force=True, silent=True) or {}).get("cmd", "")
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return jsonify({"ok": p.returncode == 0, "stdout": p.stdout[-200000:],
                    "stderr": p.stderr[-50000:], "code": p.returncode})

@app.get("/health")
def _health():
    gpu = "no-GPU"
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no-GPU"
    except Exception:
        pass
    return jsonify({"ok": True, "gpu": gpu, "file_url": STATE["file_url"],
                    "ts_ip": STATE["ts_ip"],
                    "file_port": FILE_PORT, "file_dir": FILE_DIR})

@app.get("/fileurl")
def _fileurl():
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": True, "file_url": STATE["file_url"], "file_dir": FILE_DIR})

@app.get("/listfiles")
def _listfiles():
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    pat = request.args.get("glob", FILE_DIR + "/*")
    files = {p: os.path.getsize(p) for p in sorted(glob.glob(pat)) if os.path.isfile(p)}
    return jsonify({"ok": True, "files": files, "count": len(files)})

# control-tunnel file fallbacks (small files); the bore FILE tunnel is the fast path
@app.get("/getfile")
def _getfile():
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    p = request.args.get("path", "")
    if not p or not os.path.exists(p): return jsonify({"error": "not found", "path": p}), 404
    return send_file(p, as_attachment=True, mimetype="application/octet-stream",
                     download_name=os.path.basename(p))

@app.post("/aria2")
def _aria2():
    """aria2c ON COLAB: pull URLs from the internet into a Colab dir at 16x16."""
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(force=True, silent=True) or {}
    urls = body.get("urls", []); ddir = body.get("dir", "/content/downloads")
    x = int(body.get("x", 16)); j = int(body.get("j", 16))
    if not urls: return jsonify({"ok": False, "error": "no urls"})
    os.makedirs(ddir, exist_ok=True)
    with open("/tmp/aria_in.txt", "w") as f:
        f.write("\n".join(urls))
    cmd = (f"aria2c -i /tmp/aria_in.txt -d {ddir} -x{min(16,x)} -s{min(16,x)} -j{min(16,j)} "
           f"--max-tries=5 --retry-wait=2 --continue=true --allow-overwrite=true "
           f"--console-log-level=warn --summary-interval=0")
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    got = [f for f in os.listdir(ddir) if os.path.isfile(os.path.join(ddir, f))]
    return jsonify({"ok": p.returncode == 0, "dir": ddir, "downloaded": len(got),
                    "files": got[:200], "rc": p.returncode, "stderr": p.stderr[-1000:]})

# manifest for diff-based sync
import hashlib
def _sig(path, size):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            h.update(f.read(65536))
            if size > 131072:
                f.seek(-65536, os.SEEK_END); h.update(f.read(65536))
        return f"{size}-{h.hexdigest()}"
    except Exception:
        return f"{size}-0"

@app.get("/sync/manifest")
def _manifest():
    if not _auth(request): return jsonify({"error": "unauthorized"}), 401
    root = request.args.get("dir", FILE_DIR)
    out = {}
    if os.path.isdir(root):
        for dp, _, fs in os.walk(root):
            for fn in fs:
                full = os.path.join(dp, fn)
                try:
                    st = os.stat(full)
                    out[os.path.relpath(full, root).replace("\\", "/")] = {
                        "size": st.st_size, "sig": _sig(full, st.st_size)}
                except Exception:
                    pass
    return jsonify({"ok": True, "root": root, "count": len(out), "files": out})

# ----------------------------- FILE SERVER (HTTP/1.1, Range-capable) ---------
# HTTP/1.1 + explicit Range support so the Rust parallel downloader (rdl.exe) and
# parallel curl can fetch byte ranges concurrently (multi-x speedup over bore).
class FileHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def __init__(self, *a, **k):
        super().__init__(*a, directory=FILE_DIR, **k)
    def log_message(self, *a):
        pass
    def do_PUT(self):
        if self.headers.get("X-Token") != TOKEN:
            self.send_response(401); self.send_header("Content-Length", "0"); self.end_headers(); return
        dest = os.path.join(FILE_DIR, self.path.lstrip("/"))
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        n = int(self.headers.get("Content-Length", 0))
        with open(dest, "wb") as f:
            rem = n
            while rem > 0:
                c = self.rfile.read(min(1048576, rem))
                if not c: break
                f.write(c); rem -= len(c)
        self.send_response(201); self.send_header("Content-Length", "2"); self.end_headers()
        self.wfile.write(b"OK")
    def do_GET(self):
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().do_GET()
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            try:
                s, e = rng[6:].split("-")
                start = int(s) if s else 0
                end = int(e) if e else size - 1
                end = min(end, size - 1)
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                self.end_headers()
                with open(path, "rb") as f:
                    f.seek(start); remaining = length
                    while remaining > 0:
                        chunk = f.read(min(1048576, remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining -= len(chunk)
                return
            except Exception:
                pass
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.end_headers()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1048576)
                if not chunk: break
                self.wfile.write(chunk)

def _serve_files():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", FILE_PORT), FileHandler) as httpd:
        httpd.serve_forever()

# ----------------------------- LAUNCH ---------------------------------------
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=CTRL_PORT, threaded=True), daemon=True).start()
threading.Thread(target=_serve_files, daemon=True).start()

time.sleep(2)

# CONTROL tunnel via cloudflared
def _cf_tunnel(port):
    p = subprocess.Popen([CF, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    for line in p.stdout:
        m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line)
        if m: return m.group(0)
        if time.time() - t0 > 45: break
    return None

# FILE tunnel via bore
def _bore_tunnel(port):
    p = subprocess.Popen([BORE, "local", str(port), "--to", "bore.pub"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    for line in p.stdout:
        m = re.search(r"bore\.pub:(\d+)", line)
        if m: return f"http://bore.pub:{m.group(1)}"
        if time.time() - t0 > 30: break
    return None

ctrl_url = _cf_tunnel(CTRL_PORT)
file_url = _bore_tunnel(FILE_PORT)
STATE["file_url"] = file_url

print("\n\n========  COLAB MCP BRIDGE READY (perfect build)  ========")
print("COLAB_URL  :", ctrl_url, "   <- give this to Claude (control tunnel)")
print("FILE_URL   :", file_url, "   <- bore file tunnel (fast, auto-used by the MCP)")
if STATE["ts_ip"]:
    print("TAILSCALE  :", STATE["ts_ip"], f"  <- NATIVE SPEED: file server :{FILE_PORT} direct, no bore!")
print("COLAB_TOKEN:", TOKEN)
print("Files served from", FILE_DIR, "| aria2 on Colab for internet pulls.")
print("Keep this cell running. ========================================")
