import paramiko

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!")

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:500])
    return out

# ===== 0. Current state check =====
print("=== Current Node.js ===")
run("node -v")
print("=== Current PM2 ===")
run("pm2 list | head -5")
print("=== Current nginx config check ===")
run("curl -s -I https://j3trisheng.com/api/status 2>&1 | head -10")
run("curl -s -I https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe 2>&1 | head -10")

ssh.close()
print("\n=== INITIAL CHECK DONE ===")
