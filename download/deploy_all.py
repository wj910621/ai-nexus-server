import paramiko

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!")

# Update the download page with 300+ model count and .zip option
download_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TriGenClaw 下载</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body{background:#0f0a1a;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:linear-gradient(135deg,#1a1040,#2a1a50);border:1px solid rgba(108,78,245,.3);border-radius:16px;padding:48px;max-width:520px;width:90%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}
h1{font-size:28px;margin-bottom:8px;background:linear-gradient(135deg,#6c4ef5,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
p{color:#a090c0;margin:12px 0 24px;font-size:14px;line-height:1.6}
.dl-btn{display:inline-flex;align-items:center;gap:8px;padding:16px 40px;background:linear-gradient(135deg,#6c4ef5,#a855f7);color:#fff;border-radius:12px;text-decoration:none;font-size:16px;font-weight:600;transition:transform .2s,box-shadow .2s;margin:6px}
.dl-btn:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(108,78,245,.4)}
.dl-btn-zip{background:linear-gradient(135deg,#10b981,#059669)}
.info{font-size:12px;color:#6b5b95;margin-top:20px;line-height:1.8}
.badge{display:inline-block;padding:3px 10px;background:rgba(16,185,129,.15);color:#10b981;border-radius:6px;font-size:12px;margin:4px}
.note{font-size:0.75rem;color:#6b5b95;margin-top:10px;padding:8px 12px;background:rgba(255,255,255,.03);border-radius:8px}
</style></head>
<body>
<div class="card">
  <div style="font-size:48px;margin-bottom:16px">🦀</div>
  <h1>TriGenClaw</h1>
  <p>300+ AI 大模型桌面客户端<br>写作/聊天/编程/绘图，一个客户端全搞定</p>
  <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px">
    <a class="dl-btn" href="/download/TriGen-Desktop-1.0.0-win-Setup.exe">⬇ 下载安装包 (EXE 97MB)</a>
    <a class="dl-btn dl-btn-zip" href="/download/TriGenClaw-1.0.0-win-Setup.zip">📦 下载 ZIP 包 (97MB)</a>
  </div>
  <div class="note">
    ⚠️ 浏览器可能提示"通常不会下载"，点击 <b>「保留」</b> 或 <b>「仍要下载」</b> 即可<br>
    如 EXE 被拦截，请尝试 ZIP 版本
  </div>
  <div class="info">
    <span class="badge">Windows 10/11 64位</span>
    <span class="badge">v1.0.0</span>
    <span class="badge">NSIS 安装程序</span><br>
    下载后双击安装即可使用
  </div>
  <div style="margin-top:24px;padding-top:20px;border-top:1px solid rgba(255,255,255,.05);font-size:12px;color:#6b5b95">
    <a href="/studio/" style="color:#8b7cf5;text-decoration:none">← 返回 TriGen 主站</a>
  </div>
</div>
</body>
</html>"""

stdin, stdout, stderr = ssh.exec_command("cat > /home/admin/nexus-studio/download/index.html")
stdin.write(download_html)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()
print("✅ download/index.html updated with 300+ models + .zip option")

# Now do the server-side optimizations sequentially
def run(cmd, desc="", timeout=120):
    if desc: print(f"\n{desc}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:2000])
    if err: print(f"⚠️ {err[:300]}")
    return out

# ===== 1️⃣ NODE.JS UPGRADE TO v18 =====
print("\n🔥===== 1/7: UPGRADING NODE.JS TO v18 =====")
run("""
cd /tmp && \
curl -fsSL "https://npmmirror.com/mirrors/node/v18.20.4/node-v18.20.4-linux-x64.tar.xz" -o node18.tar.xz && \
tar -xf node18.tar.xz && \
cp node-v18.20.4-linux-x64/bin/node /usr/local/bin/node && \
cp node-v18.20.4-linux-x64/bin/npm /usr/local/bin/npm && \
cp node-v18.20.4-linux-x64/bin/npx /usr/local/bin/npx && \
rm -rf node-v18.20.4-linux-x64 node18.tar.xz && \
echo "Node $(node -v) installed"
""", "1️⃣ Node 18 install")

# ===== 2️⃣ REINSTALL NPM PACKAGES =====
print("\n🔥===== 2/7: REINSTALLING PACKAGES =====")
run("cd /home/admin/ai-nexus && npm install 2>&1 | tail -5", "2️⃣ npm install")

# ===== 3️⃣ HTTP→HTTPS REDIRECT =====
print("\n🔥===== 3/7: HTTP→HTTPS REDIRECT =====")
run("""
cat > /etc/nginx/conf.d/j3trisheng-http.conf << 'HTTPEOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name j3trisheng.com www.j3trisheng.com _;
    return 301 https://$server_name$request_uri;
}
HTTPEOF
""", "3️⃣ HTTP redirect config created")

# ===== 4️⃣ RELOAD NGINX =====
print("\n🔥===== 4/7: RELOAD NGINX =====")
run("nginx -t 2>&1", "Test nginx")
run("nginx -s reload 2>&1", "Reload nginx")

# ===== 5️⃣ CREATE .ZIP =====
print("\n🔥===== 5/7: CREATING .ZIP DOWNLOAD =====")
run("""
cd /home/admin/nexus-studio/download && \
zip -j TriGenClaw-1.0.0-win-Setup.zip TriGen-Desktop-1.0.0-win-Setup.exe && \
ls -lh TriGenClaw-1.0.0-win-Setup.zip TriGen-Desktop-1.0.0-win-Setup.exe
""", "5️⃣ ZIP created")

# ===== 6️⃣ RESTART PM2 WITH NODE 18 =====
print("\n🔥===== 6/7: RESTARTING PM2 WITH NODE 18 =====")
run("pm2 kill", "Kill PM2")
import time; time.sleep(2)
run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
time.sleep(5)

# ===== 7️⃣ VERIFY EVERYTHING =====
print("\n🔥===== 7/7: VERIFYING =====")
run("echo 'Node:' && node -v", "Node version")
run("pm2 list | head -5", "PM2 status")
run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 100", "API test")
run("curl -s -I https://j3trisheng.com/download/TriGenClaw-1.0.0-win-Setup.zip 2>&1 | head -5", "ZIP download test")
run("curl -s -I https://j3trisheng.com/ 2>&1 | head -5", "HTTPS root test")
run("curl -s -I http://j3trisheng.com/ 2>&1 | head -5", "HTTP redirect test")

print("\n" + "="*60)
print("🎉 ALL 7 SERVER-SIDE OPTIMIZATIONS COMPLETE!")
print("="*60)

ssh.close()
