# 项目记忆

## 品牌命名（最终确定，2026-06-12）
- **中文名**: 三联
- **英文名**: Y·NEX
- **标语**: All from Three
- **全称**: Y·NEX Studio
- **哲学**: 一生二、二生三、三生万物，万物互联
- **欢迎语**: "欢迎来到未来" + "All from Three"

## 前端设计偏好
- 浅色主题（背景 #f5f5f7，侧边栏 #ececf0）
- 桌面应用布局：左侧边栏 + 顶部工具栏 + 底部输入栏
- 四个核心模块：对话、知识库、Agent、Skills
- 单文件架构（所有 CSS/JS 内联）

## 部署信息
- 服务器: 120.79.17.184
- 前端路径: /home/admin/nexus-studio/index.html
- 后端路径: /home/admin/ai-nexus/server.js
- 访问: http://j3trisheng.com → landing.html
- SSL: /etc/nginx/ssl/origin.pem + origin.key
- PM2: nexus-hub (端口 3001)

## 反作弊积分系统（2026-06-14）
- **访客积分后端持久化**: `guest_fingerprints` 表，设备指纹 + IP 追踪
- **每日限额**: 30 积分/天/设备，刷新不重置（从后端同步）
- **设备指纹限一**: 每个设备指纹最多注册 1 个账号
- **IP 限二**: 每个 IP 最多注册 2 个账号（已有）
- **渐进式解锁**:
  - 0-14 分：正常使用
  - 15-19 分：弹出"建议注册"提示
  - 20-29 分：强制提示"必须注册"
  - 30 分：锁定，显示注册弹窗
- **API**: `POST /api/guest/sync`（同步积分）、`POST /api/guest/spend`（消费）
- **前端**: Canvas 设备指纹 + 后端积分同步 + 渐进解锁 UI
