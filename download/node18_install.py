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
    if out: print(f"    {out[:2000]}")
    if err: print(f"    ⚠️ {err[:300]}")
    return out

# Step 1: Kill PM2
print("🔥 Step 1: Stop services")
run("pm2 kill")
time.sleep(2)

# Step 2: Copy Node 18 binaries  
print("\n🔥 Step 2: Install Node 18 binaries")
run("""
cp /tmp/node-v18.20.4-linux-x64/bin/node /usr/local/bin/node && \
cp /tmp/node-v18.20.4-linux-x64/bin/npm /usr/local/bin/npm && \
cp /tmp/node-v18.20.4-linux-x64/bin/npx /usr/local/bin/npx && \
echo "Node 18 INSTALLED: $(/usr/local/bin/node -v)"
""")

# Step 3: Clean up temp
run("rm -rf /tmp/node-v18.20.4-linux-x64 /tmp/node18.tar.xz 2>/dev/null; echo 'cleaned'")

# Step 4: Verify
print("\n🔥 Step 4: Verify Node version")
run("hash -r && node -v", "")

# Step 5: Reinstall packages with Node 18
print("\n🔥 Step 5: Reinstall packages")
run("cd /home/admin/ai-nexus && npm install 2>&1 | tail -5")

# Step 6: Start PM2
print("\n🔥 Step 6: Start PM2 with Node 18")
run("cd /home/admin/ai-nexus && pm2 start server.js --name nexus-hub 2>&1")
time.sleep(5)
run("pm2 list")

# Step 7: Verify API
print("\n🔥 Step 7: Verify API")
run("curl -s -m 5 http://127.0.0.1:3001/api/status 2>&1 | head -c 150")
run("pm2 save", "PM2 save")

print("\n" + "="*60)
print("✅ ALL DONE!")
ssh.close()
