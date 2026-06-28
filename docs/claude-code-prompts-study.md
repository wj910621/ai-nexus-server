# Claude Code 提示词学习总结

> 来源: https://github.com/Piebald-AI/claude-code-system-prompts (v2.1.191, 2026-06-24)

## 一、核心设计理念

### 1. 模块化提示词架构
Claude Code 不是单一的系统提示词，而是由 **500+ 个独立提示词模块** 组成：
- 条件化注入（根据环境、配置动态添加）
- 工具描述分块（Write、Bash、TodoWrite 等各有独立描述）
- 子 Agent 专用提示词（Explore、Plan、General Purpose 等）
- AI 驱动的工具函数（会话压缩、CLAUDE.md 生成等）

### 2. 通信风格（Communication Style）
```
用户只能看到文本输出，看不到工具调用过程
- 首次工具调用前：一句话说明要做什么
- 工作中：关键节点简短更新（发现什么、转向何处、遇到障碍）
- 结束时：一两句话总结（什么改变了、下一步做什么）
- 代码中：默认不写注释，最多一行简短说明
- 不主动创建文档文件（README、规划文档等）
```

### 3. 安全与操作规范（Action Safety）
```
- 不可逆或对外操作：先确认（除非已获得持久授权）
- 删除/覆盖前：检查目标内容
- 测试失败：如实报告并输出
- 不引入安全漏洞：命令注入、XSS、SQL注入等 OWASP Top 10
```

## 二、Agent 系统架构

### 1. Explore Agent（只读搜索代理）
```
用途：快速定位代码
模型：Haiku（轻量级）
限制：
- Read-only，禁止任何文件修改
- 禁止创建临时文件
- 禁止使用重定向和 heredoc
- 仅限 ls, git status, git log, find, grep 等读操作
```

### 2. General Purpose Agent（通用任务代理）
```
用途：复杂研究、多步任务
特点：
- 搜索、分析、跨文件编辑
- 先广后窄，多策略搜索
- 报告简洁，只说要点
- 避免不必要的文件创建
```

### 3. Plan Mode（计划模式）
```
特点：
- 5 阶段流程：探索→分析→计划→确认→执行
- 用户批准后才执行
- 增强版有更详细的任务分解
```

## 三、关键系统提示词模块

### 1. 任务执行
| 模块 | 描述 |
|------|------|
| `doing-tasks-ambitious-tasks` | 允许用户完成复杂任务，由用户判断范围 |
| `doing-tasks-help-and-feedback` | 提供帮助和反馈渠道 |
| `doing-tasks-no-unnecessary-additions` | 不添加不必要的代码 |
| `doing-tasks-no-unnecessary-error-handling` | 不添加过度错误处理 |
| `prefer-editing-existing-files` | 优先编辑现有文件 |
| `exploratory-questions` | 探索性问题先分析再实施 |

### 2. 安全与信任
| 模块 | 描述 |
|------|------|
| `action-safety-and-truthful-reporting` | 不可逆操作需确认，如实报告结果 |
| `doing-tasks-security` | 避免注入、XSS 等安全漏洞 |
| `censoring-assistance` | 不协助恶意活动 |

### 3. 输出风格
| 模块 | 描述 |
|------|------|
| `emoji-avoidance` | 不使用 emoji（除非用户要求） |
| `tone-and-style-concise-output-short` | 简洁输出，短句优先 |
| `tool-call-colon-avoidance` | 避免工具调用后的冒号 |
| `comment-what-and-task-context-avoidance` | 代码注释简洁 |

### 4. 上下文管理
| 模块 | 描述 |
|------|------|
| `context-compaction-summary` | 会话压缩摘要格式 |
| `memory-instructions` | 记忆系统指令 |
| `team-memory-index-pointer` | 团队记忆索引 |

## 四、Claude Code 的独特设计

### 1. 异步通知机制
```javascript
// Autonomous loop tick
"Run the autonomous check using the loop instructions..."
"Recurring cron will fire the next tick automatically"
```

### 2. 子 Agent 委托
```javascript
// Subagent delegation
"Delegate to specialized agents for specific tasks"
"Report back concisely with findings"
```

### 3. 工作树隔离
```javascript
// Worktree isolation
"Inherited context for worktree sub-agent"
"Working in isolated git worktree"
```

### 4. 权限分类器
```javascript
// Permission classifier
"Strict review guidance for permission decisions"
"Approval doesn't extend to next context"
```

## 五、对 Y·NEX 的启示

### 1. 提示词模块化
当前 Y·NEX 使用单一提示词，应拆分：
- 聊天风格提示词（简洁、专业）
- 小说创作提示词（创意、叙事）
- 代码助手提示词（技术、准确）
- 通用助手提示词

### 2. Agent 能力
应实现：
- [ ] 探索 Agent（只读代码搜索）
- [ ] 通用任务 Agent（多步骤复杂任务）
- [ ] 计划模式（用户确认后再执行）

### 3. 通信规范
- 一句话说清楚要做什么
- 关键节点简短更新
- 结束时简洁总结
- 代码中避免冗余注释

### 4. 安全机制
- 不可逆操作需确认
- 删除前检查内容
- 避免引入安全漏洞

### 5. 记忆系统
- 项目级记忆（CLAUDE.md）
- 用户级记忆（偏好设置）
- 会话级记忆（当前任务状态）

## 六、参考文件清单

| 文件 | Token | 用途 |
|------|-------|------|
| `agent-prompt-explore.md` | 871 | 只读搜索代理 |
| `agent-prompt-plan-mode-enhanced.md` | 715 | 增强计划模式 |
| `agent-prompt-general-purpose.md` | 285 | 通用任务代理 |
| `system-prompt-communication-style.md` | - | 通信风格 |
| `system-prompt-action-safety-and-truthful-reporting.md` | - | 行动安全 |
| `system-prompt-doing-tasks-security.md` | - | 安全规范 |
| `system-prompt-exploratory-questions.md` | - | 探索性问题 |
| `system-prompt-emoji-avoidance.md` | - | Emoji 使用 |
| `system-prompt-prefer-editing-existing-files.md` | - | 文件操作 |
| `skill-debugging.md` | - | 调试技能 |
| `system-prompt-context-compaction-summary.md` | - | 上下文压缩 |

---

*学习时间: 2026-06-25*
*来源仓库: Piebald-AI/claude-code-system-prompts*
