import paramiko

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...")
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
print("Connected!")

sftp = ssh.open_sftp()
print("Uploading final index.html...")
sftp.put(r"G:\大模型聚合网站\index.html", "/home/admin/nexus-studio/index.html")
print("Done!")

ssh.exec_command("nginx -s reload")
print("Nginx reloaded")
sftp.close()
ssh.close()
print("=== ALL DONE ===")
