import paramiko

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!\n")

sftp = ssh.open_sftp()

print("✅ Uploading index.html (modelCount 72→360, fetchDynamic fix)...")
sftp.put(r"G:\大模型聚合网站\index.html", "/home/admin/nexus-studio/index.html")

print("✅ Uploading landing.html (links fix)...")
sftp.put(r"G:\大模型聚合网站\landing.html", "/home/admin/nexus-studio/landing.html")

sftp.close()

# Check trigen.ai DNS
stdin, stdout, stderr = ssh.exec_command("nslookup trigen.ai 2>&1 | head -10")
print("\n🔍 trigen.ai DNS:")
print(stdout.read().decode().strip()[:500])

# Check /api/bailian-models, /api/siliconflow-models, /api/openrouter-models
stdin, stdout, stderr = ssh.exec_command("curl -s -m 5 http://127.0.0.1:3001/api/bailian-models 2>&1 | head -c 100")
print("\n🔍 bailian models API:", stdout.read().decode().strip()[:100] or "no response")

stdin, stdout, stderr = ssh.exec_command("curl -s -m 5 http://127.0.0.1:3001/api/siliconflow-models 2>&1 | head -c 100")
print("🔍 siliconflow models API:", stdout.read().decode().strip()[:100] or "no response")

stdin, stdout, stderr = ssh.exec_command("curl -s -m 5 http://127.0.0.1:3001/api/openrouter-models 2>&1 | head -c 100")
print("🔍 openrouter models API:", stdout.read().decode().strip()[:100] or "no response")

# Reload nginx
stdin, stdout, stderr = ssh.exec_command("nginx -s reload 2>&1")
print("\n✅ Nginx reloaded")

ssh.close()
print("\n=== DONE ===")
