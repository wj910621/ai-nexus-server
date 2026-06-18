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
    
    def run(cmd, desc=""):
        if desc: print(f"\n=== {desc} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out: print(out[:2000])
        if err: print(f"STDERR: {err[:500]}")
        return out, err
    
    # Kill old process on port 3001
    run("kill -9 42604 2>/dev/null; echo 'killed old process'", "Kill old process on 3001")
    
    # Kill all PM2 processes
    run("pm2 kill", "Kill all PM2")
    
    # Check port is free
    run("ss -tlnp | grep 3001 || echo 'Port 3001 is free'", "Check port 3001")
    
    # Delete old PM2 logs 
    run("pm2 flush", "Flush PM2 logs")
    
    # Start fresh
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2 fresh")
    
    import time
    time.sleep(5)
    
    # Check status
    run("pm2 list", "PM2 status")
    
    # Check error log
    run("tail -20 /root/.pm2/logs/nexus-hub-error.log 2>/dev/null", "Error log")
    
    # Check out log
    run("tail -30 /root/.pm2/logs/nexus-hub-out.log 2>/dev/null", "Output log")
    
    # Test API
    run("curl -s http://127.0.0.1:3001/api/health 2>&1 || curl -s http://127.0.0.1:3001/ 2>&1", "Test API")
    
    # PM2 save
    run("pm2 save", "PM2 save")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
