# TriGen (Nexus Hub) 部署说明
# ==============================

## 快速部署（SSH方式）

```bash
# 1. 上传文件
scp trigen-deploy.tar.gz admin@your-server:/home/admin/he-wiki-rag/

# 2. SSH登录服务器
ssh admin@your-server

# 3. 解压部署包
cd /home/admin/he-wiki-rag
tar -xzvf trigen-deploy.tar.gz

# 4. 运行自动部署脚本
chmod +x autodeploy.sh
./autodeploy.sh
```

## 宝塔面板部署

1. 上传 `trigen-deploy.tar.gz` 到 `/www/wwwroot/j3trisheng.com/`
2. 解压文件
3. 在终端中执行：
   ```bash
   cd /www/wwwroot/j3trisheng.com
   npm install
   ```
4. 添加Node项目，选择server.js
5. 设置端口：3000

## Docker部署

```bash
# 构建镜像
docker build -t trigen .

# 运行容器
docker run -d \
  --name trigen \
  -p 3000:3000 \
  -v /data/trigen:/app/data \
  trigen
```

## Ansible部署

```bash
ansible-playbook -i inventory deploy.yml
```

## 文件清单

```
trigen-deploy/
├── autodeploy.sh          # 自动部署脚本
├── .deploy.conf           # 配置文件
├── README_DEPLOY.md       # 部署说明
├── index.html             # 主页面
├── server.js              # Node服务
├── package.json           # 依赖配置
├── ecosystem.config.js    # PM2配置
├── js/                    # JavaScript模块
│   ├── prompts.js         # 提示词系统
│   ├── safety.js          # 安全确认
│   ├── memory.js          # 记忆系统
│   ├── sandbox.js         # 沙箱执行
│   ├── session.js         # 会话持久化
│   ├── file-editor.js     # 文件编辑器
│   ├── plan-system.js     # 规划系统
│   ├── explore-agent.js   # 代码探索
│   ├── chat.js            # 聊天模块
│   ├── main.js            # 主程序
│   └── ...
├── css/                   # 样式文件
│   └── core.css
└── data/                  # 数据目录
```

## 部署后检查

1. 访问 http://j3trisheng.com 检查是否正常
2. 打开浏览器控制台(F12)检查错误
3. 测试发送消息功能
4. 检查PM2日志：`pm2 logs trigen`

## 常见问题

### 端口被占用
```bash
# 查看端口占用
lsof -i:3000

# 杀掉进程
kill -9 <PID>
```

### npm安装失败
```bash
# 清理缓存
npm cache clean --force

# 重新安装
rm -rf node_modules package-lock.json
npm install
```

### PM2启动失败
```bash
# 查看错误日志
pm2 logs trigen --err

# 手动启动调试
node server.js
```
