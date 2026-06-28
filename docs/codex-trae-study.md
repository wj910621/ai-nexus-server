# Codex & TRAE Agent 源码学习总结

> 学习时间: 2026-06-25
> 来源仓库:
> - OpenAI Codex: https://github.com/openai/codex (67K+ stars)
> - TRAE Agent: https://github.com/bytedance/trae-agent (11K+ stars, MIT)

---

## 一、Codex CLI 架构分析

### 1.1 核心架构（Rust 重写版）

```
codex-rs/
├── core/           # 核心 Agent 逻辑
├── cli/            # 命令行接口
├── tui/            # 终端 UI
├── prompts/        # 提示词系统
├── tools/          # 工具集
├── model-provider/ # 模型路由
├── memories/       # 记忆系统
├── thread-store/   # 会话持久化
├── sandboxing/     # 沙箱隔离
│   ├── bwrap/      # Linux Bubblewrap
│   ├── linux-sandbox/
│   └── windows-sandbox-rs/
├── exec/           # 命令执行
├── execpolicy/     # 执行策略
├── mcp-server/     # MCP 协议
└── skills/         # 技能系统
```

### 1.2 关键设计：Thread 会话模型

```rust
// Codex 使用 SQLite 持久化会话
Thread     // 持久化对话，可恢复/分叉/归档
  └── Turn // 一次往返：用户输入 → 模型推理 → 工具调用 → 结果
        └── Item // Turn 内的细粒度事件
```

**与 Claude Code 的关键区别：**
- Codex 有内置的跨会话持久化
- Claude Code 无内置跨会话记忆

### 1.3 工具系统

| 工具 | 功能 |
|------|------|
| `shell` | 沙箱化 shell 执行 |
| `apply_patch` | 结构化文件编辑（Lark 语法解析） |
| `js_repl` | 持久化 Node.js REPL |
| `list_dir` | 分页目录列表 |
| `view_image` | 多模态图像查看 |
| `tool_search` | BM25 语义搜索工具 |
| `spawn_agent` | 层级多 Agent 派生 |
| `request_permissions` | 运行时权限升级 |
| `web_search` | 实时网络搜索 |

### 1.4 沙箱安全架构（重点！）

**Linux: Bubblewrap**
```
用户空间 → Bubblewrap → 内核系统调用
            ↓
      限制文件系统、网络、进程
```

**Windows: Windows Sandbox API**

**Codex 的安全策略：**
1. 默认禁止危险操作
2. 用户审批机制
3. 权限分级（trusted/untrusted/on-request）
4. 沙箱隔离执行

### 1.5 GPT-5 Codex Prompt 核心内容

```markdown
## 通信风格
- 简洁、直接、友好
- 高效沟通，不过多细节
- 优先行动导向

## 自主性
- 持续直到任务完全解决
- 不停在分析或部分修复
- 除非用户明确暂停

## 响应规范
- 首次工具调用前给快速计划
- 工作中分享有意义的发现
- 改变计划时明确说明

## 规划工具使用
- 简单任务不使用规划（~25%）
- 不做单步计划
- 完成后更新计划

## 文件编辑
- 使用 apply_patch 工具
- 最小化变更
- 保持与现有代码风格一致

## 安全约束
- 不使用 git reset --hard（除非明确要求）
- 不修改未请求的内容
- 发现意外变更立即停止询问
```

---

## 二、TRAE Agent 架构分析

### 2.1 核心架构（Python）

```
trae_agent/
├── agent/
│   ├── agent.py          # Agent 入口
│   ├── trae_agent.py     # 主 Agent 实现
│   ├── base_agent.py     # 基类
│   └── docker_manager.py # Docker 管理
├── tools/
│   ├── bash_tool.py      # Bash 执行
│   ├── edit_tool.py      # 文件编辑
│   ├── json_edit_tool.py # JSON 编辑
│   ├── sequential_thinking_tool.py # 思维链
│   ├── ckg_tool.py       # 代码知识图谱
│   └── mcp_tool.py       # MCP 集成
├── prompt/
│   └── agent_prompt.py   # Agent 提示词
└── utils/
    ├── llm_clients/      # 多模型支持
    └── trajectory_recorder.py # 轨迹记录
```

### 2.2 Agent System Prompt

```python
TRAE_AGENT_SYSTEM_PROMPT = """You are an expert AI software engineering agent.

# 路径规则
所有 file_path 参数必须是绝对路径

# 方法论步骤
1. 理解问题 - 仔细阅读问题描述
2. 探索定位 - 使用工具探索代码库
3. 复现 Bug - 创建复现脚本（关键！）
4. 调试诊断 - 追踪执行流程
5. 开发修复 - 精准修改
6. 验证测试 - 运行测试防止回归
7. 总结工作 - 清晰简洁总结

# 指导原则
像高级工程师一样行动。优先考虑正确性、安全性和高质量测试驱动开发。

# sequential_thinking 使用
- 复杂问题至少 5-25 个思考步骤
- 可以在思考之间运行 bash 命令
- 用于分解问题、逐步分析
"""
```

### 2.3 五大内置工具

| 工具 | 功能 |
|------|------|
| `str_replace_based_edit_tool` | 文件操作（view/create/str_replace/insert） |
| `bash` | 持久化 shell 会话（120秒超时） |
| `sequential_thinking` | 结构化思维链（分支、修订） |
| `task_done` | 任务完成信号 |
| `json_edit_tool` | JSONPath 精确编辑 |

### 2.4 多模型支持（Provider-Agnostic）

```python
# 支持的模型提供商
- OpenAI (GPT-4, o1, o3)
- Anthropic (Claude 3.5, 4)
- Google (Gemini)
- Azure OpenAI
- Doubao (字节豆包)
- Ollama (本地模型)
- OpenRouter
```

**架构优势：**
- 统一接口
- 易于扩展新提供商
- 支持模型对比

### 2.5 Patch Selection 机制

```
多模型生成 Patch → 回归测试过滤 → 选择器 Agent 最终选择
                                      ↓
                              语法等价聚类 + 多 Agent 验证
```

**SWE-bench Verified 得分：75.2%（第一）**

---

## 三、关键设计对比

| 特性 | Codex CLI | TRAE Agent | Claude Code |
|------|-----------|------------|-------------|
| 语言 | Rust (~97%) | Python | 未开源 |
| 会话持久化 | SQLite Thread | 无 | 无 |
| 沙箱 | Bubblewrap/Win | Docker/Host | Sandboxed |
| 工具系统 | MCP + 内置 | 内置 + MCP | 内置 |
| 多模型 | Responses API | Provider-Agnostic | Claude Only |
| 规划 | update_plan | sequential_thinking | 5 阶段模式 |
| 记忆 | Memories + Thread | trajectory_recorder | 无内置 |

---

## 四、对 Y·NEX 的启示

### 4.1 紧急需要实现的功能

1. **沙箱隔离执行**
   - Codex 的 Bubblewrap 是 Linux 标准
   - Windows 需要类似隔离机制
   - 当前 Y·NEX 缺乏命令执行安全

2. **会话持久化**
   - Codex Thread 模型值得借鉴
   - SQLite 存储会话历史
   - 支持会话恢复和分叉

3. **执行策略系统**
   - 危险操作自动拦截
   - 用户审批机制
   - 权限分级控制

4. **apply_patch 工具**
   - Lark 语法解析
   - 结构化编辑验证
   - 比字符串替换更安全

### 4.2 提示词设计借鉴

**Codex 通信规范：**
```
- 首次行动前：快速计划（目标 + 约束 + 下一步）
- 工作中：分享有意义发现
- 重大变更：提前告知用户
- 结束：简洁总结 + 建议下一步
```

**TRAE Agent 方法论：**
```
1. 理解问题
2. 探索定位
3. 复现 Bug（关键！）
4. 调试诊断
5. 开发修复
6. 验证测试
7. 总结工作
```

### 4.3 架构建议

```
Y·NEX 2.0 架构
├── core/
│   ├── agent/           # Agent 核心
│   ├── tools/            # 工具系统
│   ├── sandbox/          # 沙箱隔离
│   ├── memory/           # 记忆系统
│   └── session/          # 会话持久化
├── prompts/
│   ├── system/           # 系统提示词
│   ├── skills/           # 技能定义
│   └── agents_md/        # 项目级指令
└── providers/
    ├── openai/
    ├── anthropic/
    └── ...               # 多模型支持
```

---

## 五、优先实施计划

### Phase 1: 安全隔离（高优先级）
- [ ] 实现命令执行沙箱
- [ ] 危险操作自动拦截
- [ ] 用户审批机制

### Phase 2: 会话管理
- [ ] SQLite 会话持久化
- [ ] 会话恢复和分叉
- [ ] 轨迹记录

### Phase 3: 工具系统
- [ ] apply_patch 结构化编辑
- [ ] 文件版本控制
- [ ] MCP 集成

### Phase 4: 提示词优化
- [ ] 通信风格规范化
- [ ] 规划模式增强
- [ ] 项目级 AGENTS.md

---

## 六、参考文件清单

### Codex
| 文件 | 内容 |
|------|------|
| `codex-rs/core/gpt_5_codex_prompt.md` | GPT-5 Codex 提示词 |
| `codex-rs/core/gpt_5_1_prompt.md` | GPT-5.1 完整提示词 |
| `docs/execpolicy.md` | 执行策略文档 |
| `docs/sandbox.md` | 沙箱安全文档 |
| `docs/skills.md` | 技能系统文档 |

### TRAE Agent
| 文件 | 内容 |
|------|------|
| `trae_agent/prompt/agent_prompt.py` | Agent 提示词 |
| `trae_agent/agent/agent.py` | Agent 入口 |
| `trae_agent/tools/bash_tool.py` | Bash 工具 |
| `trae_agent/tools/edit_tool.py` | 编辑工具 |
| `docs/tools.md` | 工具文档 |

---

*本总结基于 2026-06-25 的源码分析，版本可能已更新*
