import paramiko

host = '120.79.17.184'
port = 22
username = 'root'
password = 'Wangjie910621'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, port, username, password, look_for_keys=False, allow_agent=False)

print('✅ Connected')

def run(cmd, timeout=10):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[:1500])
    return out

# Step 1: Update nginx SSL config - add /app/ location BEFORE /studio/
print('\n=== Step 1: Update nginx SSL config ===')
ssl_config = open('/etc/nginx/conf.d/j3trisheng-ssl.conf').read() if False else None

# Read current config
stdin, stdout, stderr = ssh.exec_command('cat /etc/nginx/conf.d/j3trisheng-ssl.conf')
current = stdout.read().decode()

# Add /app/ location after the root location block
new_config = current.replace(
    '    location /studio/ {\n        alias /home/admin/nexus-studio/;\n        index index.html;\n        try_files $uri $uri/ /index.html;\n        expires 0;\n        add_header Cache-Control "no-cache, no-store, must-revalidate";\n    }',
    '    # /app/ 入口（全新路径，绕过旧 Service Worker 缓存）\n    location = /app { return 301 /app/; }\n\n    location /app/ {\n        alias /home/admin/nexus-studio/;\n        index index.html;\n        try_files $uri $uri/ /index.html;\n        expires 0;\n        add_header Cache-Control "no-cache, no-store, must-revalidate";\n    }\n\n    location /studio/ {\n        alias /home/admin/nexus-studio/;\n        index index.html;\n        try_files $uri $uri/ /index.html;\n        expires 0;\n        add_header Cache-Control "no-cache, no-store, must-revalidate";\n        # 301 跳转到新路径绕过 Service Worker 缓存\n        return 301 /app/;\n    }'
)

stdin, stdout, stderr = ssh.exec_command('cat > /etc/nginx/conf.d/j3trisheng-ssl.conf')
stdin.write(new_config)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()
print('✅ SSL config updated')

# Also update HTTP config
stdin, stdout, stderr = ssh.exec_command('cat /etc/nginx/conf.d/j3trisheng-http.conf')
current_http = stdout.read().decode()

new_http = current_http.replace(
    '    location = /studio { return 301 /studio/; }\n    location /studio/ {',
    '    location = /studio { return 301 /app/; }\n    location = /app { return 301 /app/; }\n    location /app/ {\n        alias /home/admin/nexus-studio/;\n        index index.html;\n        try_files $uri $uri/ /index.html;\n    }\n\n    location /studio/ {\n        return 301 /app/;\n    }\n    location /studio {'
)

stdin, stdout, stderr = ssh.exec_command('cat > /etc/nginx/conf.d/j3trisheng-http.conf')
stdin.write(new_http)
stdin.channel.shutdown_write()
_ = stdout.channel.recv_exit_status()
print('✅ HTTP config updated')

# Test and reload
run('nginx -t 2>&1', 10)
run('nginx -s reload 2>&1', 10)

# Test the new /app/ path
run('curl -s -o /dev/null -w "HTTP %{http_code}" https://j3trisheng.com/app/', 10)
print()
run('curl -s -o /dev/null -w "HTTP %{http_code}" https://j3trisheng.com/studio/', 10)
print()

ssh.close()
print('\n=== DONE ===')
