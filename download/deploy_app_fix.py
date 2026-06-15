import paramiko

host = '120.79.17.184'
port = 22
username = 'root'
password = 'Wangjie910621'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)

print('✅ Connected')

sftp = ssh.open_sftp()

# Upload updated files
sftp.put(r'G:\大模型聚合网站\index.html', '/home/admin/nexus-studio/index.html')
sftp.put(r'G:\大模型聚合网站\landing.html', '/home/admin/nexus-studio/landing.html')
print('✅ index.html & landing.html uploaded')

sftp.close()

# Update download page to link to /app/
stdin, stdout, stderr = ssh.exec_command("sed -i 's|/studio/|/app/|g' /home/admin/nexus-studio/download/index.html")
_ = stdout.channel.recv_exit_status()
print('✅ download page updated')

# Test
stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/app/")
print(f'✅ /app/ returns HTTP {stdout.read().decode().strip()}')

stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' https://j3trisheng.com/studio/")
print(f'✅ /studio/ redirects HTTP {stdout.read().decode().strip()}')

ssh.close()
print('\n=== DONE - 请从 https://j3trisheng.com/app/ 进入主站 ===')
