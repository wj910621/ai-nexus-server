# TriGen 部署指南

## 快速部署（推荐）

### 方式一：SSH 自动部署（本地执行）

```bash
# 1. 给脚本添加执行权限
chmod +x ssh-deploy.sh

# 2. 执行部署
./ssh-deploy.sh
```

### 方式二：手动打包上传

```bash
# 1. 本地打包
chmod +x upload.sh
./upload.sh

# 2. 上传到服务器
scp trigen-hub-*.tar.gz admin@120.79.17.184:/home/admin/

# 3. SSH 登录服务器
ssh admin@120.79.17.184

# 4. 解压并部署
cd /home/admin
tar -xzf trigen-hub-*.tar.gz
./deploy.sh
```

---

## 服务器要求

| 项目 | 要求 |
|------|------|
| Node.js | ≥ 18.x |
| PM2 | 最新稳定版 |
| 端口 | 3001（需开放） |

---

## 部署后配置

### 1. 环境变量配置

在服务器上编辑 `.env` 文件：

```bash
cd /home/admin/he-wiki-rag
nano .env
```

配置你的 API 密钥。

### 2. 检查服务状态

```bash
pm2 status
pm2 logs trigen-hub
```

### 3. 常用命令

```bash
# 重启服务
pm2 restart trigen-hub

# 查看日志
pm2 logs trigen-hub --lines 100

# 监控面板
pm2 monit

# 开机自启
pm2 startup
pm2 save
```

---

## Nginx 反向代理配置（可选）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## 故障排查

### 服务无法启动

```bash
# 查看错误日志
pm2 logs trigen-hub --err --lines 50

# 检查端口占用
netstat -tlnp | grep 3001

# 检查 Node 版本
node -v
```

### 数据库问题

```bash
# 检查数据库文件
ls -la *.db

# 重新初始化
rm -f trigen.db
pm2 restart trigen-hub
```

---

## 联系支持

如有问题，请提供：
1. `pm2 logs trigen-hub --lines 100` 的输出
2. 服务器 Node 版本：`node -v`
3. 操作系统信息：`cat /etc/os-release`
