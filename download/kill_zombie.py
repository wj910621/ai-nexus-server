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
    
    # Step 1: Find the zombie PID holding port 3001
    run("ss -tlnp | grep 3001", "Current port 3001 holder")
    
    # Step 2: Kill it explicitly with SIGKILL
    run("kill -9 45281 2>/dev/null; sleep 1", "Kill zombie pid 45281")
    
    # Step 3: Check if port is free now
    run("ss -tlnp | grep 3001 || echo 'PORT 3001 IS FREE!'", "Verify port free")
    
    # Step 4: Kill all remaining node
    run("ps aux | grep node | grep -v grep | awk '{print $2}' | while read pid; do kill -9 $pid 2>/dev/null; done; sleep 1", "Kill all remaining node processes")
    
    # Step 5: Verify
    run("ps aux | grep node | grep -v grep || echo 'No node processes'", "Verify no node processes")
    run("ss -tlnp | grep 3001 || echo 'PORT 3001 IS FREE!'", "Verify port 3001 free again")
    
    # Step 6: Kill PM2 daemon
    run("pm2 kill 2>&1; sleep 1", "Kill PM2 daemon")
    
    # Step 7: Start fresh
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2 fresh")
    
    import time
    time.sleep(3)
    
    run("pm2 list", "PM2 status")
    run("tail -5 /root/.pm2/logs/nexus-hub-error.log 2>/dev/null", "Error log")
    run("tail -5 /root/.pm2/logs/nexus-hub-out.log 2>/dev/null", "Output log")
    
    # Test API
    run("curl -s -m 5 http://127.0.0.1:3001/api/admin/auth 2>&1", "Test API")
    run("ss -tlnp | grep 3001 || echo 'Nothing on 3001!'", "Final port check")
    
    run("pm2 save", "PM2 save")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
