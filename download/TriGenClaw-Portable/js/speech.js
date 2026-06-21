/**
 * TriGenClaw - 贾维斯语音模块 (Speech)
 * Web Speech API 封装：语音识别 + 语音合成
 * 无需任何 API Key，浏览器原生能力
 */
;(function(){
  'use strict';

  // ============================================================
  // 语音合成（TTS - 说话）
  // ============================================================
  function speak(text, options) {
    return new Promise(function(resolve) {
      if (!text) { resolve(); return; }
      // 取消正在播放的语音
      window.speechSynthesis.cancel();

      var utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = options && options.lang ? options.lang : 'zh-CN';
      utterance.rate = options && options.rate ? options.rate : 0.9;
      utterance.pitch = options && options.pitch ? options.pitch : 1.0;
      utterance.volume = 1.0;

      // 选择优质中文语音
      var voices = window.speechSynthesis.getVoices();
      var preferredVoice = voices.find(function(v) {
        return v.lang.startsWith('zh') && v.name.includes('Neural');
      }) || voices.find(function(v) {
        return v.lang.startsWith('zh');
      }) || voices.find(function(v) {
        return v.lang.startsWith('en') && v.name.includes('Neural');
      });
      if (preferredVoice) utterance.voice = preferredVoice;

      utterance.onend = resolve;
      utterance.onerror = resolve;
      window.speechSynthesis.speak(utterance);
    });
  }

  // ============================================================
  // 语音识别（ASR - 听）
  // ============================================================
  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognizer = null;
  var isListening = false;
  var onResultCallback = null;
  var onEndCallback = null;

  function initRecognizer() {
    if (!SpeechRecognition) {
      console.warn('[Jarvis] 浏览器不支持语音识别');
      return false;
    }
    if (recognizer) return true;

    recognizer = new SpeechRecognition();
    recognizer.lang = 'zh-CN';
    recognizer.continuous = true;
    recognizer.interimResults = true;
    recognizer.maxAlternatives = 3;

    recognizer.onresult = function(event) {
      var finalText = '';
      var interimText = '';
      for (var i = event.resultIndex; i < event.results.length; i++) {
        var transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalText += transcript;
        } else {
          interimText += transcript;
        }
      }
      if (onResultCallback) {
        onResultCallback({ final: finalText, interim: interimText, isFinal: !!finalText });
      }
    };

    recognizer.onerror = function(event) {
      console.warn('[Jarvis] 语音识别错误:', event.error);
      if (event.error === 'no-speech' || event.error === 'aborted') {
        // 安静重试
        return;
      }
      isListening = false;
      if (onEndCallback) onEndCallback({ error: event.error });
    };

    recognizer.onend = function() {
      // 自动重启（保持持续监听）
      if (isListening) {
        try {
          recognizer.start();
        } catch(e) {
          setTimeout(function() {
            if (isListening) recognizer.start();
          }, 500);
        }
      }
      if (onEndCallback && !isListening) onEndCallback({ ended: true });
    };

    return true;
  }

  function startListening(onResult, onEnd) {
    if (!initRecognizer()) {
      speak('抱歉先生，您的浏览器不支持语音识别。请使用 Chrome 或 Edge。');
      return;
    }
    if (isListening) return;
    isListening = true;
    onResultCallback = onResult;
    onEndCallback = onEnd;
    try {
      recognizer.start();
      console.log('[Jarvis] 🎤 语音识别已启动');
    } catch(e) {
      console.error('[Jarvis] 启动语音识别失败:', e);
      isListening = false;
    }
  }

  function stopListening() {
    isListening = false;
    onResultCallback = null;
    onEndCallback = null;
    if (recognizer) {
      try { recognizer.stop(); } catch(e) {}
    }
    console.log('[Jarvis] 🎤 语音识别已停止');
  }

  function isListeningNow() {
    return isListening;
  }

  // ============================================================
  // 获取可用语音列表
  // ============================================================
  function getAvailableVoices() {
    return window.speechSynthesis.getVoices().map(function(v) {
      return { name: v.name, lang: v.lang, isNeural: v.name.includes('Neural') };
    });
  }

  // ============================================================
  // 暴露 API
  // ============================================================
  window.jarvisSpeech = {
    speak: speak,
    startListening: startListening,
    stopListening: stopListening,
    isListening: isListeningNow,
    getVoices: getAvailableVoices,
    isSupported: !!SpeechRecognition
  };

  // 预加载语音列表
  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = function() {
      window.speechSynthesis.getVoices();
    };
  }
})();
