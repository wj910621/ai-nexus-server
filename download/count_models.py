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

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:2000])
    if err: print(f"ERR: {err[:500]}")

# Check models count from backend API
print("=== Models count from backend ===")
run("curl -s -m 3 http://127.0.0.1:3001/api/models-count 2>&1")

print("\n=== Full status from backend ===")
run("curl -s -m 3 http://127.0.0.1:3001/api/status 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);c=sum(len(v.get('models',[])) for v in d.get('providers',{}).values());print(f'Total model slots: {c}')\" 2>&1 || echo 'python parse failed'")

print("\n=== Models list count ===")
run("curl -s -m 3 http://127.0.0.1:3001/api/models-list 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print(f'Models: {len(d)}')\" 2>&1 || echo 'parse failed'")

print("\n=== Check front-end HTML for model numbers ===")
run("grep -oE '[0-9]+.*模型|模型.*[0-9]+' /home/admin/nexus-studio/index.html | head -10")

# Also get the exact models count page
run("curl -s -m 3 http://127.0.0.1:3001/api/models 2>&1 | python3 -c \"import sys,json;d=json.load(sys.stdin);print(f'Total models returned: {len(d)}')\" 2>&1 || echo 'parse failed'")

ssh.close()
print("\n=== DONE ===")
