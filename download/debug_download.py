import paramiko

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!")

def run(cmd, desc=""):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if desc:
        print(f"\n=== {desc} ===")
        if out: print(out[:500])
        if err: print(f"ERR: {err[:200]}")
    return out, err

# Check download file exists and permissions
run("ls -lah /home/admin/nexus-studio/download/", "Download directory contents")

# Check file MIME type detection
run("file /home/admin/nexus-studio/download/TriGen-Desktop-1.0.0-win-Setup.exe", "File type detection")

# Check nginx mime.types for .exe
run("grep -i 'exe' /etc/nginx/mime.types || echo 'No .exe in mime.types'", "Nginx MIME types for exe")

# Test download via HTTP HEAD
run("curl -s -I https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe 2>&1 | head -15", "HTTP headers for download")

# Check nginx error log for any recent issues
run("tail -20 /var/log/nginx/error.log 2>/dev/null || echo 'No nginx error log access'", "Nginx recent errors")

# Verify PM2 is still running
run("pm2 list", "PM2 status")
run("ss -tlnp | grep 3001", "Port 3001 status")

# Check API is responding
run("curl -s -m 3 http://127.0.0.1:3001/api/status 2>&1 | head -c 100", "API status check")

ssh.close()
print("\n=== DONE ===")
