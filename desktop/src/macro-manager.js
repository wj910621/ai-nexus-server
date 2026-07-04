/**
 * Y·NEX Desktop — 键盘宏录制与回放管理器
 * 录制按键序列，支持保存/加载/回放
 */

class MacroManager {
  constructor() {
    this.macros = new Map();
    this.recording = null;
    this.recordingStart = null;
  }

  /**
   * 开始录制键盘宏
   */
  startRecording(name) {
    if (this.recording) {
      return { error: '已在录制中，请先停止当前录制' };
    }
    this.recording = {
      name: name || `宏_${Date.now()}`,
      events: [],
      startTime: Date.now()
    };
    return { ok: true, name: this.recording.name };
  }

  /**
   * 记录按键事件
   */
  recordEvent(event) {
    if (!this.recording) return;
    const elapsed = Date.now() - this.recording.startTime;
    this.recording.events.push({
      ...event,
      delay: elapsed - (this.recording.events.length > 0
        ? this.recording.events[this.recording.events.length - 1].delay : 0)
    });
  }

  /**
   * 停止录制并保存
   */
  stopRecording() {
    if (!this.recording) {
      return { error: '没有正在录制' };
    }
    const macro = {
      name: this.recording.name,
      events: this.recording.events,
      totalTime: Date.now() - this.recording.startTime,
      eventCount: this.recording.events.length,
      createdAt: new Date().toISOString()
    };
    this.macros.set(macro.name, macro);
    this.recording = null;
    return { ok: true, macro };
  }

  /**
   * 获取回放事件序列
   */
  getPlayback(name) {
    const macro = this.macros.get(name);
    if (!macro) return { error: '宏不存在' };
    return { ok: true, events: macro.events };
  }

  /**
   * 删除宏
   */
  delete(name) {
    if (this.recording?.name === name) {
      this.recording = null;
    }
    return { ok: this.macros.delete(name) };
  }

  /**
   * 列出所有宏
   */
  list() {
    return Array.from(this.macros.values()).map(m => ({
      name: m.name,
      totalTime: m.totalTime,
      eventCount: m.eventCount,
      createdAt: m.createdAt
    }));
  }

  /**
   * 重命名宏
   */
  rename(oldName, newName) {
    const macro = this.macros.get(oldName);
    if (!macro) return { error: '宏不存在' };
    this.macros.delete(oldName);
    macro.name = newName;
    this.macros.set(newName, macro);
    return { ok: true };
  }

  isRecording() {
    return !!this.recording;
  }
}

module.exports = { MacroManager };