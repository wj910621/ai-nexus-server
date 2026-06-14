import paramiko
import sys

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("Connecting...")
    ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
    print("Connected!")
    
    def run(cmd, desc="", timeout=30):
        if desc: print(f"\n=== {desc} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out: print(out[:3000])
        if err: print(f"STDERR: {err[:500]}")
        return out, err
    
    # Check if /api/status endpoint exists in server.js
    run("grep -n 'api/status' /home/admin/ai-nexus/server.js", "Check /api/status endpoint")
    
    # Check all route definitions 
    run("grep -nE 'app\\.(get|post|use)\\(.*api' /home/admin/ai-nexus/server.js | head -30", "All API routes")
    
    # Test /api/status directly
    run("curl -s -m 3 http://127.0.0.1:3001/api/status 2>&1", "Direct test /api/status")
    
    # Test /api/status through nginx
    run("curl -s -m 3 https://j3trisheng.com/api/status 2>&1", "Through nginx /api/status")
    
    # Check the welcome credit message
    run("grep 'credited.*30\\|欢迎.*积分\\|首次.*积分' /home/admin/ai-nexus/server.js | head -5", "Credit welcome message")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
