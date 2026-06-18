import paramiko
import os
import sys

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

# File to upload
local_file = r"G:\大模型聚合网站\download\release\TriGen-Desktop-1.0.0-win-Setup.exe"
remote_file = "/home/admin/nexus-studio/download/TriGen-Desktop-1.0.0-win-Setup.exe"

# Create SSH client
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("Connecting...")
    ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)
    print("Connected!")
    
    # Ensure remote download directory exists
    stdin, stdout, stderr = ssh.exec_command("mkdir -p /home/admin/nexus-studio/download/")
    stdout.channel.recv_exit_status()
    
    # Upload file via SFTP
    sftp = ssh.open_sftp()
    file_size = os.path.getsize(local_file)
    print(f"Uploading {local_file} ({file_size/1024/1024:.1f} MB)...")
    
    def progress_callback(transferred, total):
        pct = transferred / total * 100
        print(f"\rProgress: {pct:.1f}% ({transferred/1024/1024:.1f}/{total/1024/1024:.1f} MB)", end="")
    
    sftp.put(local_file, remote_file, callback=progress_callback)
    print(f"\nUpload complete!")
    
    # Verify
    stdin, stdout, stderr = ssh.exec_command(f"ls -lh {remote_file}")
    print(stdout.read().decode())
    
    # Also check what else is in the download directory
    stdin, stdout, stderr = ssh.exec_command("ls -lh /home/admin/nexus-studio/download/")
    print("Server /download/ contents:")
    print(stdout.read().decode())
    
    sftp.close()
    print("Done!")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
