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
    if desc: print(f"🔧 {desc}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:1500])
    if err: print(f"⚠️ {err[:300]}")
    return out

# Step 1: Kill PM2 first
run("pm2 kill", "1. Kill PM2")

# Step 2: Install morgan (for current Node 14)
print("\n🔥 Step 2: Install morgan")
run("cd /home/admin/ai-nexus && npm install morgan 2>&1 | tail -3")

# Step 3: Restart PM2 with Node 14 (get server back online ASAP)
print("\n🔥 Step 3: Restart PM2")
run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1")
time.sleep(5)
run("pm2 list | head -5")
run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 100")

# Step 4: Try Node.js 18 install via a different method
print("\n🔥 Step 4: Install Node.js 18 via nvm-style approach")
run("""
# First try the official download
curl -fsSL --connect-timeout 10 "https://nodejs.org/dist/v18.20.4/node-v18.20.4-linux-x64.tar.xz" -o /tmp/node18.tar.xz 2>&1 && \
echo "Download OK: $(ls -lh /tmp/node18.tar.xz | awk '{print $5}')" || \
echo "Official mirror failed"
""", "Try official Node 18 download")

# Check if we got it
stdin, stdout, stderr = ssh.exec_command("ls -lh /tmp/node18.tar.xz 2>/dev/null | awk '{print $5}'")
size = stdout.read().decode().strip()
print(f"  File size: {size or 'NOT FOUND'}")

if size:
    # Extract and install
    run("""
tar -xf /tmp/node18.tar.xz -C /tmp && \
cp /tmp/node-v18.20.4-linux-x64/bin/node /usr/local/bin/node && \
cp /tmp/node-v18.20.4-linux-x64/bin/npm /usr/local/bin/npm && \
cp /tmp/node-v18.20.4-linux-x64/bin/npx /usr/local/bin/npx && \
rm -rf /tmp/node-v18.20.4-linux-x64 /tmp/node18.tar.xz && \
echo "Node 18 INSTALLED: $(node -v)"
""", "Extract and install Node 18")
else:
    print("⚠️ Node 18 download failed. Server will continue with Node 14.")

# Step 5: Save PM2 config
run("pm2 save", "5. PM2 save")

print("\n" + "="*60)
print("✅ ALL FIXES APPLIED")
run("node -v", "Node version")
run("pm2 list | head -5", "PM2 status")
run("curl -s -m 5 https://j3trisheng.com/api/status 2>&1 | head -c 150", "API via HTTPS")

ssh.close()
