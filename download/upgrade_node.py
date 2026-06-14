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
    
    def run(cmd, desc=""):
        if desc: print(f"\n=== {desc} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out: print(out[:3000])
        if err: print(f"STDERR: {err[:1000]}")
        return out, err
    
    # Step 1: Remove old nodejs and install Node 18 LTS
    print("\n=== Step 1: Install Node.js 18 LTS via NodeSource ===")
    run("""
curl -fsSL https://rpm.nodesource.com/setup_18.x -o /tmp/nodesetup.sh && \
bash /tmp/nodesetup.sh 2>&1 && \
yum install -y nodejs 2>&1
""", "Install Node 18 LTS")
    
    run("node -v", "Verify Node version")
    run("npm -v", "Verify npm version")
    
    # Step 2: Kill old PM2 and restart
    run("pm2 kill", "Kill PM2")
    
    # Step 3: Reinstall npm packages with new Node
    run("cd /home/admin/ai-nexus && npm install 2>&1", "Reinstall npm packages")
    
    # Step 4: Start PM2 fresh
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
    
    import time
    time.sleep(5)
    
    # Step 5: Check status
    run("pm2 list", "PM2 status")
    run("tail -20 /root/.pm2/logs/nexus-hub-error.log 2>/dev/null", "Error log")
    run("tail -10 /root/.pm2/logs/nexus-hub-out.log 2>/dev/null", "Output log")
    
    # Step 6: Test API
    run("curl -s http://127.0.0.1:3001/api/health 2>&1 || echo 'no /api/health'", "Test /api/health")
    run("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/api/admin/auth 2>&1", "Test /api/admin/auth")
    
    # Step 7: PM2 save
    run("pm2 save", "PM2 save")
    
    # Step 8: Verify Nginx reload
    run("nginx -t 2>&1", "Test nginx config")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
