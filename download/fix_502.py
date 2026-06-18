import paramiko, time

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!\n")

def run(cmd, desc=""):
    if desc: print(f"  {desc}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f"    {out[:2000]}")
    if err: print(f"    ⚠️ {err[:300]}")
    return out, err

# Diagnose 502
print("🔥 Diagnosing 502...")
run("ss -tlnp | grep 3001 || echo 'NO 3001!'", "Port 3001")
run("pm2 logs nexus-hub --lines 15 --nostream 2>&1", "PM2 logs")

# Restart PM2
print("\n🔥 Restarting PM2...")
run("pm2 restart nexus-hub 2>&1", "Restart")
time.sleep(5)
run("pm2 list | head -5", "Status")
run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 200", "API localhost")
run("nginx -s reload 2>&1", "Reload nginx")
time.sleep(1)
run("curl -s -m 5 https://j3trisheng.com/api/status 2>&1 | head -c 200", "API via HTTPS")

print("\n=== DONE ===")
ssh.close()
