# WebSocket API 文档

> 本文档详细说明实时通信接口，用于生成进度推送、协作编辑、状态同步。

---

## 一、连接规范

### 1.1 连接地址
```
wss://ynexai.cn/story-ws?token=<jwt_token>  # 生产共享域名；本地开发为 ws://localhost:8000/ws
```

### 1.2 消息格式
```json
{
  "type": "event_type",
  "channel": "channel_name",
  "data": {},
  "timestamp": 1784351313
}
```

### 1.3 心跳机制
- 客户端每30秒发送 `{"type": "ping"}`
- 服务端响应 `{"type": "pong"}`
- 60秒无心跳断开连接

---

## 二、事件类型

### 2.1 渲染进度事件

**订阅频道：** `render.{task_id}`

```json
{
  "type": "render_progress",
  "channel": "render.abc123",
  "data": {
    "task_id": "abc123",
    "status": "processing",
    "progress": 45,
    "current_frame": 9,
    "total_frames": 20,
    "current_frame_url": "https://...",
    "estimated_remaining": 120
  }
}
```

**完成事件：**
```json
{
  "type": "render_completed",
  "channel": "render.abc123",
  "data": {
    "task_id": "abc123",
    "status": "completed",
    "output_url": "https://...",
    "duration": 45.5,
    "file_size": 52428800
  }
}
```

### 2.2 图像生成进度

**订阅频道：** `image_gen.{request_id}`

```json
{
  "type": "image_progress",
  "channel": "image_gen.xyz789",
  "data": {
    "step": 15,
    "total_steps": 30,
    "preview_url": "https://...preview.jpg",
    "progress": 50
  }
}
```

### 2.3 协作编辑事件

**订阅频道：** `project.{project_id}`

**用户加入：**
```json
{
  "type": "collab_user_joined",
  "channel": "project.abc123",
  "data": {
    "user_id": "uuid",
    "username": "张三",
    "avatar": "https://..."
  }
}
```

**内容变更：**
```json
{
  "type": "collab_content_changed",
  "channel": "project.abc123",
  "data": {
    "user_id": "uuid",
    "target_type": "script",
    "target_id": "scene_uuid",
    "changes": {
      "field": "description",
      "old_value": "旧内容",
      "new_value": "新内容"
    }
  }
}
```

**光标位置同步：**
```json
{
  "type": "collab_cursor",
  "channel": "project.abc123",
  "data": {
    "user_id": "uuid",
    "target_type": "script",
    "position": {
      "line": 5,
      "column": 10
    }
  }
}
```

### 2.4 系统通知事件

**订阅频道：** `user.{user_id}.notifications`

```json
{
  "type": "notification",
  "channel": "user.abc123.notifications",
  "data": {
    "id": "notification_uuid",
    "category": "render",
    "title": "渲染完成",
    "message": "您的漫剧《夏日物语》已渲染完成",
    "action_url": "/projects/xxx/render/yyy",
    "created_at": "2026-07-18T12:00:00Z"
  }
}
```

### 2.5 计费事件

**订阅频道：** `user.{user_id}.billing`

```json
{
  "type": "credits_deducted",
  "channel": "user.abc123.billing",
  "data": {
    "amount": 10,
    "reason": "create_character",
    "remaining_credits": 4990,
    "timestamp": "2026-07-18T12:00:00Z"
  }
}
```

---

## 三、客户端请求

### 3.1 订阅频道

```json
{
  "type": "subscribe",
  "channel": "render.abc123"
}
```

### 3.2 取消订阅

```json
{
  "type": "unsubscribe",
  "channel": "render.abc123"
}
```

### 3.3 协作编辑推送

```json
{
  "type": "collab_edit",
  "channel": "project.abc123",
  "data": {
    "target_type": "script",
    "target_id": "scene_uuid",
    "field": "description",
    "value": "新内容"
  }
}
```

---

## 四、错误处理

```json
{
  "type": "error",
  "data": {
    "code": "SUBSCRIPTION_DENIED",
    "message": "无权订阅此频道"
  }
}
```

---

*本文档最后更新：2026-07-18*
