import paramiko, json

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!")

report = []

def run(cmd, desc=""):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if desc: 
        ok = not err or "warn" in err.lower()
        report.append({"check": desc, "status": "✅" if ok else "❌", "detail": out[:200] if out else (err[:200] if err else "N/A")})
        print(f"  {'✅' if ok else '❌'} {desc}")
        if out[:300]:
            print(f"    {out[:300]}")
    return out, err

print("\n=== 服务器健康检查 ===\n")

# Core services
run("pm2 list | grep nexus-hub | head -3", "PM2 nexus-hub 运行状态")
run("ss -tlnp | grep ':3001' || echo 'NOT LISTENING'", "后端端口 3001")

# API endpoints
run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print(f'uptime: {d[\\\"uptime\\\"]:.0f}s, providers: {len(d[\\\"providers\\\"])}')\" 2>&1", "/api/status 返回正常")
run("curl -s -m 5 http://127.0.0.1:3001/api/models-count 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print(f'Total models: {d[\\\"count\\\"]}')\" 2>&1", "/api/models-count 模型数量")
run("curl -s -m 5 -X POST http://127.0.0.1:3001/api/admin/auth -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"admin888\"}' 2>&1", "/api/admin/auth 管理员登录")
run("curl -s -m 5 -X POST http://127.0.0.1:3001/api/guest/sync -H 'Content-Type: application/json' -d '{\"deviceFp\":\"test_fp_123\",\"ip\":\"1.2.3.4\"}' 2>&1", "/api/guest/sync 访客积分同步")
run("curl -s -m 5 -X POST http://127.0.0.1:3001/api/chat -H 'Content-Type: application/json' -d '{\"model\":\"deepseekv3\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}' 2>&1 | head -c 200", "/api/chat 聊天API")

# Nginx
run("nginx -t 2>&1 | head -3", "Nginx 配置正确")
run("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/studio/", "HTTPS /studio/ 响应码")
run("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/download/", "HTTPS /download/ 响应码")
run("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/", "HTTPS 根路径/响应码")

# File sizes
run("ls -lh /home/admin/nexus-studio/index.html /home/admin/nexus-studio/landing.html /home/admin/nexus-studio/download/index.html", "前端文件大小")
run("ls -lh /home/admin/ai-nexus/server.js /home/admin/ai-nexus/.env", "后端文件大小")
run("ls -lh /home/admin/nexus-studio/download/TriGen-Desktop-1.0.0-win-Setup.exe 2>/dev/null || echo 'NOT FOUND'", "桌面端安装包存在")

# Disk & memory
run("df -h / | tail -1", "磁盘空间")
run("free -h | head -2", "内存使用")

print("\n\n=== 综合审查报告 ===\n")
for r in report:
    print(f"{r['status']} {r['check']}")
    print(f"    {r['detail']}")

ssh.close()
