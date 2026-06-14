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
        if err: print(f"STDERR: {err[:500]}")
        return out, err
    
    # Get the full API_BASE function
    run("grep -oP 'const API_BASE=\(\)=>\{[^}]*\}' /home/admin/nexus-studio/index.html", "Full API_BASE definition")
    
    # Also get the window.API_BASE if exists
    run("grep -oP 'window\.API_BASE[^;]*' /home/admin/nexus-studio/index.html | head -5", "window.API_BASE")
    
    # Check for "loading" or blocking code  
    run("grep -oP '检测中|loading.*true|while\(|spin|showLoading' /home/admin/nexus-studio/index.html | head -20", "Loading patterns")
    
    # Check the credits init code
    run("grep -oP 'initCredits|init.*credit|loadModel|initModel' /home/admin/nexus-studio/index.html | head -10", "Init functions")
    
print("\n=== DONE ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
