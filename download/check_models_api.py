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
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:3000])
    if err: print(f"ERR: {err[:300]}")

# Check what /api/models returns
print("=== /api/models full output ===")
run("curl -s -m 3 http://127.0.0.1:3001/api/models 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print(json.dumps(d[:5],indent=2)[:2000])\" 2>&1")

# Check models route in server.js
print("\n=== Models route handler ===")
run("grep -n -A20 \"app.get('/api/models'\" /home/admin/ai-nexus/server.js | head -30")

# Check the models-list endpoint
print("\n=== Models list route ===")
run("grep -n -A20 \"app.get('/api/models-list'\" /home/admin/ai-nexus/server.js | head -30")

# Check the models-count endpoint
print("\n=== Models count route ===")
run("grep -n -A10 \"app.get('/api/models-count'\" /home/admin/ai-nexus/server.js | head -20")

ssh.close()
