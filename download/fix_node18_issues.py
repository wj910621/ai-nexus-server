import paramiko, time

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!\n")

def run(cmd, desc=""):
    if desc: print(f"  {desc}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f"    {out[:1500]}")
    if err: print(f"    ⚠️ {err[:300]}")
    return out, err

# Step 1: Fix nginx duplicate default server
print("🔥 Step 1: Fix nginx config")
# Remove the backup file
run("rm -f /etc/nginx/conf.d/j3trisheng-http-old.conf.bak", "Remove duplicate nginx config")
# Check remaining configs
run("ls /etc/nginx/conf.d/", "Nginx configs list")

# Step 2: Test and reload nginx
_, err = run("nginx -t 2>&1", "Test nginx")
if "emerg" not in err:
    run("nginx -s reload 2>&1", "Reload nginx")
else:
    print("    ❌ Nginx config error - checking...")
    # Fix: rename the redirect config
    run("""
cat > /etc/nginx/conf.d/j3trisheng-http-redirect.conf << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name j3trisheng.com www.j3trisheng.com;
    return 301 https://$server_name$request_uri;
}
EOF
""", "Rewrite redirect config without default_server")
    run("rm -f /etc/nginx/conf.d/j3trisheng.http.conf.bak /etc/nginx/conf.d/j3trisheng-http-old.conf.bak", "Cleanup")
    run("nginx -t 2>&1", "Test nginx again")
    run("nginx -s reload 2>&1", "Reload nginx")

# Step 3: Fix sql.js for Node 18
print("\n🔥 Step 3: Fix sql.js for Node 18")
run("cd /home/admin/ai-nexus && npm install sql.js@1.11.0 2>&1 | tail -5", "Install sql.js 1.11.0 for Node 18")

# Step 4: Fix the sql.js wasm URL issue in server.js
# The issue is that sql.js tries to fetch wasm as a URL from file path
run("""
cd /home/admin/ai-nexus && \
grep -q 'initSqlJs' server.js || echo 'no initSqlJs' && \
grep -q 'locateFile' server.js && \
echo 'Need to check server.js sql init'
""", "Check sql.js initialization")

# Step 5: Kill and restart PM2
print("\n🔥 Step 4: Restart PM2")
run("pm2 kill", "Kill PM2")
time.sleep(2)
run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
time.sleep(8)

# Step 6: Verify
run("pm2 list | head -5", "PM2 status")
out, err = run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 200", "API test")
if "status" in out and "ok" in out:
    print("    ✅ API SUCCESS!")
    run("curl -s -m 5 https://j3trisheng.com/api/status 2>&1 | head -c 200", "API via HTTPS")
    run("pm2 save", "Save PM2")
else:
    # Check the error
    run("tail -20 /root/.pm2/logs/nexus-hub-error.log 2>/dev/null", "Error log")
    # Fallback: install sql.js 1.7.x which is more compatible
    print("    ⚠️ Trying sql.js@1.10.0 instead...")
    run("pm2 kill", "Kill PM2")
    run("cd /home/admin/ai-nexus && npm install sql.js@1.10.0 2>&1 | tail -3", "Install 1.10.0")
    time.sleep(2)
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
    time.sleep(8)
    run("pm2 list | head -5", "PM2 status")
    out2, _ = run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 200", "API test retry")
    if "status" in out2 and "ok" in out2:
        print("    ✅ API SUCCESS!")
        run("pm2 save", "Save PM2")

print("\n=== DONE ===")
ssh.close()
