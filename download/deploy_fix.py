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
    
    sftp = ssh.open_sftp()
    
    # Step 1: Upload fixed server.js
    print("\n=== Uploading fixed server.js ===")
    sftp.put(r"G:\大模型聚合网站\server.js", "/home/admin/ai-nexus/server.js")
    print("server.js uploaded!")
    
    # Step 2: Upload .env
    print("\n=== Uploading .env ===")
    sftp.put(r"G:\大模型聚合网站\.env", "/home/admin/ai-nexus/.env")
    print(".env uploaded!")
    
    # Step 3: Also remove the problematic express-rate-limit package
    print("\n=== Removing express-rate-limit ===")
    stdin, stdout, stderr = ssh.exec_command("cd /home/admin/ai-nexus && npm uninstall express-rate-limit 2>&1")
    print(stdout.read().decode().strip())
    err = stderr.read().decode().strip()
    if err:
        print(f"STDERR: {err}")
    
    # Step 4: Restart PM2
    print("\n=== Restarting PM2 ===")
    stdin, stdout, stderr = ssh.exec_command("pm2 delete nexus-hub 2>&1")
    print(stdout.read().decode().strip())
    
    stdin, stdout, stderr = ssh.exec_command("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1")
    print(stdout.read().decode().strip())
    
    import time
    time.sleep(3)
    
    # Step 5: Check status
    print("\n=== PM2 status ===")
    stdin, stdout, stderr = ssh.exec_command("pm2 list")
    print(stdout.read().decode().strip())
    
    # Step 6: Check logs for errors
    print("\n=== Recent error logs ===")
    stdin, stdout, stderr = ssh.exec_command("pm2 logs nexus-hub --lines 10 --nostream 2>&1 | grep -E 'Error|启动成功|数据库已就绪|listening|3001' | head -5")
    print(stdout.read().decode().strip())
    
    # Step 7: Test API
    print("\n=== Testing API /api/admin/auth ===")
    stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/api/admin/auth")
    print(f"HTTP status: {stdout.read().decode().strip()}")
    
    # Step 8: Check running processes listening on 3001
    print("\n=== Processes on port 3001 ===")
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 3001")
    print(stdout.read().decode().strip())
    
    # Step 9: PM2 save
    print("\n=== PM2 save ===")
    stdin, stdout, stderr = ssh.exec_command("pm2 save")
    print(stdout.read().decode().strip())
    
    sftp.close()
    print("\n=== ALL DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
