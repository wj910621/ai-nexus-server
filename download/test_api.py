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
    
    # Test with proper POST request
    run("""curl -s -X POST http://127.0.0.1:3001/api/admin/auth \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin888"}' 2>&1""", "Test admin login with POST")
    
    # Test chat endpoint
    run("""curl -s -X POST http://127.0.0.1:3001/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseekv3","message":"hi","guest":true}' 2>&1 | head -c 500""", "Test chat API")
    
    # Test guest sync
    run("""curl -s -X POST http://127.0.0.1:3001/api/guest/sync \
  -H 'Content-Type: application/json' \
  -d '{"fingerprint":"test123","ip":"1.2.3.4"}' 2>&1""", "Test guest sync API")
    
    # Check recent PM2 logs
    run("pm2 logs nexus-hub --lines 15 --nostream 2>&1 | head -20", "Recent PM2 logs")
    
    # Verify frontend is being served
    run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/studio/", "Test frontend /studio/")
    run("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/studio/", "Test via HTTPS")
    run("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/download/", "Test download page")
    
    # Final check: nginx reload
    run("nginx -s reload 2>&1 || nginx -t 2>&1", "Nginx reload")
    
    print("\n=== ALL TESTS COMPLETE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
