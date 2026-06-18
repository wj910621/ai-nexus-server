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
    
    def run(cmd):
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(out)
        if err:
            print(f"STDERR: {err}")
        return out, err
    
    # Check PM2 logs for nexus-hub
    print("=== PM2 logs (last 50 lines) ===")
    run("pm2 logs nexus-hub --lines 50 --nostream")
    
    print("=== Checking server.js exists ===")
    run("ls -la /home/admin/ai-nexus/server.js")
    
    print("=== Checking Node.js version ===")
    run("node -v")
    
    print("=== Checking if port 3001 is in use ===")
    run("ss -tlnp | grep 3001")
    
    print("=== Try restarting PM2 ===")
    run("pm2 delete nexus-hub")
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1")
    run("sleep 2 && pm2 list")
    
    print("=== PM2 logs after restart ===")
    run("pm2 logs nexus-hub --lines 30 --nostream")
    
    print("Done!")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
