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
        if out: print(out[:3000])
        if err: print(f"STDERR: {err[:1000]}")
        return out, err
    
    # Step 1: Check backend status
    run("pm2 list", "Check PM2 status")
    run("ss -tlnp | grep 3001", "Check port 3001")
    
    # Step 2: If backend is down, restart it
    run("""
if ! ss -tlnp | grep -q ':3001'; then
    echo "Port 3001 not listening, restarting..."
    pm2 restart nexus-hub
else
    echo "Port 3001 is active"
fi
""", "Restart backend if needed")
    
    import time
    time.sleep(2)
    
    # Step 3: Test backend API
    run("curl -s -m 3 -X POST http://127.0.0.1:3001/api/guest/sync -H 'Content-Type: application/json' -d '{\"fingerprint\":\"test\",\"ip\":\"1.1.1.1\"}' 2>&1", "Test backend API")
    
    # Step 4: Fix nginx config for download directory
    # The issue is autoindex is showing instead of index.html
    nginx_config = """
server {
    listen 443 ssl http2;
    server_name j3trisheng.com www.j3trisheng.com;

    ssl_certificate /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 欢迎页 - 根路径
    root /home/admin/nexus-studio/;
    index landing.html;

    location / {
        try_files /landing.html =404;
    }

    # Nexus Studio PWA 前端
    location = /studio { return 301 /studio/; }

    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        try_files $uri $uri/ /index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # 下载目录 - 优先显示 index.html，没有才显示目录列表
    location = /download { return 301 /download/; }

    location /download/ {
        alias /home/admin/nexus-studio/download/;
        index index.html;
        try_files $uri $uri/ =404;
        # 只在请求 /download/ 且没有 index.html 时才显示目录
        autoindex off;
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_connect_timeout 5s;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 120s;
        proxy_connect_timeout 5s;
    }

    # 静态资源
    location /css/ { }
    location /js/ { }
    location /icons/ { }
}
"""
    print("\n=== Updating nginx SSL config ===")
    stdin, stdout, stderr = ssh.exec_command("cat > /etc/nginx/conf.d/j3trisheng-ssl.conf")
    stdin.write(nginx_config)
    stdin.channel.shutdown_write()
    exit_status = stdout.channel.recv_exit_status()
    print("SSL config updated!" if exit_status == 0 else "Failed")
    
    # Also update HTTP config
    http_config = """
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name j3trisheng.com www.j3trisheng.com _;

    root /home/admin/nexus-studio/;
    index landing.html;

    # 欢迎页
    location = / {
        try_files /landing.html =404;
    }

    # /studio/ → TriGen Desktop
    location = /studio { return 301 /studio/; }

    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 下载目录 - 优先 index.html
    location = /download { return 301 /download/; }

    location /download/ {
        alias /home/admin/nexus-studio/download/;
        index index.html;
        try_files $uri $uri/ =404;
        autoindex off;
    }

    # 静态资源
    location /css/ { }
    location /js/ { }
    location /icons/ { }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_connect_timeout 5s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_connect_timeout 5s;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # 主站 SPA 路由
    location / {
        try_files $uri $uri/ /landing.html;
    }
}
"""
    print("\n=== Updating nginx HTTP config ===")
    stdin, stdout, stderr = ssh.exec_command("cat > /etc/nginx/conf.d/j3trisheng.conf")
    stdin.write(http_config)
    stdin.channel.shutdown_write()
    exit_status = stdout.channel.recv_exit_status()
    print("HTTP config updated!" if exit_status == 0 else "Failed")
    
    # Test nginx config
    run("nginx -t 2>&1", "Test nginx config")
    
    # Reload nginx
    run("nginx -s reload 2>&1", "Reload nginx")
    
    # Verify download/index.html exists
    run("cat /home/admin/nexus-studio/download/index.html | head -10", "Verify download/index.html")
    
    print("\n=== ALL FIXED ===")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
