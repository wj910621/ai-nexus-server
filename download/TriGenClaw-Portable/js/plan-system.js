/**
 * TriGenClaw 桌面端规划系统 v2.0
 * 融合 Codex update_plan + TRAE sequential_thinking
 */
'use strict';

// ============================================================
// 一、简化版规划系统
// ============================================================
var DesktopPlan = {
  current: null,
  history: [],

  /**
   * 创建计划
   */
  create: function(title, goal) {
    this.current = {
      id: 'plan_' + Date.now(),
      title: title || '新计划',
      goal: goal || '',
      steps: [],
      created: Date.now(),
      updated: Date.now()
    };
    this.history.push(this.current);
    return this.current;
  },

  /**
   * 添加步骤
   */
  addStep: function(description) {
    if (!this.current) this.create();

    var step = {
      id: 'step_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
      description: description,
      status: 'pending',
      created: Date.now(),
      completed: null,
      result: null
    };

    this.current.steps.push(step);
    this.current.updated = Date.now();
    return step;
  },

  /**
   * 完成当前步骤
   */
  completeStep: function(stepId, result) {
    if (!this.current) return;

    for (var i = 0; i < this.current.steps.length; i++) {
      var step = this.current.steps[i];
      if (step.id === stepId) {
        step.status = 'completed';
        step.completed = Date.now();
        step.result = result;
        break;
      }
    }

    this.current.updated = Date.now();
  },

  /**
   * 标记失败
   */
  failStep: function(stepId, error) {
    if (!this.current) return;

    for (var i = 0; i < this.current.steps.length; i++) {
      var step = this.current.steps[i];
      if (step.id === stepId) {
        step.status = 'failed';
        step.completed = Date.now();
        step.error = error;
        break;
      }
    }

    this.current.updated = Date.now();
  },

  /**
   * 完成计划
   */
  complete: function(summary) {
    if (!this.current) return;

    this.current.completed = Date.now();
    this.current.summary = summary;
    this.current = null;
  },

  /**
   * 取消计划
   */
  cancel: function() {
    this.current = null;
  },

  /**
   * 获取进度
   */
  getProgress: function() {
    if (!this.current || this.current.steps.length === 0) return 0;

    var completed = 0;
    for (var i = 0; i < this.current.steps.length; i++) {
      if (this.current.steps[i].status === 'completed') {
        completed++;
      }
    }

    return Math.round((completed / this.current.steps.length) * 100);
  },

  /**
   * 转为文本
   */
  toText: function() {
    if (!this.current) return '';

    var text = '# ' + this.current.title + '\n\n';
    text += '目标: ' + this.current.goal + '\n\n';

    for (var i = 0; i < this.current.steps.length; i++) {
      var step = this.current.steps[i];
      var icon = {
        pending: '[ ]',
        in_progress: '[>]',
        completed: '[x]',
        failed: '[!]'
      }[step.status] || '[ ]';

      text += icon + ' ' + (i + 1) + '. ' + step.description;
      if (step.result) {
        text += '\n   → ' + step.result;
      }
      if (step.error) {
        text += '\n   ✗ ' + step.error;
      }
      text += '\n';
    }

    text += '\n进度: ' + this.getProgress() + '%';
    return text;
  }
};

// ============================================================
// 二、顺序思考系统
// ============================================================
var DesktopThinking = {
  thoughts: [],

  /**
   * 添加思考
   */
  think: function(thought, options) {
    options = options || {};

    var obj = {
      id: 'thought_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
      thought: thought,
      number: this.thoughts.length + 1,
      totalThoughts: options.totalThoughts || 10,
      nextNeeded: options.nextNeeded !== false,
      isRevision: options.isRevision || false,
      revisesId: options.revisesId || null,
      branchId: options.branchId || null,
      timestamp: Date.now()
    };

    this.thoughts.push(obj);
    return obj;
  },

  /**
   * 修订
   */
  revise: function(thoughtId, newThought) {
    return this.think(newThought, {
      isRevision: true,
      revisesId: thoughtId
    });
  },

  /**
   * 分支
   */
  branch: function(thoughtId, newThought, branchName) {
    return this.think(newThought, {
      branchId: branchName || ('branch_' + Date.now()),
      branchFrom: thoughtId
    });
  },

  /**
   * 结束思考
   */
  conclude: function(finalThought) {
    if (finalThought) {
      this.think(finalThought, { nextNeeded: false });
    }

    var conclusion = this.getConclusion();
    this.thoughts = []; // 清空
    return conclusion;
  },

  /**
   * 获取结论
   */
  getConclusion: function() {
    if (this.thoughts.length === 0) {
      return { summary: '', insights: [], nextSteps: [] };
    }

    var insights = [];
    var nextSteps = [];

    for (var i = 0; i < this.thoughts.length; i++) {
      var t = this.thoughts[i];
      if (t.thought.indexOf('发现') !== -1 || t.thought.indexOf('关键') !== -1) {
        insights.push(t.thought);
      }
    }

    if (this.thoughts.length > 0) {
      nextSteps.push(this.thoughts[this.thoughts.length - 1].thought);
    }

    return {
      summary: this.thoughts.map(function(t) { return t.thought; }).join('\n'),
      insights: insights.slice(0, 3),
      nextSteps: nextSteps.slice(0, 2)
    };
  },

  /**
   * 清空
   */
  clear: function() {
    this.thoughts = [];
  }
};

// ============================================================
// 三、导出
// ============================================================
window.DesktopPlan = {
  Plan: DesktopPlan,
  Thinking: DesktopThinking,

  create: function(title, goal) { return DesktopPlan.create(title, goal); },
  addStep: function(desc) { return DesktopPlan.addStep(desc); },
  completeStep: function(id, result) { return DesktopPlan.completeStep(id, result); },
  failStep: function(id, error) { return DesktopPlan.failStep(id, error); },
  complete: function(summary) { return DesktopPlan.complete(summary); },
  cancel: function() { return DesktopPlan.cancel(); },
  getProgress: function() { return DesktopPlan.getProgress(); },
  toText: function() { return DesktopPlan.toText(); },
  getCurrent: function() { return DesktopPlan.current; },

  think: function(thought, opts) { return DesktopThinking.think(thought, opts); },
  revise: function(id, thought) { return DesktopThinking.revise(id, thought); },
  branch: function(id, thought, name) { return DesktopThinking.branch(id, thought, name); },
  conclude: function(final) { return DesktopThinking.conclude(final); },
  getThoughts: function() { return DesktopThinking.thoughts; }
};
