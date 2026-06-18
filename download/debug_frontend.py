import paramiko
import sys

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

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
        if err: print(f"STDERR: {err[:1000]}")
        return out, err
    
    # Check API_BASE in deployed index.html
    run("grep -o 'API_BASE[^;]*' /home/admin/nexus-studio/index.html | head -5", "API_BASE in index.html")
    
    # Check health check endpoint pattern
    run("grep -oE 'fetch\(.*api.*|axios.*api.*|health|online|offline' /home/admin/nexus-studio/index.html | head -20", "Health check patterns")
    
    # Check if the frontend has error in its JS
    run("grep -oE '检测中|检查连接|loading|离线|online.*status' /home/admin/nexus-studio/index.html | head -10", "Loading/error text patterns")
    
    # Check the API_BASE from server-side
    run("grep -oE 'process\.env\.PORT|PORT =|3001|3002|3003' /home/admin/nexus-studio/index.html | head -10", "Port references in index.html")
    
    # Direct test of API proxy through nginx
    run("curl -s -m 3 -X POST https://j3trisheng.com/api/guest/sync -H 'Content-Type: application/json' -d '{\"fingerprint\":\"test\",\"ip\":\"1.1.1.1\"}' 2>&1", "Test API through nginx HTTPS")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
