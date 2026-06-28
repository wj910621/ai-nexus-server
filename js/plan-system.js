/**
 * Y·NEX 增强规划系统 v2.0
 * 融合 Codex update_plan + TRAE sequential_thinking
 * 结构化问题解决和任务规划
 */
'use strict';

// ============================================================
// 一、规划状态
// ============================================================
const PlanState = {
  // 当前计划
  currentPlan: null,

  // 计划历史
  history: [],

  // 步骤状态枚举
  STATUS: {
    PENDING: 'pending',
    IN_PROGRESS: 'in_progress',
    COMPLETED: 'completed',
    CANCELLED: 'cancelled',
    DEFERRED: 'deferred'
  }
};

// ============================================================
// 二、步骤类
// ============================================================
class PlanStep {
  constructor(description, options = {}) {
    this.id = `step_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    this.description = description;
    this.status = PlanState.STATUS.PENDING;
    this.createdAt = Date.now();
    this.startedAt = null;
    this.completedAt = null;
    this.result = null;
    this.error = null;
    this.substeps = options.substeps || [];
    this.metadata = options.metadata || {};
  }

  start() {
    this.status = PlanState.STATUS.IN_PROGRESS;
    this.startedAt = Date.now();
  }

  complete(result = null) {
    this.status = PlanState.STATUS.COMPLETED;
    this.completedAt = Date.now();
    this.result = result;
  }

  cancel() {
    this.status = PlanState.STATUS.CANCELLED;
    this.completedAt = Date.now();
  }

  defer() {
    this.status = PlanState.STATUS.DEFERRED;
  }

  fail(error) {
    this.status = PlanState.STATUS.COMPLETED;
    this.completedAt = Date.now();
    this.error = error;
  }

  toJSON() {
    return {
      id: this.id,
      description: this.description,
      status: this.status,
      createdAt: this.createdAt,
      startedAt: this.startedAt,
      completedAt: this.completedAt,
      result: this.result,
      error: this.error,
      substeps: this.substeps,
      metadata: this.metadata
    };
  }
}

// ============================================================
// 三、计划类
// ============================================================
class Plan {
  constructor(title, goal = '') {
    this.id = `plan_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    this.title = title;
    this.goal = goal;
    this.steps = [];
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
    this.completedAt = null;
    this.currentStepIndex = -1;
    this.metadata = {};
  }

  /**
   * 添加步骤
   */
  addStep(description, options = {}) {
    const step = new PlanStep(description, options);
    this.steps.push(step);
    this.updatedAt = Date.now();
    return step;
  }

  /**
   * 获取当前步骤
   */
  getCurrentStep() {
    return this.steps[this.currentStepIndex] || null;
  }

  /**
   * 获取下一个待处理步骤
   */
  getNextPendingStep() {
    return this.steps.find(s => s.status === PlanState.STATUS.PENDING);
  }

  /**
   * 推进到下一步
   */
  advanceToNext() {
    // 完成当前步骤
    const current = this.getCurrentStep();
    if (current && current.status === PlanState.STATUS.IN_PROGRESS) {
      current.complete();
    }

    // 找到下一个待处理步骤
    const next = this.getNextPendingStep();
    if (next) {
      const index = this.steps.indexOf(next);
      this.currentStepIndex = index;
      next.start();
      this.updatedAt = Date.now();
      return next;
    }

    return null;
  }

  /**
   * 标记当前步骤完成
   */
  completeCurrentStep(result = null) {
    const current = this.getCurrentStep();
    if (current) {
      current.complete(result);
      this.updatedAt = Date.now();
    }
  }

  /**
   * 标记当前步骤失败
   */
  failCurrentStep(error) {
    const current = this.getCurrentStep();
    if (current) {
      current.fail(error);
      this.updatedAt = Date.now();
    }
  }

  /**
   * 检查计划是否完成
   */
  isComplete() {
    return this.steps.every(s =>
      s.status === PlanState.STATUS.COMPLETED ||
      s.status === PlanState.STATUS.CANCELLED ||
      s.status === PlanState.STATUS.DEFERRED
    );
  }

  /**
   * 获取完成百分比
   */
  getProgress() {
    if (this.steps.length === 0) return 0;
    const completed = this.steps.filter(s =>
      s.status === PlanState.STATUS.COMPLETED ||
      s.status === PlanState.STATUS.CANCELLED
    ).length;
    return Math.round((completed / this.steps.length) * 100);
  }

  /**
   * 生成文本表示
   */
  toText() {
    let text = `# ${this.title}\n\n`;
    text += `目标: ${this.goal}\n\n`;

    this.steps.forEach((step, i) => {
      const statusIcon = {
        pending: '⏳',
        in_progress: '🔄',
        completed: '✅',
        cancelled: '❌',
        deferred: '⏸️'
      }[step.status];

      const prefix = step.status === PlanState.STATUS.IN_PROGRESS ? '→ ' : '  ';
      text += `${prefix}${i + 1}. ${statusIcon} ${step.description}`;

      if (step.result) {
        text += `\n   结果: ${step.result}`;
      }
      if (step.error) {
        text += `\n   错误: ${step.error}`;
      }
      text += '\n';
    });

    text += `\n进度: ${this.getProgress()}%`;
    return text;
  }

  /**
   * 生成 Markdown 表示
   */
  toMarkdown() {
    let md = `## ${this.title}\n\n`;
    md += `**目标:** ${this.goal}\n\n`;
    md += `**进度:** ${this.getProgress()}%\n\n`;
    md += '---\n\n';

    this.steps.forEach((step, i) => {
      const statusIcon = {
        pending: '⏳',
        in_progress: '🔄',
        completed: '✅',
        cancelled: '❌',
        deferred: '⏸️'
      }[step.status];

      const statusColor = {
        pending: '#9ca3af',
        in_progress: '#3b82f6',
        completed: '#10b981',
        cancelled: '#ef4444',
        deferred: '#f59e0b'
      }[step.status];

      md += `### ${i + 1}. ${statusIcon} ${step.description}\n`;
      md += `<span style="color:${statusColor}">[${step.status}]</span>\n\n`;

      if (step.result) {
        md += `**结果:** ${step.result}\n\n`;
      }
      if (step.error) {
        md += `**错误:** ${step.error}\n\n`;
      }
    });

    return md;
  }

  toJSON() {
    return {
      id: this.id,
      title: this.title,
      goal: this.goal,
      steps: this.steps.map(s => s.toJSON()),
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      completedAt: this.completedAt,
      progress: this.getProgress(),
      isComplete: this.isComplete()
    };
  }
}

// ============================================================
// 四、规划管理器
// ============================================================
const PlanManager = {
  /**
   * 创建新计划
   */
  create(title, goal = '') {
    const plan = new Plan(title, goal);
    PlanState.currentPlan = plan;
    PlanState.history.push(plan);
    return plan;
  },

  /**
   * 从文本解析计划
   * 支持格式:
   * 1. 按行号: "1. 步骤1\n2. 步骤2"
   * 2. Markdown: "## 计划\n- 步骤1\n- 步骤2"
   */
  parse(text) {
    const lines = text.split('\n').filter(l => l.trim());
    const plan = new Plan('解析的计划');

    // 尝试解析标题
    const titleMatch = text.match(/^#+\s*(.+)/m);
    if (titleMatch) {
      plan.title = titleMatch[1].trim();
    }

    // 解析步骤
    const stepPattern = /^[-\d.]\s*(.+)/;
    for (const line of lines) {
      const match = line.match(stepPattern);
      if (match) {
        plan.addStep(match[1].trim());
      }
    }

    PlanState.currentPlan = plan;
    return plan;
  },

  /**
   * 添加步骤到当前计划
   */
  addStep(description, options = {}) {
    if (!PlanState.currentPlan) {
      this.create('新计划');
    }
    return PlanState.currentPlan.addStep(description, options);
  },

  /**
   * 开始执行计划
   */
  start() {
    if (!PlanState.currentPlan) return null;

    const next = PlanState.currentPlan.getNextPendingStep();
    if (next) {
      const index = PlanState.currentPlan.steps.indexOf(next);
      PlanState.currentPlan.currentStepIndex = index;
      next.start();
    }
    return next;
  },

  /**
   * 完成当前步骤
   */
  completeStep(result = null) {
    if (!PlanState.currentPlan) return;

    PlanState.currentPlan.completeCurrentStep(result);

    // 检查是否完成
    if (PlanState.currentPlan.isComplete()) {
      PlanState.currentPlan.completedAt = Date.now();
    }
  },

  /**
   * 完成计划
   */
  complete(summary = '') {
    if (!PlanState.currentPlan) return;

    // 完成所有未完成的步骤
    PlanState.currentPlan.steps.forEach(s => {
      if (s.status === PlanState.STATUS.IN_PROGRESS) {
        s.complete(summary);
      } else if (s.status === PlanState.STATUS.PENDING) {
        s.cancel();
      }
    });

    PlanState.currentPlan.completedAt = Date.now();
    PlanState.currentPlan = null;
  },

  /**
   * 取消计划
   */
  cancel() {
    if (!PlanState.currentPlan) return;

    PlanState.currentPlan.steps.forEach(s => s.cancel());
    PlanState.currentPlan = null;
  },

  /**
   * 获取当前计划
   */
  getCurrentPlan() {
    return PlanState.currentPlan;
  },

  /**
   * 获取计划历史
   */
  getHistory() {
    return PlanState.history;
  }
};

// ============================================================
// 五、顺序思考工具（TRAE 风格）
// ============================================================
const SequentialThinking = {
  // 思考历史
  thoughts: [],

  /**
   * 添加思考
   */
  addThought(thought, options = {}) {
    const thoughtObj = {
      id: `thought_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      thought,
      number: this.thoughts.length + 1,
      totalThoughts: options.totalThoughts || 10,
      nextThoughtNeeded: options.nextThoughtNeeded !== false,
      isRevision: options.isRevision || false,
      revisesThought: options.revisesThought || null,
      branchFromThought: options.branchFromThought || null,
      branchId: options.branchId || null,
      timestamp: Date.now(),
      metadata: options.metadata || {}
    };

    this.thoughts.push(thoughtObj);
    return thoughtObj;
  },

  /**
   * 修订之前的思考
   */
  revise(thoughtId, newThought) {
    const thought = this.thoughts.find(t => t.id === thoughtId);
    if (!thought) return null;

    return this.addThought(newThought, {
      isRevision: true,
      revisesThought: thoughtId,
      nextThoughtNeeded: true
    });
  },

  /**
   * 分支思考
   */
  branch(thoughtId, newThought, branchName) {
    const thought = this.thoughts.find(t => t.id === thoughtId);
    if (!thought) return null;

    const branchId = `branch_${Date.now()}`;

    return this.addThought(newThought, {
      branchFromThought: thoughtId,
      branchId,
      nextThoughtNeeded: true,
      metadata: { branchName }
    });
  },

  /**
   * 结束思考
   */
  conclude(finalThought = '') {
    if (finalThought) {
      this.addThought(finalThought, { nextThoughtNeeded: false });
    }

    const conclusion = this.generateConclusion();
    this.thoughts = []; // 清空，准备下一次思考
    return conclusion;
  },

  /**
   * 生成结论
   */
  generateConclusion() {
    if (this.thoughts.length === 0) {
      return { summary: '', keyInsights: [], nextSteps: [] };
    }

    // 提取关键洞察
    const insights = this.thoughts
      .filter(t => t.thought.includes('发现') || t.thought.includes('关键') || t.thought.includes('洞察'))
      .map(t => t.thought)
      .slice(0, 3);

    // 提取下一步
    const nextSteps = this.thoughts
      .filter(t => t.nextThoughtNeeded === false || t === this.thoughts[this.thoughts.length - 1])
      .map(t => t.thought)
      .slice(0, 2);

    return {
      summary: this.thoughts.map(t => t.thought).join('\n\n'),
      keyInsights: insights,
      nextSteps
    };
  },

  /**
   * 获取思考历史
   */
  getHistory() {
    return this.thoughts;
  },

  /**
   * 导出为 Markdown
   */
  toMarkdown() {
    if (this.thoughts.length === 0) return '';

    let md = '## 思考过程\n\n';

    for (const thought of this.thoughts) {
      const prefix = thought.isRevision ? '↩️ ' : thought.branchId ? '🔀 ' : '';
      md += `**${thought.number}/${thought.totalThoughts}** ${prefix}${thought.thought}\n\n`;

      if (thought.metadata.branchName) {
        md += `> 分支: ${thought.metadata.branchName}\n\n`;
      }
    }

    const conclusion = this.generateConclusion();
    if (conclusion.keyInsights.length > 0) {
      md += '---\n\n## 关键洞察\n\n';
      conclusion.keyInsights.forEach((insight, i) => {
        md += `${i + 1}. ${insight}\n`;
      });
      md += '\n';
    }

    return md;
  }
};

// ============================================================
// 六、导出
// ============================================================
window.PlanSystem = {
  Plan,
  PlanStep,
  Manager: PlanManager,
  Thinking: SequentialThinking,

  // 便捷方法
  createPlan: (title, goal) => PlanManager.create(title, goal),
  parsePlan: (text) => PlanManager.parse(text),
  addStep: (desc, opts) => PlanManager.addStep(desc, opts),
  startPlan: () => PlanManager.start(),
  completeStep: (result) => PlanManager.completeStep(result),
  completePlan: (summary) => PlanManager.complete(summary),
  cancelPlan: () => PlanManager.cancel(),
  getCurrentPlan: () => PlanManager.getCurrentPlan(),
  think: (thought, opts) => SequentialThinking.addThought(thought, opts),
  revise: (id, thought) => SequentialThinking.revise(id, thought),
  branch: (id, thought, name) => SequentialThinking.branch(id, thought, name),
  conclude: (final) => SequentialThinking.conclude(final),
  getThoughts: () => SequentialThinking.getHistory(),
  planToMarkdown: () => PlanState.currentPlan ? PlanState.currentPlan.toMarkdown() : '',
  planToText: () => PlanState.currentPlan ? PlanState.currentPlan.toText() : ''
};
