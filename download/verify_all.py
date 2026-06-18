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

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:3000])
    return out

# 1. Check the deployed index.html has the AbortController fix
print("=== Check AbortController in deployed index.html ===")
run("grep -c 'AbortController' /home/admin/nexus-studio/index.html")
run("grep 'AbortController' /home/admin/nexus-studio/index.html | head -2")

# 2. Check Service Worker fix
print("\n=== Check Service Worker fix ===")
run("grep 'register.*blob' /home/admin/nexus-studio/index.html || echo 'NO blob SW registration (GOOD!)'")
run("grep 'unregister' /home/admin/nexus-studio/index.html")

# 3. Check model count in HTML
print("\n=== Model count stat ===")
run("grep -oP 'modelCount\">\\d+' /home/admin/nexus-studio/index.html")

# 4. Verify nginx proxy is working
print("\n=== Test full HTTPS chain ===")
run("curl -s -m 5 -I https://j3trisheng.com/studio/ 2>&1 | head -20")

# 5. Test API through full HTTPS
print("\n=== Test /api/status via HTTPS ===")
run("curl -s -m 5 https://j3trisheng.com/api/status 2>&1 | head -c 200")

# 6. Also test from a non-cached perspective
print("\n=== PM2 status ===")
run("pm2 list | head -5")

# 7. Check if we need to reload nginx for the new config
print("\n=== Nginx restart ===")
run("nginx -t 2>&1 && nginx -s reload 2>&1")

ssh.close()
print("\n=== DONE ===")
