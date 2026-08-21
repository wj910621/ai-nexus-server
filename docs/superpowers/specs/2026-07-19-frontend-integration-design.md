# 前端集成设计：WebSocket / SSE / 首次启动向导

- **日期**：2026-07-19
- **阶段**：Phase 7 后续 / 前端集成
- **前置**：Phase 7 Task 10（WebSocketManager + /ws）、Task 12（SSE 流式对话）、Task 15（LocalRuntimeDetector）、Task 16（首次启动向导骨架，需修复路径问题）
- **后续**：Phase 8 规划（K8s / 多区域 / 语义缓存 / LoRA 训练 UI / AMD/Intel 支持）→ 生产部署

## 1. 目标

将后端 Phase 7 已实现的实时能力（WebSocket、SSE、本地推理运行时检测）接入前端 React 应用，并提供首启动向导，使 Web 浏览器和 Electron Desktop 两端共享同一套代码并具备差异化能力。

### 1.1 核心目标

1. **WebSocket 集成**：订阅后端 channel pub/sub，支持 4 个场景——后台任务进度、工作流执行进度、实时通知、（扩展阶段）实时协作编辑
2. **SSE 集成**：消费 `/api/v1/chat?stream=true` 流式响应，支持 AI 对话、图像/音频/导出任务进度
3. **首次启动向导**：4 步流程（欢迎与法律 → 运行时检测 → AI Provider 选择 → 数据与隐私），同时适配 Web 和 Desktop
4. **修复 Task 16 遗留问题**：删除 `desktop/src/renderer/` 错误目录，重写 `first-launch.ts`，扩展 preload bridge
5. **保证商业策略落地**：所有 AI 功能（本地+云）必须订阅或付费，向导默认推荐云 API，本地推理作为 Pro 福利

### 1.2 非目标

- 不实现实时协作编辑的 OT/CRDT 后端（标记为扩展阶段，仅留 hook 接口）
- 不重构现有 `authStore` / `editorStore`
- 不引入新的 UI 框架（继续使用 antd 5）
- 不修改后端现有 API（仅新增 endpoint + 在现有 service 中追加 WS publish 调用）

## 2. 范围

### 2.1 适用范围

- **Web 端**：`frontend/` React 应用，浏览器访问
- **Desktop 端**：Electron renderer，通过 `electron.vite.config.ts` 配置 `renderer.root = '../frontend'` 完全复用 frontend 代码

### 2.2 用户决策摘要

| 决策点 | 用户选择 |
|---|---|
| 集成范围 | 两端统一 + Desktop 增强（推荐） |
| WS 场景 | 后台任务进度、工作流执行进度、实时通知、实时协作编辑（扩展阶段） |
| SSE 场景 | AI 对话流式输出、图像生成进度、音频任务进度、项目导出进度 |
| 向导步骤 | 欢迎与法律、GPU/运行时检测、AI Provider 选择、数据与隐私 |
| 商业策略 | 所有 AI 功能（本地+云）必须订阅或收费；云 API 默认推荐，本地推理作为 Pro 福利，混合模式 Pro 专属 |

## 3. 总体架构

### 3.1 分层结构

```
┌──────────────────────────────────────────────────────────┐
│  UI Layer (Pages/Components)                             │
│  - FirstLaunchPage, ExecutionPanel, NotificationBell,    │
│    TaskProgressList, ChatPanel, RealtimeStatus           │
└──────────────────────────────────────────────────────────┘
                          ↑
┌──────────────────────────────────────────────────────────┐
│  Hooks Layer (frontend/src/hooks/)                       │
│  - useWebSocket / useSSE      传输层抽象                  │
│  - useTaskProgress / useWorkflowStream / useNotifications│
│  - useFirstLaunch             向导流程编排                │
└──────────────────────────────────────────────────────────┘
                          ↑
┌──────────────────────────────────────────────────────────┐
│  State Layer (frontend/src/stores/)                      │
│  - realtimeStore (zustand)   连接状态/通知/任务进度缓存    │
│  - 现有 authStore / editorStore 不改动                    │
└──────────────────────────────────────────────────────────┘
                          ↑
┌──────────────────────────────────────────────────────────┐
│  Transport Layer (frontend/src/api/)                     │
│  - websocket.ts              WS 单例客户端                │
│  - sse.ts                     SSE 工厂函数                │
│  - runtime.ts                 isElectron 检测 + 抽象       │
└──────────────────────────────────────────────────────────┘
                          ↑
┌──────────────────────────────────────────────────────────┐
│  Backend (Phase 7 已实现 + 本 spec 配套小改动)            │
│  - /ws (Task 10 WebSocketManager + JWT)                  │
│  - /api/v1/chat?stream=true (Task 12 SSE)                │
│  - /api/v1/models/runtime (Task 15 LocalRuntimeDetector) │
│  - WebSocketManager.publish(channel, msg)                │
│  - 新增：PUT /api/v1/users/me/preferences                 │
│  - 新增：PUT /api/v1/users/me/first-launch                │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Web/Desktop 共用机制

**环境检测**：`utils/runtime.ts` 导出 `isElectron` 常量
- 判定条件：`typeof window !== 'undefined' && 'electronAPI' in window`
- Desktop renderer 通过 preload bridge (`window.electronAPI`) 暴露的 API 调用 Electron 主进程能力
- 所有 desktop-only 调用必须经过 `window.electronAPI?.xxx` 可选链，web 端自动降级

**WS/SSE 端点解析**：
- Web：`/ws` 和 `/api/v1/chat?stream=true`（同源相对路径）
- Desktop：`ws://127.0.0.1:{port}/ws` 和 `http://127.0.0.1:{port}/api/v1/chat?stream=true`
- 由 `window.electronAPI?.getBackendUrl?.()` 返回，未定义时回退到相对路径

### 3.3 文件清单

**新增（14 个文件）**：

| 路径 | 用途 |
|---|---|
| `frontend/src/utils/runtime.ts` | isElectron 检测 + getBackendUrl |
| `frontend/src/api/websocket.ts` | WS 客户端单例 |
| `frontend/src/api/sse.ts` | SSE 工厂函数 |
| `frontend/src/stores/realtimeStore.ts` | 实时状态 store |
| `frontend/src/hooks/useWebSocket.ts` | 频道订阅 hook |
| `frontend/src/hooks/useSSE.ts` | 流式请求 hook |
| `frontend/src/hooks/useTaskProgress.ts` | 后台任务进度 |
| `frontend/src/hooks/useWorkflowStream.ts` | 工作流执行进度 |
| `frontend/src/hooks/useNotifications.ts` | 实时通知 |
| `frontend/src/pages/FirstLaunchPage.tsx` | 4 步向导 |
| `frontend/src/components/common/NotificationBell.tsx` | 通知铃铛 |
| `frontend/src/components/common/RealtimeStatus.tsx` | WS 连接状态指示器 |
| `frontend/src/components/dashboard/TaskProgressList.tsx` | 任务进度列表 |
| `frontend/src/components/project/ChatPanel.tsx` | 流式对话面板 |

**修改（前端 6 个文件）**：

| 路径 | 改动 |
|---|---|
| `frontend/src/App.tsx` | 添加 `/first-launch` 路由 + desktop 首启检测 |
| `frontend/src/routes/index.tsx` | 新增 `/first-launch` 路由定义 |
| `frontend/src/components/workflow/ExecutionPanel.tsx` | 接入 `useWorkflowStream` |
| `frontend/src/components/layout/TopBar.tsx` | 挂载 `NotificationBell` + `RealtimeStatus` |
| `frontend/src/pages/DashboardPage.tsx` | 挂载 `TaskProgressList` |
| `frontend/src/pages/ProjectEditorPage.tsx` | 挂载 `ChatPanel` |

**修改（Desktop 2 个文件）**：

| 路径 | 改动 |
|---|---|
| `desktop/src/main/first-launch.ts` | 重写：删除 loadFile('first-launch.html')，改为 hash 路由（dev: loadURL(`${DEV_SERVER_URL}#/first-launch`) / prod: loadFile(PROD_RENDERER_ENTRY, { hash: '/first-launch' })）；删除 triggerModelDownload（移到前端） |
| `desktop/src/preload/api.ts` | 暴露 7 个新 API：getBackendUrl、getRuntimeInfo、chooseDirectory、saveSettings、completeFirstLaunch、downloadModel、onBackendUrlChange |

**删除**：
- `desktop/src/renderer/` 整个目录（Task 16 错误产物，renderer root 已指向 `../frontend`）

**后端新增/修改（7 个文件）**：

| 路径 | 改动 | 行数估计 |
|---|---|---|
| `backend/app/models/user.py` | 新增 4 字段：first_launch_completed, preferred_provider, telemetry_enabled, cloud_sync_enabled | +8 |
| `backend/app/api/users.py` | 新增 `PUT /me/preferences` 和 `PUT /me/first-launch` | +50 |
| `backend/app/schemas/user.py` | 新增 `UserPreferencesUpdate`、`FirstLaunchUpdate` schema | +30 |
| `backend/app/engines/workflow/executor.py` | 节点执行前后 publish 到 `workflow:{id}` 频道 | +30 |
| `backend/app/services/task_service.py` | 任务进度变更时 publish 到 `task:{id}` 频道 | +20 |
| `backend/app/services/billing_service.py` | 额度低/订阅到期时 publish 到 `user:{id}` | +15 |
| `backend/alembic/versions/006_add_user_preferences.py` | 新迁移：4 列 + 默认值 | +40 |

**法律协议文件**（2 个，纯文本）：
- `frontend/src/legal/terms.md`
- `frontend/src/legal/privacy.md`

### 3.4 新增依赖

- `react-markdown` + `remark-gfm`（渲染法律协议，向导 Step 1 使用）
- 其余使用现有 antd Steps、Button、Radio、Checkbox、Card 组件

## 4. WebSocket 客户端设计

### 4.1 接口定义

```typescript
type WSStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed'

interface WSMessage {
  type: 'subscribed' | 'unsubscribed' | 'pong' | 'error' | string
  channel?: string
  data?: unknown
  [key: string]: unknown
}

type ChannelHandler = (msg: WSMessage) => void

class WebSocketClient {
  async connect(token: string): Promise<void>
  disconnect(): void
  subscribe(channel: string, handler: ChannelHandler): () => void
  getStatus(): WSStatus
  onStatusChange(cb: (s: WSStatus) => void): () => void
  reconnectWithToken(token: string): Promise<void>
}

export const wsClient = new WebSocketClient()
```

### 4.2 关键设计

1. **延迟连接**：单例创建时不连接，由 `useWebSocket` hook 在用户已认证时触发 `connect(token)`
2. **JWT 认证**：URL 构造 `getBackendUrl().replace(/^http/, 'ws') + '/ws?token=' + token`
3. **频道引用计数**：`channelRefs: Map<string, number>`，多个组件订阅同一频道时，第一次发送 `{"type":"subscribe","channel":"task:123"}`，引用清零时发送 `unsubscribe`
4. **心跳**：连接成功后每 30s 发 `{"type":"ping"}`，10s 内未收 pong 则强制重连
5. **指数退避重连**：1s → 2s → 4s → 8s → 16s → 30s（封顶），连接成功后重置 attempts，重连期间自动重新订阅所有 channelRefs 中的频道
6. **消息分发**：`{"type":"subscribed"|"pong"|"error"}` 是控制消息（不转发给 handlers）；其他带 `channel` 字段的消息按 channel 分发给对应 handlers
7. **Token 刷新**：`authStore` 监听 token 变化时调用 `wsClient.reconnectWithToken(newToken)`
8. **认证失败**：WS 关闭码 4001 → 调用 `authStore.logout()` + 跳转登录页
9. **重连上限**：超过 5 次仍失败则停止重连，标记 `closed`，由用户手动重试

### 4.3 频道命名规约

沿用后端 Task 10 已定义：
- `user:{user_id}` — 用户私有通知频道
- `task:{task_id}` — 后台任务进度
- `workflow:{execution_id}` — 工作流执行进度（本次新增）
- `image:{image_id}` — 图像生成进度
- `video:{video_id}` — 视频生成进度
- `global` — 全局广播

## 5. SSE 客户端设计

### 5.1 接口定义

```typescript
interface SSEOptions {
  url: string
  body?: unknown
  signal?: AbortSignal
  onMessage: (data: string) => void
  onError?: (err: Error) => void
  onDone?: () => void
}

export async function fetchSSE(options: SSEOptions): Promise<void>
```

### 5.2 关键设计

1. **不用 EventSource**：EventSource 不支持自定义 header（无法附加 Bearer token），且只支持 GET
2. **基于 fetch + ReadableStream**：手动解析 SSE 协议（`data: ...\n\n`）
3. **POST 请求**：默认 POST + Content-Type: application/json + Bearer token（从 `tokenStorage`）
4. **AbortController**：调用方通过 `signal` 控制中断（如组件 unmount 或用户点击"停止生成"）
5. **错误处理**：HTTP 非 2xx 抛错；网络中断调用 `onError`；正常结束调用 `onDone`
6. **不自动重试**：SSE 流断开后由调用方决定是否重试（hooks 层实现重试逻辑）
7. **超时**：60s 无数据自动 abort + `onError(new Error('SSE timeout'))`

### 5.3 SSE 协议解析

```typescript
const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const events = buffer.split('\n\n')
  buffer = events.pop() || ''
  for (const event of events) {
    if (event.startsWith('data: ')) {
      onMessage(event.slice(6))
    }
  }
}
```

### 5.4 后端 SSE 响应格式（Task 12 已实现）

```
data: {"type":"token","content":"好"}
data: {"type":"token","content":"的"}
data: {"type":"token","content":"，"}
...
data: {"type":"done","usage":{"prompt_tokens":50,"completion_tokens":120}}
```

## 6. Realtime Store 设计

### 6.1 接口定义

```typescript
interface NotificationItem {
  id: string
  type: 'task_completed' | 'task_failed' | 'credit_low' | 'subscription_expiring' | 'system_maintenance'
  title: string
  body: string
  createdAt: number
  read: boolean
}

interface TaskProgress {
  taskId: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number        // 0-1
  stage: string
  eta?: number
  result?: unknown
  error?: string
}

interface RealtimeState {
  wsStatus: WSStatus
  notifications: NotificationItem[]    // 最近 50 条，FIFO
  taskProgress: Record<string, TaskProgress>
  setWsStatus: (s: WSStatus) => void
  addNotification: (n: NotificationItem) => void
  markAllRead: () => void
  updateTaskProgress: (taskId: string, p: TaskProgress) => void
  removeTaskProgress: (taskId: string) => void
}
```

### 6.2 设计要点

- 使用 zustand `persist` 中间件持久化 `notifications`（最近 50 条）
- `taskProgress` 不持久化（临时状态，刷新后从 API 重新拉取）
- `unreadCount` 派生自 `notifications.filter(n => !n.read).length`，由组件计算
- `notifications` 超过 50 条自动 FIFO 裁剪
- `taskProgress` 任务完成 3s 后由 hook 自动移除

## 7. Hooks 层设计

### 7.1 Hook 一览

| Hook | 职责 | 依赖 |
|---|---|---|
| `useWebSocket(channel)` | 订阅指定频道，返回最新消息 | wsClient + realtimeStore |
| `useSSE(url, body)` | 发起 SSE 流式请求，返回 `{ data, done, error, abort }` | sse.ts |
| `useTaskProgress(taskId)` | 订阅 `task:{id}` 频道，返回进度 | useWebSocket + taskProgress API |
| `useWorkflowStream(executionId)` | 订阅 `workflow:{id}` 频道 | useWebSocket |
| `useNotifications()` | 订阅 `user:{id}` 频道，返回通知列表 | useWebSocket + realtimeStore |

### 7.2 useWebSocket 生命周期

```typescript
function useWebSocket(channel: string | null) {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  
  useEffect(() => {
    if (!channel) return
    // 确保已认证并连接
    const token = tokenStorage.getAccessToken()
    if (token && wsClient.getStatus() === 'idle') {
      wsClient.connect(token)
    }
    // 订阅频道（仅返回最新消息，store 同步由专用 hook 处理）
    const unsubscribe = wsClient.subscribe(channel, (msg) => {
      setLastMessage(msg)
    })
    return unsubscribe
  }, [channel])
  
  return lastMessage
}
```

**专用 hook 负责 store 同步**（职责分离）：

```typescript
// useNotifications.ts — 在 useWebSocket 之上叠加 store 同步
function useNotifications() {
  const userId = useAuthStore(s => s.user?.id)
  const lastMsg = useWebSocket(userId ? `user:${userId}` : null)
  
  useEffect(() => {
    if (lastMsg?.type === 'notification') {
      useRealtimeStore.getState().addNotification(lastMsg.data as NotificationItem)
      // Desktop 系统通知
      window.electronAPI?.showNotification?.(lastMsg.data as NotificationItem)
    }
  }, [lastMsg])
  
  return useRealtimeStore(s => s.notifications)
}

// useTaskProgress.ts — 同理
function useTaskProgress(taskId: string | null) {
  const lastMsg = useWebSocket(taskId ? `task:${taskId}` : null)
  
  useEffect(() => {
    if (lastMsg?.type === 'progress' && lastMsg.taskId) {
      useRealtimeStore.getState().updateTaskProgress(
        lastMsg.taskId as string,
        lastMsg.data as TaskProgress
      )
    }
  }, [lastMsg])
  
  return useRealtimeStore(s => taskId ? s.taskProgress[taskId] : undefined)
}
```

### 7.3 useSSE 生命周期

```typescript
function useSSE(url: string, body?: unknown) {
  const [data, setData] = useState<string>('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  
  const start = useCallback(() => {
    const controller = new AbortController()
    abortRef.current = controller
    setData(''); setDone(false); setError(null)
    
    fetchSSE({
      url, body, signal: controller.signal,
      onMessage: (chunk) => setData(prev => prev + chunk),
      onError: setError,
      onDone: () => setDone(true),
    })
  }, [url, body])
  
  const abort = useCallback(() => abortRef.current?.abort(), [])
  
  useEffect(() => () => abort(), [])  // unmount 时清理
  
  return { data, done, error, start, abort }
}
```

### 7.4 降级策略（Progressive Enhancement）

```
WS 可用 ────────────────► 实时推送（最优体验）
  ↓ 不可用（30s 未连上）
轮询 GET /api/v1/tasks/{id}（每 2s）──► 准实时
  ↓ 不可用
同步等待 API 返回（当前行为）────────► 基线体验
```

**实现**：`useTaskProgress` 和 `useWorkflowStream` 内部检测 `wsStatus`，若 30s 内未连上则降级为轮询。

## 8. 首次启动向导设计

### 8.1 路由与触发

**路由**：`/first-launch`（不受 ProtectedRoute 保护）

**触发流程**：

**Desktop**：
```
index.ts 检查 electron-store 的 first-launch-completed 标志
  ↓
未完成 → createMainWindow() 后通过 hash 路由跳转向导
         - dev:  loadURL(`${DEV_SERVER_URL}#/first-launch`)
         - prod: loadFile(PROD_RENDERER_ENTRY, { hash: '/first-launch' })
  ↓
向导完成 → ipcMain 收到 'first-launch:complete' → store.set(true)
         → mainWindow 加载主页（dev: DEV_SERVER_URL / prod: loadFile(PROD_RENDERER_ENTRY)）
         → 进入正常 /dashboard
  ↓
已完成 → 直接加载主页
```

**Web**：
```
用户首次注册后 → 后端 user.first_launch_completed=false
  ↓
登录后路由检查 → 若 false → 跳转 /first-launch
  ↓
完成后调用 PUT /api/v1/users/me/first-launch → 标记 true
  ↓
跳转 /dashboard
```

### 8.2 四步向导（Ant Design Steps）

#### Step 1：欢迎与法律协议

- 欢迎页 + License 协议（Markdown 渲染） + 隐私政策（Markdown 渲染）
- 必须勾选两个复选框（"我已阅读并同意《用户协议》"、"我已阅读并同意《隐私政策》"）才能进入下一步
- 协议文件路径：`frontend/src/legal/terms.md` + `frontend/src/legal/privacy.md`

#### Step 2：运行时检测（Desktop-only，Web 自动跳过）

- 调用 `window.electronAPI?.getRuntimeInfo()` → 内部调用 backend `/api/v1/models/runtime`
- 显示：GPU 名称、VRAM、RAM、平台、推荐 provider
- Web 端 `isElectron === false` → 自动跳到 Step 3
- 检测结果存入组件 local state，供 Step 3 使用
- 失败时显示"检测失败，将使用远程 API"，允许下一步

#### Step 3：AI Provider 选择（商业策略核心）

**三个卡片**：

1. **云 API（Pro 订阅）** — 默认推荐
   - 高质量 SDXL/Qwen 模型
   - 3-5s/图，流式对话
   - 无需本地 GPU
   - 需 Pro 订阅（¥39/月起）
   - 按钮：[立即订阅] / [使用免费试用额度]

2. **本地推理（Pro 福利）**
   - 离线可用、零 API 成本
   - 需要 8GB+ VRAM
   - 速度较慢（GPU ~8s/图）
   - 需 Pro 订阅（解锁本地推理）
   - 按钮：[解锁]

3. **混合模式（Pro 专属）**
   - 优先本地、fallback 云
   - 最佳性价比
   - 需 Pro 订阅
   - 按钮：[选择]

**逻辑分支**：
- **新注册用户 / Free 用户**：默认选中"云 API + 免费试用额度"，本地推理和混合模式卡片置灰 + 显示"升级 Pro 解锁"按钮 → 跳转 `/billing`
- **Pro 用户**：三个选项可选，根据 Step 2 检测结果默认推荐：
  - 有 GPU（≥8GB VRAM）→ 默认"混合模式"
  - 无 GPU → 默认"云 API"
- **Desktop 端未登录首启**（首启时可能尚未注册）：跳转 `/register` 完成注册后回到向导 Step 3
- 选项写入 `users.preferred_provider` 字段（cloud/local/hybrid）

#### Step 4：数据与隐私设置

- **数据存储位置**（仅 Desktop）：默认 `~/Documents/ComicStudio` 或自定义（通过 `window.electronAPI?.chooseDirectory()`）
- **遥测数据**：发送匿名使用统计（默认勾选）
- **自动更新**（仅 Desktop）：自动检查更新（默认勾选）
- **云端同步**：启用项目云端同步（Pro 功能，Free 用户置灰）

### 8.3 完成处理

```typescript
async function handleComplete() {
  // 1. 调用后端保存偏好
  await apiClient.put('/api/v1/users/me/preferences', {
    preferred_provider: selectedProvider,
    telemetry_enabled: telemetry,
    cloud_sync_enabled: cloudSync,
  })
  
  // 2. Desktop: 保存数据存储位置 + 标记首启完成
  if (isElectron) {
    await window.electronAPI!.saveSettings({ dataDir, telemetry, autoUpdate })
    await window.electronAPI!.completeFirstLaunch()
  }
  
  // 3. Web: 调用后端标记首启完成
  await apiClient.put('/api/v1/users/me/first-launch', { completed: true })
  
  // 4. 跳转 /dashboard
  navigate('/dashboard')
}
```

### 8.4 Desktop Preload Bridge 扩展

`desktop/src/preload/api.ts` 新增暴露：

```typescript
getBackendUrl: () => string
getRuntimeInfo: () => Promise<RuntimeInfo>
chooseDirectory: () => Promise<string | null>
saveSettings: (s: Settings) => Promise<void>
completeFirstLaunch: () => Promise<void>
downloadModel: (name: string) => Promise<void>
onBackendUrlChange: (cb: (url: string) => void) => () => void
```

## 9. UI 集成设计

### 9.1 ExecutionPanel 升级

**当前问题**：`frontend/src/components/workflow/ExecutionPanel.tsx` 是同步 `await workflowEngineApi.execute()` 阻塞等待，无实时进度。

**升级后流程**：
1. 用户点击"执行工作流"
2. 调用 `POST /api/v1/workflows/execute` → 返回 `{ execution_id }`
3. `useWorkflowStream(execution_id)` 订阅 WS 频道 `workflow:{execution_id}`
4. WS 推送事件：
   - `{ type: "node_start", node_id, timestamp }`
   - `{ type: "node_complete", node_id, result, duration_ms }`
   - `{ type: "node_error", node_id, error }`
   - `{ type: "progress", completed, total, progress }`
   - `{ type: "execution_complete", status, total_duration_ms }`
5. ExecutionPanel 实时更新：
   - 节点状态高亮（绿色=完成、蓝色=执行中、灰色=未开始、红色=失败）
   - 进度条 + 百分比 + 已完成/总数
   - 失败节点显示错误 tooltip
   - 完成后自动取消订阅

### 9.2 通知系统（NotificationBell）

**位置**：TopBar 右侧用户头像旁，铃铛图标 + 红点未读数。

**实现**：
- `NotificationBell` 组件挂在 TopBar
- `useNotifications()` hook 订阅 `user:{userId}` 频道
- 收到 `{type: "notification", ...}` 推送到 `realtimeStore.notifications`
- 桌面端：通过 `window.electronAPI?.showNotification()` 同步触发系统通知
- Web 端：使用浏览器 `Notification` API（需用户授权）

**通知类型**（后端 WebSocketManager 推送）：
- `task_completed` — 后台任务完成（Task 2）
- `task_failed` — 后台任务失败
- `credit_low` — 额度低于阈值（Phase 6 billing）
- `subscription_expiring` — 订阅即将到期（Phase 6）
- `system_maintenance` — 系统维护通知

### 9.3 任务进度列表（TaskProgressList）

**位置**：Dashboard 页面右侧"最近任务"卡片。

**实现**：
- `TaskProgressList` 组件在 DashboardPage 渲染
- 初始化时 `GET /api/v1/tasks?status=running` 获取运行中任务
- 每个任务通过 `useTaskProgress(taskId)` 订阅 `task:{taskId}` 频道
- WS 推送 `{type: "progress", taskId, progress, stage, eta}` 实时更新
- 任务完成自动从列表移除（保留 3s 渐隐动画）

### 9.4 流式对话（ChatPanel）

**位置**：ProjectEditorPage 内的 AI 对话侧栏。

**实现**：
- `ChatPanel` 组件维护 `messages` local state
- `useSSE('/api/v1/chat?stream=true', { message, history })` 发起流式请求
- `onMessage` 收到 token 增量追加到当前 AI 消息
- "停止"按钮调用 `abortController.abort()`
- 流式过程中禁用"发送"按钮，显示"停止"按钮
- 错误时在消息末尾追加 `[错误: xxx]`

### 9.5 RealtimeStatus 指示器

**位置**：TopBar 右下角小圆点（NotificationBell 左侧）。

**状态**：
- 绿色：`connected`
- 橙色：`connecting` / `reconnecting`
- 红色：`closed`
- 灰色：`idle`

点击：弹出 tooltip 显示当前状态 + 手动重连按钮（红色时）。

## 10. 错误处理矩阵

| 场景 | 行为 | 用户感知 |
|---|---|---|
| WS 连接失败（首次） | 指数退避重连（1→30s，封顶） | TopBar 显示橙色"重连中..."小圆点 |
| WS 重连超过 5 次仍失败 | 停止重连，标记 disconnected | TopBar 红点 + tooltip"实时连接断开，点击重试" |
| WS 心跳超时（发 ping 后 10s 未收 pong） | 强制关闭 + 立即重连 | 用户无感知（重连后自动恢复订阅） |
| WS 认证失败（4001） | 不重连，调用 `authStore.logout()` | 跳转登录页 + "会话已过期"提示 |
| Token 刷新后 | `wsClient.reconnectWithToken(newToken)` | 用户无感知 |
| SSE 网络中断 | `onError` 回调，UI 显示"生成中断，点击重试" | ChatPanel 末尾追加错误提示 + 重试按钮 |
| SSE 401 | 触发 token 刷新 → 失败则 logout | 跳转登录页 |
| SSE 5xx | `onError` + 显示"服务暂时不可用" | 错误提示 + 重试按钮 |
| SSE 超时（60s 无数据） | AbortController.abort() + onError | "请求超时"提示 + 重试 |
| 运行时检测失败（向导 Step 2） | 默认 `remote` provider，允许下一步 | "检测失败，将使用远程 API" |
| 后端 `/api/v1/models/runtime` 不可达 | 同上 | 同上 |
| electronAPI 不存在（Web 端调用 desktop API） | 可选链 `?.` 自动返回 undefined | Web 端自动跳过 desktop-only 步骤 |
| 频道订阅后立即 unmount | hook 清理函数 unsubscribe + 引用计数归零 | 无泄漏 |
| 模型下载失败（向导） | 显示失败列表 + "重试"按钮 | 不阻塞向导完成 |

## 11. 测试策略

**目标**：新增 ~35 测试，总测试数 501 → 536+，零回归。

### 11.1 前端单元测试（vitest + @testing-library/react）

| 文件 | 测试数 | 覆盖点 |
|---|---|---|
| `tests/utils/runtime.test.ts` | 3 | isElectron 检测、getBackendUrl 默认值/自定义值 |
| `tests/api/websocket.test.ts` | 8 | 连接/断开/重连/心跳/频道订阅引用计数/消息分发/认证失败/token 刷新 |
| `tests/api/sse.test.ts` | 6 | 正常流/错误响应/网络中断/abort 中断/SSE 协议解析/带 token 请求 |
| `tests/stores/realtimeStore.test.ts` | 5 | addNotification FIFO/超过 50 条裁剪/markAllRead/updateTaskProgress/removeTaskProgress/wsStatus |
| `tests/hooks/useWebSocket.test.tsx` | 4 | 订阅/取消订阅/handler 调用/多组件共享频道 |
| `tests/hooks/useTaskProgress.test.tsx` | 3 | 初始拉取/WS 更新/完成自动清理 |
| `tests/hooks/useWorkflowStream.test.tsx` | 3 | 订阅 workflow 频道/节点事件更新/完成自动取消订阅 |
| `tests/hooks/useNotifications.test.tsx` | 3 | 订阅 user 频道/通知推送/未读数 |
| `tests/pages/FirstLaunchPage.test.tsx` | 6 | 4 步流程/必填校验/Web 跳过 Step 2/Free 用户置灰本地推理/Pro 用户可选/完成提交 |

**Mock 策略**：
- `wsClient` 全局 mock（vi.mock）
- `fetchSSE` 全局 mock
- `window.electronAPI` 在测试中手动注入/清除
- antd Steps 通过 `fireEvent.click` 驱动

### 11.2 后端测试（pytest）

| 文件 | 测试数 | 覆盖点 |
|---|---|---|
| `backend/tests/test_user_preferences.py` | 4 | PUT /me/preferences 鉴权/字段校验/更新/返回当前偏好 |
| `backend/tests/test_first_launch_api.py` | 3 | PUT /me/first-launch 鉴权/标记完成/重复调用幂等 |
| `backend/tests/test_workflow_ws_publish.py` | 3 | 节点开始/完成/失败时 publish 事件到 workflow:{id} 频道 |

### 11.3 集成测试（前端 + Mock 后端）

| 场景 | 测试数 |
|---|---|
| 向导完整流程（Web 端 4 步） | 1 |
| ExecutionPanel 实时进度 | 1 |
| ChatPanel 流式对话 + 中断 | 1 |
| NotificationBell 接收推送 | 1 |
| TaskProgressList 实时更新 | 1 |

## 12. 兼容性保证

### 12.1 Web/Desktop 共用兼容

| 场景 | Web 端 | Desktop 端 |
|---|---|---|
| `window.electronAPI` | undefined（可选链降级） | 已暴露 |
| WS URL | `wss://host/ws?token=` | `ws://127.0.0.1:{port}/ws?token=` |
| SSE URL | `/api/v1/chat?stream=true` | `http://127.0.0.1:{port}/api/v1/chat?stream=true` |
| 运行时检测 | 跳过 Step 2 | 调用 `/api/v1/models/runtime` |
| 数据存储位置 | 隐藏选项 | 显示目录选择 |
| 系统通知 | 浏览器 Notification API | `electronAPI.showNotification()` |
| 自动更新 | 隐藏选项 | 显示 + 调用 `electronAPI.checkForUpdates()` |

**关键原则**：所有 `window.electronAPI?.xxx` 调用必须用可选链，Web 端 fallback 到 Web 实现。

### 12.2 现有 API 兼容

- **后端 API 零破坏**：所有新增 API 为 `PUT /me/preferences`、`PUT /me/first-launch`，不修改现有 endpoint
- **User 模型新增字段**：4 个字段都有默认值（`first_launch_completed=False`、`preferred_provider='cloud'`、`telemetry_enabled=True`、`cloud_sync_enabled=False`），旧数据自动兼容
- **Alembic 迁移**：`006_add_user_preferences.py` 添加列 + 默认值，无破坏性

### 12.3 现有测试不回归

- `ExecutionPanel.tsx` 改造：保留原有 `handleExecute` 同步逻辑作为 fallback（WS 不可用时降级为轮询）
- `TopBar.tsx` 改造：`NotificationBell` 和 `RealtimeStatus` 作为可选组件挂载，不影响现有布局
- `DashboardPage.tsx`：`TaskProgressList` 在 WS 未连接时显示"暂无运行中任务"
- `ProjectEditorPage.tsx`：`ChatPanel` 在 SSE 不可用时降级为同步 POST `/api/v1/chat`

## 13. 迁移路径（修复 Task 16 遗留）

```
Step 1: 删除 desktop/src/renderer/ 整个目录（Task 16 错误产物）
        - desktop/src/renderer/src/pages/FirstLaunch.tsx
        - desktop/src/renderer/ 下的其他文件（如果有）

Step 2: 重写 desktop/src/main/first-launch.ts
        - 删除 loadFile('first-launch.html') 调用
        - 改为 hash 路由：dev 模式 loadURL(`${DEV_SERVER_URL}#/first-launch`)，
          prod 模式 loadFile(PROD_RENDERER_ENTRY, { hash: '/first-launch' })
        - 删除 triggerModelDownload（移到前端通过 preload bridge 调用）

Step 3: 扩展 desktop/src/preload/api.ts
        - 暴露 7 个新 API（见 8.4）

Step 4: 新增 frontend/src/pages/FirstLaunchPage.tsx
        - 4 步向导 + isElectron 分支

Step 5: 新增 /first-launch 路由（不保护）

Step 6: 后端 User 模型 + API + Alembic 迁移

Step 7: 前端 transport/hooks/stores/components

Step 8: 集成改造（ExecutionPanel + TopBar + DashboardPage + ProjectEditorPage）

Step 9: 测试 + 回归验证
```

## 14. 性能考量

- **WS 单例**：全局 1 个 WS 连接，避免多标签页（desktop 单窗口）开多连接
- **频道引用计数**：避免重复 subscribe/unsubscribe 抖动
- **realtimeStore 选择器**：组件用 `useRealtimeStore(s => s.taskProgress[id])` 精确订阅，避免全量重渲染
- **SSE 流量**：每条 token 平均 5 字节，1k token ≈ 5KB，可接受
- **通知裁剪**：`notifications` 超过 50 条自动 FIFO 裁剪，避免内存增长
- **任务进度清理**：任务完成 3s 后从 `taskProgress` 移除，避免 store 膨胀

## 15. 实施顺序（Task 划分预案）

> 详细 task 列表将在 writing-plans 阶段生成，这里仅给出大致顺序。

1. **后端支撑**：User 字段 + API + 迁移 + WS publish 扩展（workflow executor / task_service / billing_service）
2. **Transport 层**：runtime.ts + websocket.ts + sse.ts
3. **Store 层**：realtimeStore.ts
4. **Hooks 层**：5 个 hooks
5. **FirstLaunchPage + desktop bridge 改造**（删除 Task 16 错误文件 + 重写 first-launch.ts + 扩展 preload）
6. **UI 组件**：NotificationBell + TaskProgressList + ChatPanel + RealtimeStatus
7. **集成改造**：ExecutionPanel + TopBar + DashboardPage + ProjectEditorPage
8. **测试 + 回归验证**

## 16. 成功标准

- [ ] 536+ 测试通过（新增 35+，零回归）
- [ ] Web 端首次访问可完成 4 步向导（Step 2 自动跳过）
- [ ] Desktop 端首启检测 GPU 并展示推荐 provider
- [ ] WS 连接成功后 TopBar 显示绿点
- [ ] 后台任务进度实时推送到 Dashboard
- [ ] 工作流执行进度实时更新到 ExecutionPanel
- [ ] ChatPanel 支持 SSE 流式输出 + 中断
- [ ] NotificationBell 接收推送并显示未读数
- [ ] WS 断开自动重连 + 红点提示
- [ ] Web/Desktop 两端无崩溃、无控制台错误
- [ ] Free 用户在向导中看到本地推理置灰 + "升级 Pro"按钮
- [ ] Pro 用户在向导中可选三个 provider 方案

## 17. 视觉设计规范

### 17.1 设计哲学

**定位**：专业级 AI 漫剧创作平台，融合 TRAE IDE 的工程感 + 即梦的 AI 创作美感 + ChatGPT 的对话流畅度。

**四大原则**：
1. **浅色优先**：默认浅色主题（符合大众习惯），暗色可一键切换；浅色降低初次使用门槛
2. **内容为王**：UI 让位于 AI 生成内容（图像/视频/对话），使用低饱和度表面色 + 高对比度内容
3. **中文优先**：字体栈以中文优先，间距与字号针对中文阅读优化
4. **性能优先动画**：动画适度，仅在关键交互反馈处使用，避免过度动画影响性能与体验

### 17.2 色彩系统

**主色（Brand）- 科技蓝**：
```css
--brand-primary: #3B82F6;        /* 科技蓝 - 信任感、专业感（Notion/Linear/Stripe 同色系） */
--brand-primary-hover: #2563EB;
--brand-primary-active: #1D4ED8;
--brand-primary-light: #DBEAFE;  /* 浅色背景态 */
--brand-gradient: linear-gradient(135deg, #3B82F6 0%, #6366F1 100%);
/* 用于 Logo、Pro 徽章、AI 生成按钮 */
```

**辅色（Accent）**：
```css
--accent-cyan: #06B6D4;          /* AI 特色 - 流式光标、AI 标识 */
--accent-emerald: #10B981;       /* 成功 - 任务完成 */
--accent-amber: #F59E0B;         /* 警告 - 额度不足 */
--accent-rose: #EF4444;          /* 错误 - 任务失败 */
--accent-violet: #8B5CF6;        /* Pro 专属 - 订阅徽章 */
```

**浅色主题（默认）**：
```css
--bg-base: #FFFFFF;              /* 最底层背景 */
--bg-surface: #F9FAFB;           /* 卡片、面板背景 */
--bg-elevated: #FFFFFF;          /* 浮层、下拉、tooltip */
--bg-hover: #F3F4F6;             /* hover 态 */
--bg-active: #E5E7EB;            /* active 态 */

--border-subtle: #F3F4F6;        /* 分隔线、弱边框 */
--border-default: #E5E7EB;       /* 默认边框 */
--border-strong: #D1D5DB;        /* 强调边框 */

--text-primary: #111827;         /* 主文字 */
--text-secondary: #4B5563;       /* 次文字 */
--text-tertiary: #9CA3AF;        /* 弱文字、占位符 */
--text-inverse: #FFFFFF;         /* 深色按钮上的白文字反色 */
```

**暗色主题（可选）**：
```css
--bg-base: #0F172A;              /* 比纯黑更柔和的深蓝灰 */
--bg-surface: #1E293B;           /* 卡片、面板背景 */
--bg-elevated: #334155;          /* 浮层、下拉、tooltip */
--bg-hover: #334155;             /* hover 态 */
--bg-active: #475569;            /* active 态 */

--border-subtle: #1E293B;        /* 分隔线、弱边框 */
--border-default: #334155;       /* 默认边框 */
--border-strong: #475569;        /* 强调边框 */

--text-primary: #F1F5F9;         /* 主文字 */
--text-secondary: #94A3B8;       /* 次文字 */
--text-tertiary: #64748B;        /* 弱文字、占位符 */
```

**语义色映射**（两套主题统一）：
| 语义 | 色值 | 用途 |
|---|---|---|
| 成功 | `#10B981` | 任务完成、WS 已连接、Pro 激活 |
| 警告 | `#F59E0B` | 额度 80%、订阅即将到期 |
| 错误 | `#EF4444` | 任务失败、WS 断开、401 |
| 信息 | `#06B6D4` | 流式生成中、AI 标识 |
| Pro | `#8B5CF6` | Pro 徽章、付费功能 |

### 17.3 字体系统

**中文优先字体栈**：
```css
--font-sans: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Source Han Sans CN',
             'Noto Sans CJK SC', -apple-system, BlinkMacSystemFont, 'Segoe UI',
             Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas,
             'PingFang SC', monospace;
--font-display: 'PingFang SC', 'Microsoft YaHei', sans-serif;  /* 标题 */
```

**字号梯度**（8px 网格，针对中文阅读优化）：
| Token | 字号 | 行高 | 字重 | 用途 |
|---|---|---|---|---|
| `text-xs` | 12px | 18px | 400 | 标签、辅助说明 |
| `text-sm` | 13px | 20px | 400 | 正文、表格 |
| `text-base` | 14px | 22px | 400 | 默认正文 |
| `text-md` | 16px | 24px | 500 | 卡片标题 |
| `text-lg` | 18px | 28px | 600 | 页面标题 |
| `text-xl` | 22px | 32px | 700 | 区块大标题 |
| `text-2xl` | 28px | 36px | 700 | 向导标题 |

**中文优化说明**：
- 最小字号 12px（中文 11px 不清晰）
- 行高比英文略大（中文 1.5-1.6 倍，英文 1.4-1.5 倍）
- 默认字重 400，标题 600-700（避免过细导致中文笔画不清晰）

### 17.4 间距与圆角

**间距**（8px grid，适中密度）：
```css
--space-1: 4px;    /* 紧凑间距 - 图标与文字 */
--space-2: 8px;    /* 默认小间距 */
--space-3: 12px;   /* 卡片内边距 */
--space-4: 16px;   /* 默认间距 */
--space-6: 24px;   /* 区块间距 */
--space-8: 32px;   /* 大区块间距 */
--space-12: 48px;  /* 向导步骤间距 */
--space-16: 64px;  /* 页面大间距 */
```

**密度策略**（适中，符合大众习惯）：
- 卡片内边距：`--space-4` (16px) — 不太紧不太松
- 组件间距：`--space-3` (12px) — 默认
- 区块间距：`--space-6` (24px) — 清晰分隔但不空旷
- 输入框/按钮内边距：`8px 12px` — 适中点击区域

**圆角阶**：
```css
--radius-sm: 4px;    /* 小标签、徽章 */
--radius-md: 6px;    /* 按钮、输入框 */
--radius-lg: 8px;    /* 卡片、面板 */
--radius-xl: 12px;   /* 大卡片、向导 provider 卡片 */
--radius-full: 9999px; /* 头像、圆形按钮 */
```

### 17.5 图标系统

**图标库**：`lucide-react`（轻量、现代、与 shadcn 生态一致）
- 安装：`npm install lucide-react`
- 替代方案：`@ant-design/icons`（项目已有 antd，可混用，但优先 lucide）

**图标尺寸**：
| 尺寸 | 用途 |
|---|---|
| 14px | 表格内、紧凑场景 |
| 16px | 默认（按钮、菜单项） |
| 20px | 卡片标题、侧栏 |
| 24px | 向导步骤、空状态 |
| 32px | 大空状态 illustration |

**关键图标映射**：
- 通知铃铛：`Bell`
- WS 状态：`Wifi` / `WifiOff`
- 工作流执行：`Play` / `Square`（停止）
- 任务类型：`Video` / `Image` / `FileText` / `Mic`
- Provider：`Cloud` / `HardDrive` / `Shuffle`（混合）
- Pro 徽章：`Crown` / `Sparkles`
- 主题切换：`Sun` / `Moon`

### 17.6 动画规范（性能优先）

**标准过渡**：
```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
--transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
--transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
```

**应用场景**：
- hover 态：`transition-fast`（150ms）
- 面板展开/收起：`transition-base`（200ms）
- 路由切换：`transition-slow`（300ms）

**性能优先原则**：
- ✅ 仅 `transform` 和 `opacity` 属性动画（GPU 加速，不触发 reflow）
- ✅ 高频更新（进度条、流式光标）使用 `transform` 而非 `width`/`height`
- ❌ 避免动画 `box-shadow`、`border`、`margin` 等触发 layout 的属性
- ❌ 避免同时动画超过 3 个元素
- 默认动画时长 ≤ 200ms，仅路由切换例外 300ms

**关键动画（仅保留必要项）**：
1. **流式打字光标**：1s blink 无限循环（opacity，性能友好）— ChatPanel AI 消息末尾
2. **节点执行脉冲**：1.5s opacity pulse（非 box-shadow）— ExecutionPanel 执行中节点
3. **进度条填充**：200ms ease-out（transform: scaleX）— 任务进度更新
4. **WS 状态点呼吸**：2s ease-in-out infinite（opacity）— 连接中态
5. **向导步骤切换**：200ms opacity fade — 不使用 slide 减少布局计算
6. **通知出现**：150ms opacity + translateY（GPU 加速）

**禁用的过度动画**：
- ❌ 不使用 layout 动画（width/height/margin/padding）
- ❌ 不使用复杂的 keyframe 动画（除非必要）
- ❌ 不使用 backdrop-filter（性能消耗大，仅 statusbar 等小区域可用）
- ❌ 不使用 JavaScript 驱动的动画（除非 CSS 无法实现）
- ❌ 不使用 spring 物理动画（除非用户主动触发的拖拽）

### 17.7 阴影系统

```css
/* 浅色主题 - 柔和阴影 */
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
--shadow-glow: 0 0 0 3px rgba(59, 130, 246, 0.15);  /* 焦点环 - 替代发光 */

/* 暗色主题 - 更深的阴影 */
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
--shadow-glow: 0 0 0 3px rgba(59, 130, 246, 0.25);
```

**说明**：取消发光效果（`0 0 20px`），改为焦点环（`0 0 0 3px`），更符合主流设计且性能更好。

### 17.8 组件视觉规范

#### 17.8.1 按钮

```css
/* Primary - 主操作 */
.btn-primary {
  background: var(--brand-primary);
  color: var(--text-inverse);
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-weight: 500;
  font-size: 13px;
  transition: background var(--transition-fast), transform var(--transition-fast);
  box-shadow: var(--shadow-sm);
}
.btn-primary:hover {
  background: var(--brand-primary-hover);
}
.btn-primary:active {
  background: var(--brand-primary-active);
  transform: translateY(0);  /* 不使用 -1px 避免布局抖动 */
}

/* Success - 订阅、确认 */
.btn-success { background: var(--accent-emerald); }

/* Danger - 取消、停止 */
.btn-danger { background: var(--accent-rose); }

/* Ghost - 次要操作 */
.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
}
.btn-ghost:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-strong);
}

/* Gradient - AI 生成专属 */
.btn-gradient {
  background: var(--brand-gradient);
  color: var(--text-inverse);
}
```

#### 17.8.2 卡片

```css
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  transition: border-color var(--transition-fast);
}
.card:hover {
  border-color: var(--border-default);
}

.card-recommended {
  border-color: var(--accent-emerald);
  box-shadow: 0 0 0 1px var(--accent-emerald);
}

.card-disabled {
  opacity: 0.5;
}
```

#### 17.8.3 输入框

```css
.input {
  background: var(--bg-base);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);  /* 中文优先 */
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.input:focus {
  outline: none;
  border-color: var(--brand-primary);
  box-shadow: var(--shadow-glow);  /* 焦点环 */
}
.input::placeholder {
  color: var(--text-tertiary);
}
```

#### 17.8.4 进度条

```css
/* 使用 transform: scaleX 而非 width，避免 layout */
.progress-track {
  background: var(--bg-hover);
  border-radius: var(--radius-full);
  height: 8px;
  overflow: hidden;
}
.progress-fill {
  background: var(--brand-gradient);
  height: 100%;
  border-radius: var(--radius-full);
  transform-origin: left;
  transition: transform 200ms ease-out;
}
```

#### 17.8.5 通知项

```css
.notification-item {
  padding: 12px;
  border-bottom: 1px solid var(--border-subtle);
  transition: background var(--transition-fast);
}
.notification-item:hover { background: var(--bg-hover); }
.notification-item.unread {
  background: rgba(59, 130, 246, 0.06);
  border-left: 3px solid var(--brand-primary);
}
```

#### 17.8.6 WS 状态指示器

```css
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}
.status-dot.connected {
  background: var(--accent-emerald);
}
.status-dot.connecting {
  background: var(--accent-amber);
  animation: pulse-dot 2s ease-in-out infinite;
}
.status-dot.disconnected {
  background: var(--accent-rose);
}
.status-dot.idle {
  background: var(--text-tertiary);
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

### 17.9 布局规范

#### 17.9.1 主应用布局（参考 TRAE，适中密度）

```
┌─────────────────────────────────────────────────────────────┐
│ 顶部菜单栏 (40px) - Logo + 文件 + 编辑 + 视图 + 帮助 + 主题切换 │
├──────┬──────────────────────────────────┬───────────────────┤
│ 活动 │ 侧边栏      │  主编辑区          │ AI 助手面板        │
│ 栏   │ (240px)     │  (flex-1)          │ (380px, 可折叠)    │
│ (48  │ - 项目树    │                    │ - ChatPanel        │
│ px)  │ - 角色库    │  - 工作流编辑器    │ - 上下文           │
│      │ - 资源      │  - 图像预览        │                    │
│      │             │  - 视频预览        │                    │
├──────┴─────────────┴────────────────────┴───────────────────┤
│ 状态栏 (28px) - WS 状态 + 任务进度 + 额度 + Pro 徽章        │
└─────────────────────────────────────────────────────────────┘
```

**密度参数**：
- 顶部菜单栏：40px（比 32px 更宽松，适合中文显示）
- 状态栏：28px（适中）
- 活动栏：48px（图标 + 间距）
- 侧边栏：240px（适中宽度）
- AI 面板：380px（可折叠）
- 卡片内边距：16px（适中）
- 列表项高度：36-40px（适中点击区域）

#### 17.9.2 响应式断点

```css
--breakpoint-sm: 640px;    /* 手机 */
--breakpoint-md: 768px;    /* 平板 */
--breakpoint-lg: 1024px;   /* 小桌面 */
--breakpoint-xl: 1280px;   /* 桌面（默认） */
--breakpoint-2xl: 1536px;  /* 大桌面 */
```

- `< md`：AI 助手面板隐藏，通过抽屉打开
- `< lg`：侧边栏折叠为图标
- `≥ xl`：完整三栏布局

### 17.10 空状态 / 加载态 / 错误态

**空状态**：
- 使用 lucide 图标 + 简短文案 + CTA 按钮
- 示例：TaskProgressList 空态 = `ClipboardList` 图标 + "暂无运行中任务" + "创建新项目"按钮

**加载态（Skeleton）**：
- 使用 antd `Skeleton` 组件
- 卡片 skeleton：3 行文本 + 圆角矩形
- 列表 skeleton：5 行高度 40px

**错误态**：
- 使用 lucide `AlertCircle` 图标 + 错误文案 + "重试"按钮
- 颜色：`--accent-rose`
- 不使用 alert，使用内联错误提示

### 17.11 浅色/暗色主题切换

**默认主题**：浅色（符合大众习惯）

**实现**：
- 通过 `ConfigProvider` 的 `theme.defaultAlgorithm`（浅色）/ `theme.darkAlgorithm`（暗色）切换
- CSS 变量在 `:root`（浅色默认）和 `[data-theme="dark"]` 下分别定义
- 用户偏好持久化到 `localStorage`（Web）或 `electron-store`（Desktop）
- 切换按钮位置：顶部菜单栏右侧（`Sun` / `Moon` 图标）
- 跟随系统：检测 `prefers-color-scheme: dark` 作为首次访问默认值

**切换交互**：
- 点击图标立即切换，无过渡（避免大面积布局重绘卡顿）
- 切换后 200ms 内 CSS 变量平滑过渡（仅颜色属性）

### 17.12 视觉资源清单

**新增依赖**：
- `lucide-react`（图标库）
- `clsx` + `tailwind-merge`（className 合并，shadcn 生态标准）

**Tailwind 配置扩展**：
- `tailwind.config.js` 新增 `colors.brand` / `colors.accent` / `colors.surface` 命名空间
- 新增 `boxShadow.glow`（焦点环）
- 新增 `animation.pulse-dot`

**CSS 变量文件**：
- 新增 `frontend/src/styles/tokens.css`（所有 CSS 变量定义，含浅色/暗色两套）
- 在 `main.tsx` 中 import

**字体加载**：
- 中文使用系统字体（PingFang SC / Microsoft YaHei），无需 CDN 加载
- 等宽字体 JetBrains Mono 通过 `@fontsource/jetbrains-mono` 本地加载（无 FOUT）

### 17.13 视觉验收标准

- [ ] 所有颜色使用 CSS 变量，不硬编码
- [ ] 所有间距符合 8px grid
- [ ] 所有可交互元素有 hover/active/disabled 三态
- [ ] 所有动画时长在 150-300ms 之间
- [ ] **默认浅色主题**，暗色可一键切换
- [ ] 动画仅使用 `transform` 和 `opacity`，不触发 layout
- [ ] 图标统一使用 lucide-react
- [ ] 空状态、加载态、错误态齐全
- [ ] 在 1280px 桌面 / 768px 平板 / 375px 手机下可用
- [ ] 中文显示清晰（最小字号 12px，行高 1.5+）
- [ ] 主题切换无白屏闪烁（CSS 变量预先定义）
