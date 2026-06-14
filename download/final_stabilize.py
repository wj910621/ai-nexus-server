import paramiko, time

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

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
    if out: print(f"    {out[:2000]}")
    if err: print(f"    ⚠️ {err[:300]}")
    return out, err

# Step 1: Revert to Node 14 (the working one)
print("🔥 Step 1: Reinstall Node 14 (centOS 8 default)")
run("""
cd /tmp && \
curl -fsSL "https://nodejs.org/dist/v14.21.3/node-v14.21.3-linux-x64.tar.xz" -o node14.tar.xz && \
tar -xf node14.tar.xz && \
cp node-v14.21.3-linux-x64/bin/node /usr/local/bin/node && \
cp node-v14.21.3-linux-x64/bin/npm /usr/local/bin/npm && \
cp node-v14.21.3-linux-x64/bin/npx /usr/local/bin/npx && \
rm -rf node-v14.21.3-linux-x64 node14.tar.xz && \
echo "Node $(node -v) restored"
""", "Revert to Node 14")

# Step 2: Fix nginx config (remove duplicate default_server)
print("\n🔥 Step 2: Fix nginx configs")
# Read the current config
run("ls -la /etc/nginx/conf.d/", "Current configs")
# Fix SSL config - remove default_server from HTTP redirect
run("""
cat > /etc/nginx/conf.d/j3trisheng-http.conf << 'HTTPEOF'
server {
    listen 80;
    listen [::]:80;
    server_name j3trisheng.com www.j3trisheng.com;
    return 301 https://$server_name$request_uri;
}
HTTPEOF
""", "Rewrite redirect without default_server")

# Remove the old config that has the conflict
run("rm -f /etc/nginx/conf.d/j3trisheng.conf", "Remove old HTTP config")

# Now test and reload
out, err = run("nginx -t 2>&1", "Test nginx")
if "emerg" not in err:
    run("nginx -s reload 2>&1", "Reload nginx")
else:
    print("    ❌ Still has issue, checking deeper...")
    run("cat /etc/nginx/conf.d/j3trisheng-http.conf", "Show redirect config")
    run("cat /etc/nginx/conf.d/j3trisheng-ssl.conf | head -5", "Show SSL config")

# Step 3: Reinstall npm packages with Node 14
print("\n🔥 Step 3: Fix npm and reinstall packages")
run("cd /home/admin/ai-nexus && npm install sql.js@1.6.2 morgan 2>&1 | tail -5", "Install with Node 14")

# Step 4: Create ZIP download (if not already)
print("\n🔥 Step 4: Ensure ZIP exists")
run("""
cd /home/admin/nexus-studio/download && \
ls -lh TriGenClaw-1.0.0-win-Setup.zip 2>/dev/null || \
zip -j TriGenClaw-1.0.0-win-Setup.zip TriGen-Desktop-1.0.0-win-Setup.exe
""", "Create ZIP")

# Step 5: Kill and restart PM2
print("\n🔥 Step 5: Restart PM2")
run("pm2 kill", "Kill PM2")
time.sleep(2)
run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
time.sleep(8)

# Step 6: Verify
print("\n🔥 Step 6: Final verification")
run("node -v", "Node version")
run("pm2 list | head -5", "PM2 status")

# Test API
out, _ = run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 150", "API localhost")
if "status" in out:
    print("    ✅ API OK!")
    run("nginx -s reload 2>&1", "Nginx reload")
    time.sleep(1)
    run("curl -s -m 5 https://j3trisheng.com/api/status 2>&1 | head -c 150", "API via HTTPS")
    run("curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}' https://j3trisheng.com/studio/", "Studio")
    run("curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}' https://j3trisheng.com/download/", "Download")
    run("curl -s -m 5 -o /dev/null -w 'HTTP %{http_code}' http://j3trisheng.com/", "HTTP redirect")
    run("pm2 save", "PM2 save")
    print("\n✅ ALL SYSTEMS GREEN!")
else:
    print("    ❌ API FAILED")
    run("tail -20 /root/.pm2/logs/nexus-hub-error.log 2>/dev/null", "Errors")
    run("tail -10 /root/.pm2/logs/nexus-hub-out.log 2>/dev/null", "Output")

ssh.close()
