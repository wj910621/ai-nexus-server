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
    
    def run(cmd, desc="", timeout=30):
        if desc: print(f"\n=== {desc} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out: print(out[:5000])
        return out, err
    
    # Get API_BASE using grep without escape issues
    run("sed -n '3090,3105p' /home/admin/nexus-studio/index.html", "API_BASE definition (lines 3090-3105)")
    
    # Check for main init sequence
    run("grep -n 'initCredits\\|initModels\\|showLoading\\|检测中\\|checkStatus' /home/admin/nexus-studio/index.html | head -15", "Init sequence")
    
    # Check status checker function  
    run("grep -n 'online\\|offline\\|检查连接' /home/admin/nexus-studio/index.html | head -10", "Online/offline check")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
