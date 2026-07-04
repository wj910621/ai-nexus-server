/**
 * Y·NEX Desktop — Multi-Agent Orchestrator
 * 多 Agent 协作系统，支持角色分工、任务分配和协作执行
 */

const EventEmitter = require('events');

// ============================================================
// Agent 角色
// ============================================================

const AGENT_ROLES = {
  COORDINATOR: 'coordinator',   // 协调者 - 分配任务、汇总结果
  RESEARCHER: 'researcher',     // 研究员 - 搜索信息、收集数据
  CODER: 'coder',               // 程序员 - 编写代码、调试
  WRITER: 'writer',             // 写手 - 生成文档、报告
  REVIEWER: 'reviewer',         // 审核员 - 检查质量、反馈建议
  EXECUTOR: 'executor',         // 执行者 - 调用工具、执行操作
};

const ROLE_DESCRIPTIONS = {
  coordinator: '负责协调团队，分配任务，汇总各成员结果',
  researcher: '负责搜索信息，收集相关数据和背景资料',
  coder: '负责编写代码，实现技术方案，调试问题',
  writer: '负责生成文档，撰写报告，整理输出内容',
  reviewer: '负责审核质量，检查结果，提供改进建议',
  executor: '负责调用工具，执行具体操作和处理任务',
};

// ============================================================
// Agent 成员
// ============================================================

class AgentMember {
  constructor(config) {
    this.id = config.id || `agent_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.name = config.name || 'Agent';
    this.role = config.role || AGENT_ROLES.EXECUTOR;
    this.model = config.model || 'deepseekv3';
    this.capabilities = config.capabilities || [];
    this.status = 'idle'; // idle | working | completed | error
    this.currentTask = null;
    this.history = [];
    this.tools = config.tools || [];
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      role: this.role,
      model: this.model,
      capabilities: this.capabilities,
      status: this.status,
      currentTask: this.currentTask,
      historyCount: this.history.length,
    };
  }
}

// ============================================================
// Agent 团队
// ============================================================

class AgentTeam {
  constructor(config) {
    this.id = config.id || `team_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.name = config.name || 'Agent 团队';
    this.description = config.description || '';
    this.members = new Map(); // id -> AgentMember
    this.tasks = new Map();   // id -> Task
    this.results = new Map(); // taskId -> result
    this.status = 'idle';     // idle | planning | executing | completed | error
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
  }

  addMember(memberConfig) {
    const member = new AgentMember(memberConfig);
    this.members.set(member.id, member);
    this.updatedAt = Date.now();
    return member;
  }

  removeMember(memberId) {
    this.members.delete(memberId);
    this.updatedAt = Date.now();
    return true;
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      description: this.description,
      members: Array.from(this.members.values()).map(m => m.toJSON()),
      status: this.status,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    };
  }

  static fromJSON(data) {
    const team = new AgentTeam({
      id: data.id,
      name: data.name,
      description: data.description,
    });
    team.status = data.status || 'idle';
    team.createdAt = data.createdAt;
    team.updatedAt = data.updatedAt;

    for (const memberData of data.members || []) {
      team.addMember(memberData);
    }

    return team;
  }
}

// ============================================================
// 多 Agent 协调器
// ============================================================

class MultiAgentOrchestrator extends EventEmitter {
  constructor(toolRegistry, llmClient) {
    super();
    this.toolRegistry = toolRegistry;
    this.llmClient = llmClient;
    this.teams = new Map(); // id -> AgentTeam
  }

  // ============================================================
  // 团队管理
  // ============================================================

  createTeam(config) {
    const team = new AgentTeam(config);
    this.teams.set(team.id, team);
    this.emit('team:created', team);
    return team;
  }

  getTeam(id) {
    return this.teams.get(id);
  }

  listTeams() {
    return Array.from(this.teams.values()).map(team => ({
      id: team.id,
      name: team.name,
      description: team.description,
      memberCount: team.members.size,
      status: team.status,
      updatedAt: team.updatedAt,
    }));
  }

  deleteTeam(id) {
    const team = this.teams.get(id);
    if (!team) return false;
    this.teams.delete(id);
    this.emit('team:deleted', id);
    return true;
  }

  saveTeam(id) {
    const team = this.teams.get(id);
    if (!team) return null;
    return team.toJSON();
  }

  loadTeam(data) {
    const team = AgentTeam.fromJSON(data);
    this.teams.set(team.id, team);
    this.emit('team:loaded', team);
    return team;
  }

  // ============================================================
  // 预设团队模板
  // ============================================================

  createPresetTeam(type) {
    const presets = {
      'dev_team': {
        name: '开发团队',
        description: '负责软件开发任务的团队',
        members: [
          { name: '项目经理', role: 'coordinator', capabilities: ['任务分配', '进度跟踪'] },
          { name: '研究员', role: 'researcher', capabilities: ['技术调研', '方案分析'] },
          { name: '程序员', role: 'coder', capabilities: ['代码编写', '调试'] },
          { name: '审核员', role: 'reviewer', capabilities: ['代码审查', '质量检查'] },
        ]
      },
      'content_team': {
        name: '内容创作团队',
        description: '负责内容创作和文档生成',
        members: [
          { name: '主编', role: 'coordinator', capabilities: ['内容规划', '风格把控'] },
          { name: '研究员', role: 'researcher', capabilities: ['资料收集', '素材整理'] },
          { name: '写手', role: 'writer', capabilities: ['撰写', '排版'] },
          { name: '审核员', role: 'reviewer', capabilities: ['校对', '优化'] },
        ]
      },
      'research_team': {
        name: '研究团队',
        description: '负责研究和分析的团队',
        members: [
          { name: '组长', role: 'coordinator', capabilities: ['研究方向', '资源调配'] },
          { name: '研究员A', role: 'researcher', capabilities: ['数据收集', '文献检索'] },
          { name: '研究员B', role: 'researcher', capabilities: ['数据分析', '模型构建'] },
          { name: '写手', role: 'writer', capabilities: ['报告撰写', '图表制作'] },
        ]
      },
      'automation_team': {
        name: '自动化执行团队',
        description: '负责自动化执行任务的团队',
        members: [
          { name: '指挥官', role: 'coordinator', capabilities: ['任务调度', '错误处理'] },
          { name: '执行者A', role: 'executor', capabilities: ['工具调用', '数据处理'] },
          { name: '执行者B', role: 'executor', capabilities: ['API调用', '文件操作'] },
          { name: '审核员', role: 'reviewer', capabilities: ['结果验证', '异常捕获'] },
        ]
      }
    };

    const preset = presets[type];
    if (!preset) return null;

    const team = this.createTeam({
      name: preset.name,
      description: preset.description,
    });

    for (const memberConfig of preset.members) {
      team.addMember(memberConfig);
    }

    return team;
  }

  // ============================================================
  // 任务执行
  // ============================================================

  async runTask(teamId, task) {
    const team = this.teams.get(teamId);
    if (!team) {
      return { ok: false, error: '团队不存在' };
    }

    // 找到协调者
    const coordinator = this._findCoordinator(team);
    if (!coordinator) {
      return { ok: false, error: '团队缺少协调者角色' };
    }

    team.status = 'planning';
    this.emit('team:task_started', { teamId, task });

    try {
      // Phase 1: 协调者分析任务并分配
      const plan = await this._planTask(coordinator, task, team);
      
      team.status = 'executing';
      this.emit('team:plan_created', { teamId, plan });

      // Phase 2: 各成员执行分配的任务
      const results = await this._executePlan(team, plan);

      // Phase 3: 协调者汇总结果
      const finalResult = await this._summarizeResults(coordinator, results, task);

      team.status = 'completed';
      this.emit('team:task_completed', { teamId, result: finalResult });

      return {
        ok: true,
        result: finalResult,
        plan,
        memberResults: results,
      };
    } catch (e) {
      team.status = 'error';
      this.emit('team:task_error', { teamId, error: e.message });
      return { ok: false, error: e.message };
    }
  }

  async _planTask(coordinator, task, team) {
    // 构建任务分配提示
    const members = Array.from(team.members.values());
    const memberInfo = members.map(m => 
      `- ${m.name} (${m.role}): ${ROLE_DESCRIPTIONS[m.role]}`
    ).join('\n');

    const prompt = `
你是一个团队协调者，负责分析任务并分配给团队成员。

任务: ${task}

团队成员:
${memberInfo}

请分析任务，并为每个成员分配具体子任务。输出格式如下：
{
  "analysis": "任务分析...",
  "subtasks": [
    { "member": "成员名称", "task": "分配的子任务描述" },
    ...
  ],
  "expectedOutput": "期望的输出格式"
}

请只输出 JSON，不要有其他内容。
`;

    // 调用 LLM 进行任务规划
    const response = await this._callLLM(coordinator.model, prompt);
    
    try {
      // 解析 JSON
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (e) {
      // 解析失败，返回默认分配
      return {
        analysis: '无法解析任务，使用默认分配',
        subtasks: members.map(m => ({
          member: m.name,
          task: `${ROLE_DESCRIPTIONS[m.role]}，协助完成主任务`
        })),
        expectedOutput: '完成任务'
      };
    }

    return {
      analysis: response,
      subtasks: [],
      expectedOutput: '完成任务'
    };
  }

  async _executePlan(team, plan) {
    const results = [];

    for (const subtask of plan.subtasks || []) {
      const member = this._findMemberByName(team, subtask.member);
      if (!member) continue;

      member.status = 'working';
      member.currentTask = subtask.task;
      this.emit('member:task_started', { memberId: member.id, task: subtask.task });

      try {
        const result = await this._executeMemberTask(member, subtask.task, plan);
        member.status = 'completed';
        member.history.push({ task: subtask.task, result, time: Date.now() });
        
        results.push({
          member: member.name,
          role: member.role,
          task: subtask.task,
          result,
          status: 'success'
        });

        this.emit('member:task_completed', { memberId: member.id, result });
      } catch (e) {
        member.status = 'error';
        results.push({
          member: member.name,
          role: member.role,
          task: subtask.task,
          error: e.message,
          status: 'error'
        });

        this.emit('member:task_error', { memberId: member.id, error: e.message });
      }
    }

    return results;
  }

  async _executeMemberTask(member, task, plan) {
    const prompt = `
你是${member.name}，角色是${member.role}。
${ROLE_DESCRIPTIONS[member.role]}

团队任务背景:
${plan.analysis}

你的具体任务:
${task}

请完成你的任务并输出结果。如果需要调用工具，请说明需要什么工具。
`;

    const response = await this._callLLM(member.model, prompt);

    // 检查是否需要调用工具
    const toolCalls = this._extractToolCalls(response);
    if (toolCalls.length > 0 && this.toolRegistry) {
      const toolResults = [];
      for (const call of toolCalls) {
        try {
          const result = await this.toolRegistry.callTool(call.tool, call.args || {}, {});
          toolResults.push({ tool: call.tool, result });
        } catch (e) {
          toolResults.push({ tool: call.tool, error: e.message });
        }
      }
      return { response, toolResults };
    }

    return { response };
  }

  async _summarizeResults(coordinator, results, originalTask) {
    const resultSummary = results.map(r => 
      `【${r.member}(${r.role})】任务: ${r.task}\n结果: ${r.status === 'success' ? JSON.stringify(r.result).substring(0, 500) : '错误: ' + r.error}`
    ).join('\n\n');

    const prompt = `
你是团队协调者，负责汇总各成员的工作结果。

原始任务: ${originalTask}

各成员执行结果:
${resultSummary}

请汇总这些结果，生成最终输出。格式清晰、内容完整。
`;

    const response = await this._callLLM(coordinator.model, prompt);
    return response;
  }

  // ============================================================
  // 辅助方法
  // ============================================================

  _findCoordinator(team) {
    for (const member of team.members.values()) {
      if (member.role === AGENT_ROLES.COORDINATOR) {
        return member;
      }
    }
    // 如果没有协调者，返回第一个成员
    return team.members.values().next().value;
  }

  _findMemberByName(team, name) {
    for (const member of team.members.values()) {
      if (member.name === name) {
        return member;
      }
    }
    return null;
  }

  async _callLLM(model, prompt) {
    if (!this.llmClient) {
      return 'LLM 客户端未初始化，无法执行任务';
    }

    try {
      const response = await this.llmClient.chat({
        messages: [{ role: 'user', content: prompt }],
        model
      });
      return response?.content || response?.answer || '';
    } catch (e) {
      return `LLM 调用失败: ${e.message}`;
    }
  }

  _extractToolCalls(response) {
    // 提取工具调用请求（简单模式）
    const toolPattern = /\[工具:(\w+)\]|\{tool:\s*"(\w+)"\}/g;
    const calls = [];
    let match;
    
    while ((match = toolPattern.exec(response)) !== null) {
      calls.push({ tool: match[1] || match[2], args: {} });
    }
    
    return calls;
  }
}

module.exports = {
  MultiAgentOrchestrator,
  AgentTeam,
  AgentMember,
  AGENT_ROLES,
  ROLE_DESCRIPTIONS,
};