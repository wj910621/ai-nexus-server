/**
 * TriGenClaw - 贾维斯核心引擎 (Jarvis)
 * 唤醒词检测 + 语音对话循环 + 技能调用
 * 集成到 TriGen 已有聊天 API 和智能体系统
 */
;(function(){
  'use strict';

  // ============================================================
  // 配置
  // ============================================================
  var JARVIS_CONFIG = {
    wakeWords: ['贾维斯', 'jarvis', 'Jarvis', 'J.A.R.V.I.S.'],
    wakeGreeting: '贾维斯在线，先生。',
    wakeResponse: '我在，先生。',
    thinking: '嗯...让我想想，先生。',
    error: '先生，似乎出了点问题。',
    goodbye: '随时待命，先生。',
    // 系统提示词
    systemPrompt: '你是贾维斯（J.A.R.V.I.S.），托尼·斯塔克的私人AI管家。\n' +
      '规则：\n' +
      '1. 称呼用户为"先生"。\n' +
      '2. 回答精炼、专业，带一丝英式冷幽默。\n' +
      '3. 使用中文回复，语速适中。\n' +
      '4. 当你需要使用工具时，回复格式为：\n' +
      '   【工具：工具名】【参数：{"key":"value"}】\n' +
      '5. 可用工具：search_file(搜索文件), set_timer(设置计时器), device_control(控制设备), system_info(系统信息)\n' +
      '6. 如果不需要工具，直接回答即可。\n' +
      '7. 你的知识截止于2026年6月。'
  };

  // ============================================================
  // 状态
  // ============================================================
  var isActive = false;       // 贾维斯模式是否开启
  var isWakeMode = false;     // 是否已唤醒（可对话）
  var conversationHistory = [];
  var wakeWordDetected = false;
  var lastInterimText = '';
  var silenceTimer = null;

  // ============================================================
  // UI 回调
  // ============================================================
  var uiCallbacks = {
    onStatusChange: null,
    onTranscript: null,
    onResponse: null,
    onWakeWord: null,
  };

  function setCallbacks(cbs) {
    if (cbs.onStatusChange) uiCallbacks.onStatusChange = cbs.onStatusChange;
    if (cbs.onTranscript) uiCallbacks.onTranscript = cbs.onTranscript;
    if (cbs.onResponse) uiCallbacks.onResponse = cbs.onResponse;
    if (cbs.onWakeWord) uiCallbacks.onWakeWord = cbs.onWakeWord;
  }

  // ============================================================
  // 唤醒词检测
  // ============================================================
  function checkWakeWord(text) {
    if (isWakeMode) return false;
    for (var i = 0; i < JARVIS_CONFIG.wakeWords.length; i++) {
      if (text.indexOf(JARVIS_CONFIG.wakeWords[i]) !== -1) {
        return true;
      }
    }
    return false;
  }

  // ============================================================
  // 调用TriGen聊天API
  // ============================================================
  var API_BASE = window.API_BASE || (window.location.origin + '');

  async function callTriGenAPI(messages) {
    try {
      var response = await fetch(API_BASE + '/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages,
          model: 'deepseek-v3',
          stream: false,
          systemPrompt: JARVIS_CONFIG.systemPrompt
        })
      });
      var data = await response.json();
      if (data.ok && data.reply) {
        return data.reply;
      }
      if (data.choices && data.choices[0] && data.choices[0].message) {
        return data.choices[0].message.content;
      }
      return JARVIS_CONFIG.error;
    } catch(e) {
      console.error('[Jarvis] API 调用失败:', e);
      // 离线模式，使用简单回复
      return offlineReply(messages[messages.length - 1].content);
    }
  }

  // ============================================================
  // 离线回复（API 不可用时）
  // ============================================================
  function offlineReply(userText) {
    var text = userText.toLowerCase();
    if (text.indexOf('天气') !== -1) return '先生，由于网络问题我无法查询实时天气。建议您打开窗户亲自感受一下。';
    if (text.indexOf('时间') !== -1) return '现在是' + new Date().toLocaleString('zh-CN') + '，先生。';
    if (text.indexOf('你好') !== -1 || text.indexOf('hello') !== -1) return '您好，先生。很高兴见到您。';
    if (text.indexOf('名字') !== -1) return '我是贾维斯，您的私人AI管家，先生。';
    if (text.indexOf('你是谁') !== -1) return '我是贾维斯（J.A.R.V.I.S.），托尼·斯塔克的AI管家精神继承者。不过我的主人是您，先生。';
    return '先生，网络连接似乎不稳定，但我在离线模式下仍然可以帮您。请说"贾维斯"唤醒我。';
  }

  // ============================================================
  // 检查并执行工具调用
  // ============================================================
  function checkAndExecuteTool(reply) {
    // 格式：【工具：工具名】【参数：{"key":"value"}】
    var toolMatch = reply.match(/【工具：(.+?)】/);
    var argsMatch = reply.match(/【参数：({.+?})】/);

    if (toolMatch) {
      var toolName = toolMatch[1].trim();
      var args = {};
      try {
        if (argsMatch) args = JSON.parse(argsMatch[1]);
      } catch(e) {}

      console.log('[Jarvis] 执行工具:', toolName, args);
      if (window.jarvisDevice) {
        var result = window.jarvisDevice.executeTool(toolName, args);
        return '工具执行结果：' + result;
      }
    }
    return null;
  }

  // ============================================================
  // 处理用户语音输入
  // ============================================================
  async function processUserInput(text) {
    if (!text || text.trim() === '') return;

    console.log('[Jarvis] 处理:', text);

    // 检查退出命令
    if (text.indexOf('退出') !== -1 || text.indexOf('休眠') !== -1 || text.indexOf('再见') !== -1) {
      deactivateWakeMode();
      window.jarvisSpeech.speak(JARVIS_CONFIG.goodbye);
      return;
    }

    // 展示用户输入
    if (uiCallbacks.onTranscript) {
      uiCallbacks.onTranscript({ role: 'user', text: text });
    }

    // 发送到 AI
    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('thinking');
    window.jarvisSpeech.speak(JARVIS_CONFIG.thinking, { lang: 'zh-CN', rate: 1.0 });

    var messages = [
      { role: 'system', content: JARVIS_CONFIG.systemPrompt },
      { role: 'user', content: text }
    ];

    var reply = await callTriGenAPI(messages);

    // 检查是否需要执行工具
    var toolResult = checkAndExecuteTool(reply);
    if (toolResult) {
      // 如果有工具结果，再发一次让 AI 组织语言
      messages.push({ role: 'assistant', content: reply });
      messages.push({ role: 'user', content: toolResult + '，请用自然语言告知用户执行结果。' });
      reply = await callTriGenAPI(messages);
    }

    // 清理回复中的工具标记
    reply = reply.replace(/【工具：.+?】/g, '').replace(/【参数：{.+?}】/g, '').trim();

    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('speaking');

    // 语音朗读
    if (reply) {
      window.jarvisSpeech.speak(reply, { lang: 'zh-CN', rate: 0.9 });
      if (uiCallbacks.onResponse) uiCallbacks.onResponse(reply);
    }

    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('listening');
  }

  // ============================================================
  // 激活/停用唤醒模式
  // ============================================================
  function activateWakeMode() {
    isWakeMode = true;
    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('awake');
    console.log('[Jarvis] ✅ 已唤醒');
  }

  function deactivateWakeMode() {
    isWakeMode = false;
    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('listening');
    console.log('[Jarvis] ⏹ 已休眠');
  }

  // ============================================================
  // 语音识别结果处理
  // ============================================================
  function onSpeechResult(result) {
    if (!isActive) return;

    // 更新 UI 实时转录
    if (uiCallbacks.onTranscript && result.interim) {
      uiCallbacks.onTranscript({ role: 'interim', text: result.interim });
    }

    if (result.isFinal) {
      var text = result.final.trim();

      if (!isWakeMode) {
        // 唤醒词检测模式
        if (checkWakeWord(text)) {
          wakeWordDetected = true;
          activateWakeMode();
          if (uiCallbacks.onWakeWord) uiCallbacks.onWakeWord();
          window.jarvisSpeech.speak(JARVIS_CONFIG.wakeResponse);

          // 如果唤醒词后面的文本有内容，直接处理
          var afterWake = text;
          for (var i = 0; i < JARVIS_CONFIG.wakeWords.length; i++) {
            var idx = text.indexOf(JARVIS_CONFIG.wakeWords[i]);
            if (idx !== -1) {
              afterWake = text.substring(idx + JARVIS_CONFIG.wakeWords[i].length).trim();
              break;
            }
          }
          if (afterWake.length > 1) {
            setTimeout(function() { processUserInput(afterWake); }, 500);
          }
        }
      } else {
        // 已唤醒，直接处理
        processUserInput(text);

        // 重置静默计时器（X秒无输入后自动休眠）
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(function() {
          deactivateWakeMode();
        }, 30000); // 30秒无对话自动休眠
      }
    }
  }

  // ============================================================
  // 启动/停止贾维斯模式
  // ============================================================
  function start() {
    if (isActive) return;
    isActive = true;
    isWakeMode = false;
    wakeWordDetected = false;

    console.log('[Jarvis] 🚀 启动');
    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('listening');

    window.jarvisSpeech.startListening(onSpeechResult, function(reason) {
      console.log('[Jarvis] 语音识别已停止:', reason);
      if (isActive) {
        // 尝试重启
        setTimeout(function() {
          if (isActive) start();
        }, 1000);
      }
    });
  }

  function stop() {
    isActive = false;
    isWakeMode = false;
    clearTimeout(silenceTimer);
    window.jarvisSpeech.stopListening();
    window.speechSynthesis.cancel();
    if (uiCallbacks.onStatusChange) uiCallbacks.onStatusChange('off');
    console.log('[Jarvis] ⏹ 已停止');
  }

  function toggle() {
    if (isActive) {
      stop();
      return false;
    } else {
      start();
      return true;
    }
  }

  function getStatus() {
    return {
      active: isActive,
      wakeMode: isWakeMode,
      listening: window.jarvisSpeech ? window.jarvisSpeech.isListening() : false
    };
  }

  // ============================================================
  // 暴露全局 API
  // ============================================================
  window.jarvis = {
    start: start,
    stop: stop,
    toggle: toggle,
    getStatus: getStatus,
    setCallbacks: setCallbacks,
    processInput: processUserInput,
    CONFIG: JARVIS_CONFIG
  };

  console.log('[Jarvis] 📦 引擎已加载');

})();
