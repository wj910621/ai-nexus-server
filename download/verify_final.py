import paramiko

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
    if out: print(f"    {out[:1500]}")
    if err: print(f"    ⚠️ {err[:300]}")
    return out

print("🔥 Final Verification:")
run("node -v", "Node version")
run("pm2 list | head -5", "PM2 status")
run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 200", "API via localhost")
run("curl -s -m 5 https://j3trisheng.com/api/status 2>&1 | head -c 200", "API via HTTPS")
run("curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}' https://j3trisheng.com/studio/", "Studio page")
run("curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}' https://j3trisheng.com/download/", "Download page")
run("curl -s -I http://j3trisheng.com/ 2>&1 | head -5", "HTTP redirect check")
run("curl -s -I https://j3trisheng.com/download/TriGenClaw-1.0.0-win-Setup.zip 2>&1 | head -5", "ZIP download")

print("\n=== VERIFICATION COMPLETE ===")
ssh.close()
