# Nexus AI Studio - 从零部署指南

## 发布包内容

```
nexus-release/
├── server.js        # 后端 Express 服务 (2523行，已语法验证)
├── package.json     # 依赖配置 (Node >=18)
├── .env             # 环境变量 + API Key
├── index.html       # 前端独立版 (所有JS在一个作用域，6926行)
├── sw.js            # Service Worker
├── manifest.json    # PWA 清单
└── css/style.css    # 样式
```

## 第一步：服务器重置（回到未部署状态）

> 如果你之前的部署有残留，需要清除干净

### 通过 SSH 连接服务器
```bash
ssh root@120.79.17.184
```

### 1. 停止所有服务
```bash
# 停止 PM2
pm2 delete nexus-hub 2>/dev/null
pm2 delete ai-nexus 2>/dev/null

# 杀掉所有 node 进程
pkill -f "node server.js" 2>/dev/null

# 停止 Nginx（暂时）
systemctl stop nginx
```

### 2. 清理旧文件
```bash
# 删除项目目录
rm -rf /home/admin/ai-nexus
rm -rf /home/admin/nexus-studio

# 确认删除干净
ls -la /home/admin/ | grep -E "ai-nexus|nexus-studio"
```

### 3. 清理 Nginx 配置（可选）
```bash
rm -f /etc/nginx/conf.d/j3trisheng.conf
rm -f /etc/nginx/conf.d/ai-nexus.conf
rm -f /etc/nginx/conf.d/j3trisheng.conf.bak
rm -f /etc/nginx/conf.d/j3trisheng-v2.conf
```

### 4. 重设 NVM（可选，如果已有 Node 18 则跳过）
```bash
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# 安装 Node 18
nvm install 18
nvm use 18
nvm alias default 18
```

---

## 第二步：上传文件

### 方法 A：使用 FTP/SCP 工具（推荐）
把 `nexus-release/` 目录下的所有文件上传到服务器：
- `server.js` → `/home/admin/ai-nexus/server.js`
- `package.json` → `/home/admin/ai-nexus/package.json`
- `.env` → `/home/admin/ai-nexus/.env`
- `index.html` → `/home/admin/nexus-studio/index.html`
- `sw.js` → `/home/admin/nexus-studio/sw.js`
- `manifest.json` → `/home/admin/nexus-studio/manifest.json`
- `css/style.css` → `/home/admin/nexus-studio/css/style.css`

```bash
mkdir -p /home/admin/ai-nexus /home/admin/nexus-studio/css
```

### 方法 B：使用 deploy.js（自动上传）
```bash
# 在本机执行（需要 Node.js）
node deploy.js
```

---

## 第三步：安装依赖 & 启动后端

```bash
# 登录服务器
ssh root@120.79.17.184

# 进入项目目录
cd /home/admin/ai-nexus

# 安装依赖（必须使用 Node 18）
source ~/.nvm/nvm.sh
nvm use 18
npm install

# 启动服务（使用 PM2）
PORT=3001 pm2 start server.js --name nexus-hub --interpreter $(which node)

# 保存 PM2 配置并设置开机自启
pm2 save
pm2 startup systemd

# 验证 API 是否正常
curl http://localhost:3001/api/status
```

正常返回 JSON（包含 135+ 模型列表）即为成功。

---

## 第四步：配置 Nginx

### 创建配置文件
```bash
cat > /etc/nginx/conf.d/nexus.conf << 'EOF'
server {
    listen 80;
    server_name j3trisheng.com www.j3trisheng.com;

    # 前端静态文件
    location /studio/ {
        alias /home/admin/nexus-studio/;
        index index.html;
        expires 0;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        proxy_cache off;
    }

    # 根路径重定向到 /studio/
    location = / {
        return 302 /studio/;
    }

    # 其他请求交给后端
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }
}
EOF

# 测试配置
nginx -t

# 重载 Nginx
systemctl reload nginx
```

---

## 第五步：Cloudflare DNS 配置

### 1. 登录 Cloudflare
访问 https://dash.cloudflare.com

### 2. 选择 j3trisheng.com

### 3. DNS → 添加记录
| 类型 | 名称 | 值 | 代理状态 |
|------|------|-----|---------|
| A | `www` | `120.79.17.184` | 橙色云朵 ✅ |
| A | `@` | `120.79.17.184` | 橙色云朵 ✅ |

### 4. SSL/TLS → 选择 Full
- 左侧菜单 SSL/TLS
- Overview 页面 → 选择 **Full**（非 Flexible）
- 边缘证书 → 可以自动生成

### 5. 缓存 → 清除所有缓存

### 6. 验证
访问 `https://www.j3trisheng.com/studio/`

---

## 验证清单

- [ ] `curl http://localhost:3001/api/status` 返回 JSON
- [ ] `http://120.79.17.184:3001/studio/` 页面加载成功
- [ ] `https://www.j3trisheng.com/studio/` 能访问
- [ ] 控制台无 `init is not defined` 错误
- [ ] 可以发送聊天消息

## 常见问题

### Q: 页面卡 Loading
→ 打开浏览器 DevTools → 清除 Service Worker：Application → Service Workers → Unregister
→ 清除所有缓存：Application → Storage → Clear site data
→ Ctrl+F5 强制刷新

### Q: API Key 未配置
→ 检查 `/home/admin/ai-nexus/.env` 文件
→ 注意 `.env` 中仍有 14 个 `your-*-here` 占位符需要你补全
→ 修改后执行 `pm2 restart nexus-hub`

### Q: PM2 启动失败
```bash
pm2 logs nexus-hub    # 查看错误日志
pm2 restart nexus-hub # 重启
```
