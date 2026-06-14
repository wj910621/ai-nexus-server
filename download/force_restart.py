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
        if err: print(f"STDERR: {err[:1000]}")
        return out, err
    
    # Step 1: Force kill ALL node processes
    run("killall -9 node 2>/dev/null; sleep 1; echo 'All node processes killed'", "Kill all node processes")
    
    # Step 2: Verify port is free
    run("ss -tlnp | grep 3001 || echo 'Port 3001 is free'", "Verify port 3001 free")
    
    # Step 3: Recreate PM2 and start fresh
    run("pm2 kill 2>&1", "Kill PM2 daemon")
    run("sleep 1", "Wait")
    
    # Step 4: Start
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
    
    import time
    time.sleep(5)
    
    # Step 5: Check status - look for success
    run("pm2 list", "PM2 status")
    result, _ = run("tail -10 /root/.pm2/logs/nexus-hub-error.log 2>/dev/null", "Error log")
    run("tail -10 /root/.pm2/logs/nexus-hub-out.log 2>/dev/null", "Output log")
    
    # Step 6: Test if server is running
    run("curl -s -m 5 http://127.0.0.1:3001/api/admin/auth 2>&1", "Test API")
    run("ss -tlnp | grep 3001", "Check who is on 3001")
    
    run("pm2 save", "PM2 save")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
