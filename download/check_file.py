import paramiko
import sys

host = "120.79.17.184"
port = 22
username = "root"
password = os.environ.get("DEPLOY_PASS", "CHANGE_ME")

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
        if out: print(out[:3000])
        return out, err
    
    # Check file sizes
    run("ls -lh /home/admin/nexus-studio/index.html /home/admin/nexus-studio/landing.html", "File sizes")
    
    # Check if the file ends properly
    run("tail -5 /home/admin/nexus-studio/index.html", "Last 5 lines of index.html")
    
    # Check the very end of the file
    run("grep -n '</script>\\|</html>' /home/admin/nexus-studio/index.html | tail -5", "Closing tags")
    
    # Check for Service Worker registration
    run("grep -n 'serviceWorker\\|sw.js\\|register' /home/admin/nexus-studio/index.html | head -5", "Service Worker")
    
    # Check for unclosed script tags or issues
    run("grep -c '<script>' /home/admin/nexus-studio/index.html && grep -c '</script>' /home/admin/nexus-studio/index.html", "Script tag count")
    
    print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
finally:
    ssh.close()
