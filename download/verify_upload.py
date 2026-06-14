import paramiko
import sys

host = "120.79.17.184"
port = 22
username = "root"
password = "Wangjie910621"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("Connecting...")
    ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
    print("Connected!")
    
    # Run multiple commands
    commands = [
        "echo '=== File check ===' && ls -lh /home/admin/nexus-studio/download/",
        "echo '=== Nginx config ===' && cat /etc/nginx/conf.d/j3trisheng-ssl.conf",
        "echo '=== Nginx HTTP config ===' && cat /etc/nginx/conf.d/j3trisheng.conf",
        "echo '=== PM2 status ===' && pm2 list",
        "echo '=== Server uptime ===' && uptime",
        "echo '=== Disk space ===' && df -h /",
    ]
    
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(out)
        if err:
            print(f"STDERR: {err}")
        print("---")
    
    print("Done!")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
