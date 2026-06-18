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

sftp = ssh.open_sftp()

print("\n1/2: Uploading fixed server.js (CORS + morgan)...")
sftp.put(r"G:\大模型聚合网站\server.js", "/home/admin/ai-nexus/server.js")
print("✅ server.js uploaded!")

print("\n2/2: Uploading fixed index.html (online default + password reset fix)...")
sftp.put(r"G:\大模型聚合网站\index.html", "/home/admin/nexus-studio/index.html")
print("✅ index.html uploaded!")

sftp.close()

# Now run the big deploy_all script for server changes
print("\n\n🎯 Now running server-side optimizations (Node upgrade, HTTP redirect, ZIP, restart)...")
ssh.close()

import subprocess, sys
result = subprocess.run([
    sys.executable, "G:/大模型聚合网站/download/deploy_all.py"
], capture_output=True, text=True, timeout=300)
print(result.stdout[-3000:])
if result.stderr:
    print(f"STDERR: {result.stderr[-500:]}")
