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
    if desc: print(f"\n{desc}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:2000])
    if err: print(f"⚠️ {err[:500]}")
    return out, err

# 1. Check why PM2 crashed
run("pm2 logs nexus-hub --lines 20 --nostream 2>&1 | grep -i error", "PM2 crash reason")

# 2. Try installing Node.js 18 via binary using a DIFFERENT mirror
print("\n🔥 RETRYING NODE.JS 18 INSTALL...")
run("""
cd /tmp && \
curl -fsSL "https://nodejs.org/dist/v18.20.4/node-v18.20.4-linux-x64.tar.xz" -o node18.tar.xz 2>&1 && \
echo "Downloaded $(ls -lh node18.tar.xz | awk '{print $5}')" && \
tar -xf node18.tar.xz && \
cp node-v18.20.4-linux-x64/bin/node /usr/local/bin/node && \
cp node-v18.20.4-linux-x64/bin/npm /usr/local/bin/npm && \
cp node-v18.20.4-linux-x64/bin/npx /usr/local/bin/npx && \
rm -rf node-v18.20.4-linux-x64 node18.tar.xz && \
echo "SUCCESS: Node $(node -v)"
""", "Node 18 binary install", timeout=120)

# 3. Check result
ver, _ = run("node -v", "Verify Node")

# 4. If it failed, try another approach
if 'v18' not in ver:
    print("⚠️ Binary download failed, trying npm install n...")
    run("""
npm cache clean -f && \
npm install -g n 2>&1 | tail -3 && \
n 18.20.4 2>&1 | tail -5 && \
hash -r && node -v
""", "Install Node 18 via 'n'", timeout=120)

# 5. Try again
ver, _ = run("node -v", "Final Node check")

# 6. If still on v14, offer alternative
if 'v14' in ver:
    print("\n⚠️ Node 18 install failed. Will fix PM2 with Node 14 compatible server.js instead.")
    # Revert to the previous working state
    run("cd /home/admin/ai-nexus && npm install morgan 2>&1 | tail -3", "Install morgan")
    run("pm2 kill", "Kill PM2")
    import time; time.sleep(2)
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2 with Node 14")
    time.sleep(5)
    run("pm2 list | head -5", "PM2 status")
    run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 150", "API test")
else:
    # Node 18 succeeded - reinstall packages and restart
    print("\n🎉 Node 18 installed! Reinstalling packages...")
    run("cd /home/admin/ai-nexus && npm install 2>&1 | tail -5", "npm install")
    run("pm2 kill", "Kill PM2")
    time.sleep(2)
    run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1", "Start PM2")
    time.sleep(5)
    run("pm2 list | head -5", "PM2 status")
    run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 150", "API test")

# 7. Final save
run("pm2 save", "PM2 save")
run("nginx -s reload 2>&1", "Nginx reload")

print("\n=== DONE ===")
ssh.close()
