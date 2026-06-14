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

download_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TriGen Desktop 下载</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body{background:#0f0a1a;color:#fff;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:linear-gradient(135deg,#1a1040,#2a1a50);border:1px solid rgba(108,78,245,.3);border-radius:16px;padding:48px;max-width:520px;width:90%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}
h1{font-size:28px;margin-bottom:8px;background:linear-gradient(135deg,#6c4ef5,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
p{color:#a090c0;margin:12px 0 24px;font-size:14px;line-height:1.6}
.dl-btn{display:inline-flex;align-items:center;gap:8px;padding:16px 40px;background:linear-gradient(135deg,#6c4ef5,#a855f7);color:#fff;border-radius:12px;text-decoration:none;font-size:16px;font-weight:600;transition:transform .2s,box-shadow .2s}
.dl-btn:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(108,78,245,.4)}
.info{font-size:12px;color:#6b5b95;margin-top:20px;line-height:1.8}
.badge{display:inline-block;padding:3px 10px;background:rgba(16,185,129,.15);color:#10b981;border-radius:6px;font-size:12px;margin:4px}
</style>
</head>
<body>
<div class="card">
  <div style="font-size:48px;margin-bottom:16px">🖥️</div>
  <h1>TriGen Desktop</h1>
  <p>AI 大模型聚合桌面客户端<br>135+ 大模型一键访问，写作/聊天/编程/绘图全能</p>
  <a class="dl-btn" href="/download/TriGen-Desktop-1.0.0-win-Setup.exe">⬇ 下载 Windows 安装包 (97MB)</a>
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
exit_status = stdout.channel.recv_exit_status()
print("download/index.html updated!" if exit_status == 0 else "Failed")

# Also check: is the "检测中" issue a browser cache problem?
# Let me add a cache-busting version to the HTML
stdin, stdout, stderr = ssh.exec_command("head -5 /home/admin/nexus-studio/index.html")
print("index.html head:", stdout.read().decode().strip()[:200])

ssh.close()
print("\n=== DONE ===")
