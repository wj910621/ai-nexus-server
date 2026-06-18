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

# Full header test
stdin, stdout, stderr = ssh.exec_command("curl -s -D - 'https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe' -o /dev/null 2>&1 | head -20")
for line in stdout.read().decode().strip().split('\n'):
    print(f"  {line}")

print("\n=== Key headers ===")
stdin, stdout, stderr = ssh.exec_command("curl -s -D - 'https://j3trisheng.com/download/TriGen-Desktop-1.0.0-win-Setup.exe' -o /dev/null 2>&1 | grep -iE 'content-disposition|content-type|HTTP/'")
print(stdout.read().decode().strip())

ssh.close()
