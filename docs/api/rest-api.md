# REST API 文档

> 本文档详细说明漫剧生成软件的REST API接口规范。

---

## 一、API总览

### 1.1 基础信息
- **Base URL**: 由部署决定。本地开发 `http://localhost:8000/api`；生产共享域名（`ynexai.cn`）为 `https://ynexai.cn/story-api`（后端监听 `/api/` 前缀，经 nginx `/story-api/` 反代）。详见 `docs/deployment/PRODUCTION_LAUNCH_RUNBOOK.md`。
- **认证方式**: Bearer Token (JWT)
- **请求格式**: `application/json`（文件上传使用`multipart/form-data`）
- **响应格式**: 统一JSON格式

### 1.2 统一响应格式

```typescript
// 成功响应
{
  "code": 0,
  "message": "success",
  "data": T,
  "timestamp": 1784351313
}

// 分页响应
{
  "code": 0,
  "message": "success",
  "data": T[],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "timestamp": 1784351313
}

// 错误响应
{
  "code": 40401,
  "message": "角色不存在",
  "data": null,
  "timestamp": 1784351313
}
```

### 1.3 错误码定义

| 错误码 | 含义 | HTTP状态 |
|--------|------|----------|
| 0 | 成功 | 200 |
| 40001 | 参数错误 | 400 |
| 40101 | 未认证 | 401 |
| 40301 | 无权限 | 403 |
| 40401 | 资源不存在 | 404 |
| 40201 | 积分不足 | 402 |
| 42901 | 请求过于频繁 | 429 |
| 50001 | 服务器内部错误 | 500 |

---

## 二、认证接口

### 2.1 用户注册

```
POST /auth/register
```

**请求参数：**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "invite_code": "string (可选)"
}
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "user_id": "uuid",
    "username": "string",
    "token": "jwt_token",
    "expires_in": 7200
  }
}
```

### 2.2 用户登录

```
POST /auth/login
```

**请求参数：**
```json
{
  "email": "string",
  "password": "string"
}
```

### 2.3 刷新Token

```
POST /auth/refresh
```

**Headers:**
```
Authorization: Bearer <refresh_token>
```

---

## 三、项目管理接口

### 3.1 创建项目

```
POST /projects
```

**请求参数：**
```json
{
  "name": "我的漫剧项目",
  "description": "项目描述",
  "genre": "romance",
  "template_id": "basic_comic (可选)"
}
```

### 3.2 获取项目列表

```
GET /projects?page=1&page_size=20&status=active
```

### 3.3 获取项目详情

```
GET /projects/{project_id}
```

---

## 四、角色管理接口

### 4.1 创建角色

```
POST /characters
```

**请求参数：**
```json
{
  "name": "角色名",
  "description": "角色描述",
  "style": "anime",
  "gender": "female",
  "age": "青年",
  "hair_color": "黑色",
  "eye_color": "蓝色",
  "project_id": "uuid"
}
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "name": "角色名",
    "main_image_url": "https://...",
    "feature_vector": [...],
    "created_at": "2026-07-18T12:00:00Z"
  }
}
```

### 4.2 生成角色变体

```
POST /characters/{character_id}/variants
```

**请求参数：**
```json
{
  "variant_type": "expression",
  "config": {
    "expression": "happy"
  }
}
```

### 4.3 训练角色LoRA

```
POST /characters/{character_id}/train-lora
```

**请求：** `multipart/form-data`
```
files: [file1.png, file2.png, ...]  (至少5张)
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "task_id": "celery_task_id",
    "status": "training",
    "estimated_time": 1800
  }
}
```

---

## 五、剧本接口

### 5.1 AI生成剧本

```
POST /scripts/generate
```

**请求参数：**
```json
{
  "project_id": "uuid",
  "outline": "故事大纲...",
  "genre": "romance",
  "structure": "three_act",
  "target_scenes": 10,
  "characters": [
    {"name": "角色A", "description": "描述"}
  ]
}
```

### 5.2 获取剧本分镜数据

```
GET /scripts/{script_id}/storyboard
```

**响应：**
```json
{
  "code": 0,
  "data": [
    {
      "frame_index": 0,
      "scene_id": "uuid",
      "shot_type": "wide",
      "description": "建立镜头：放学后的教室",
      "dialogue": {
        "character": "小明",
        "content": "终于放学了！",
        "emotion": "happy"
      },
      "duration": 2.5
    }
  ]
}
```

---

## 六、图像生成接口

### 6.1 文生图

```
POST /image-gen/text2img
```

**请求参数：**
```json
{
  "prompt": "提示词",
  "negative_prompt": "负面提示词",
  "width": 1024,
  "height": 1024,
  "steps": 30,
  "guidance_scale": 7.5,
  "seed": -1,
  "model": "sdxl"
}
```

### 6.2 图生图

```
POST /image-gen/img2img
```

**请求：** `multipart/form-data`
```
init_image: file
prompt: string
strength: float
```

---

## 七、渲染接口

### 7.1 创建渲染任务

```
POST /render/tasks
```

**请求参数：**
```json
{
  "project_id": "uuid",
  "script_id": "uuid",
  "name": "渲染任务名称",
  "config": {
    "resolution": "1920x1080",
    "fps": 24,
    "format": "mp4",
    "quality": "high",
    "include_subtitle": true,
    "include_bgm": true,
    "transition": "fade"
  }
}
```

### 7.2 查询渲染进度

```
GET /render/tasks/{task_id}/progress
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "processing",
    "progress": 45,
    "current_frame": 9,
    "total_frames": 20,
    "estimated_remaining": 120
  }
}
```

### 7.3 下载渲染结果

```
GET /render/tasks/{task_id}/download
```

**响应：** 文件流（`application/octet-stream`）

---

## 八、工作流接口

### 8.1 执行工作流

```
POST /workflows/execute
```

**请求参数：**
```json
{
  "nodes": [
    {
      "id": "1",
      "type": "text_to_image",
      "params": {
        "width": 1024,
        "height": 1024,
        "steps": 30
      }
    },
    {
      "id": "2",
      "type": "image_preview",
      "params": {}
    }
  ],
  "edges": [
    {
      "from": "1",
      "to": "2",
      "from_port": "image",
      "to_port": "image"
    }
  ],
  "inputs": {
    "1": {
      "prompt": "a beautiful anime girl"
    }
  }
}
```

### 8.2 获取可用节点列表

```
GET /workflows/nodes
```

**响应：**
```json
{
  "code": 0,
  "data": [
    {
      "type": "text_to_image",
      "name": "文生图",
      "category": "generation",
      "inputs": [...],
      "outputs": [...],
      "parameters": [...]
    }
  ]
}
```

### 8.3 获取模板列表

```
GET /workflows/templates?category=basic
```

---

## 九、计费接口

### 9.1 获取账户信息

```
GET /billing/account
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "user_id": "uuid",
    "plan": "pro",
    "credits": 5000,
    "credits_used": 1200,
    "subscription_expires": "2026-08-18T00:00:00Z",
    "usage_this_month": {
      "image_generations": 150,
      "video_renders": 5,
      "lora_trainings": 2
    }
  }
}
```

### 9.2 充值积分

```
POST /billing/recharge
```

**请求参数：**
```json
{
  "amount": 100,
  "payment_method": "wechat"
}
```

### 9.3 获取用量统计

```
GET /billing/usage?start_date=2026-07-01&end_date=2026-07-31
```

---

## 十、限流策略

| 用户等级 | 图像生成 | 视频渲染 | LoRA训练 | API调用 |
|----------|----------|----------|----------|---------|
| 免费版 | 10次/小时 | 1次/天 | 不可用 | 60次/分钟 |
| 专业版 | 100次/小时 | 20次/天 | 5次/月 | 300次/分钟 |
| 企业版 | 无限制 | 无限制 | 无限制 | 1000次/分钟 |

### 限流响应
```json
{
  "code": 42901,
  "message": "请求过于频繁，请稍后再试",
  "data": {
    "retry_after": 60,
    "limit": 10,
    "remaining": 0,
    "reset_at": "2026-07-18T13:00:00Z"
  }
}
```

---

## 十一、WebSocket事件

详见 [WebSocket API文档](websocket-api.md)

---

*本文档最后更新：2026-07-18*
