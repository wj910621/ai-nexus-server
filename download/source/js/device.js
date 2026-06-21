/**
 * TriGenClaw - 贾维斯设备控制模块
 * 通过 Electron IPC 实现本地设备控制
 * 文件搜索、应用启动、系统控制等
 */
;(function(){
  'use strict';

  var jarvisDevice = {
    // 搜索文件 - 通过 Electron IPC
    searchFile: async function(query) {
      try {
        if (window.electronAPI && window.electronAPI.searchFile) {
          var result = await window.electronAPI.searchFile(query || '');
          if (result && result.success && result.results && result.results.length > 0) {
            var names = result.results.map(function(r) { return r.name; }).join('，');
            return '先生，找到以下文件：' + names;
          }
          return '先生，未找到与"' + query + '"相关的文件。';
        }
        return '先生，文件搜索需要桌面端环境。';
      } catch(e) {
        return '搜索文件时出错：' + e.message;
      }
    },

    // 打开文件/文件夹
    openLocation: function(filePath) {
      if (window.electronAPI && window.electronAPI.openPath) {
        window.electronAPI.openPath(filePath);
        return '好的先生，已打开。';
      }
      return '先生，此功能需要桌面端支持。';
    },

    // 获取系统信息
    getSystemInfo: function() {
      var info = {
        平台: navigator.platform,
        语言: navigator.language,
        在线: navigator.onLine ? '是' : '否',
        时间: new Date().toLocaleString('zh-CN')
      };
      return '系统信息：' + Object.entries(info).map(function(kv) { return kv[0] + '=' + kv[1]; }).join('，') + '。';
    },

    // 控制智能家居（模拟）
    controlDevice: function(device, action) {
      var actionText = (action === 'on' || action === '开' || action === '打开') ? '打开' :
                       (action === 'off' || action === '关' || action === '关闭') ? '关闭' :
                       action;
      return '好的先生，' + device + '已' + actionText + '。';
    },

    // 设置计时器
    setTimer: function(minutes, label) {
      var ms = parseInt(minutes) * 60000;
      if (isNaN(ms) || ms <= 0) return '先生，请指定一个有效的时间。';
      setTimeout(function() {
        if (window.jarvisSpeech) {
          window.jarvisSpeech.speak(label ? minutes + '分钟到了：' + label : minutes + '分钟到了，先生。');
        }
      }, ms);
      return '好的先生，' + minutes + '分钟' + (label ? '（' + label + '）' : '') + '后提醒您。';
    },

    // 执行工具
    executeTool: function(toolName, args) {
      args = args || {};
      switch(toolName) {
        case 'search_file': return this.searchFile(args.name || args.filename || args.query || '');
        case 'set_timer': return this.setTimer(args.minutes, args.label || '');
        case 'device_control': return this.controlDevice(args.device, args.action);
        case 'system_info': return this.getSystemInfo();
        case 'open_location': return this.openLocation(args.path || '');
        default: return '先生，未知的工具：' + toolName;
      }
    }
  };

  window.jarvisDevice = jarvisDevice;
})();
