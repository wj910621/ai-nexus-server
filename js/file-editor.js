/**
 * Y·NEX 结构化文件编辑系统 v2.0
 * 基于 Codex apply_patch 设计
 * 提供安全的文件编辑操作
 */
'use strict';

// ============================================================
// 一、文件操作工具
// ============================================================
const FileEditor = {
  /**
   * 读取文件内容
   * @param {string} path - 文件路径
   * @param {object} options - 选项
   * @returns {Promise<object>}
   */
  async read(path, options = {}) {
    try {
      // 通过 API 读取
      const response = await fetch(API_BASE + '/api/files/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, encoding: options.encoding || 'utf8' })
      });

      const result = await response.json();

      if (result.error) {
        return { success: false, error: result.error };
      }

      return {
        success: true,
        content: result.content,
        lines: result.content.split('\n'),
        lineCount: result.content.split('\n').length
      };
    } catch (e) {
      return { success: false, error: e.message };
    }
  },

  /**
   * 写入文件
   * @param {string} path - 文件路径
   * @param {string} content - 文件内容
   * @param {object} options - 选项
   * @returns {Promise<object>}
   */
  async write(path, content, options = {}) {
    try {
      const response = await fetch(API_BASE + '/api/files/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path,
          content,
          createDirs: options.createDirs || false,
          backup: options.backup !== false
        })
      });

      const result = await response.json();

      if (result.error) {
        return { success: false, error: result.error };
      }

      return {
        success: true,
        path: result.path,
        backupPath: result.backupPath,
        bytesWritten: content.length
      };
    } catch (e) {
      return { success: false, error: e.message };
    }
  },

  /**
   * 创建文件（仅当不存在时）
   * @param {string} path - 文件路径
   * @param {string} content - 文件内容
   * @returns {Promise<object>}
   */
  async create(path, content = '') {
    // 先检查是否存在
    const readResult = await this.exists(path);
    if (readResult.exists) {
      return { success: false, error: '文件已存在' };
    }

    return this.write(path, content, { createDirs: true });
  },

  /**
   * 删除文件
   * @param {string} path - 文件路径
   * @returns {Promise<object>}
   */
  async delete(path) {
    try {
      const response = await fetch(API_BASE + '/api/files/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });

      const result = await response.json();

      return result;
    } catch (e) {
      return { success: false, error: e.message };
    }
  },

  /**
   * 检查文件是否存在
   * @param {string} path - 文件路径
   * @returns {Promise<object>}
   */
  async exists(path) {
    try {
      const response = await fetch(API_BASE + '/api/files/exists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });

      const result = await response.json();
      return result;
    } catch (e) {
      return { exists: false, error: e.message };
    }
  },

  /**
   * 列出目录内容
   * @param {string} path - 目录路径
   * @param {object} options - 选项
   * @returns {Promise<object>}
   */
  async listDir(path, options = {}) {
    try {
      const response = await fetch(API_BASE + '/api/files/list', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path,
          depth: options.depth || 1,
          includeHidden: options.includeHidden || false
        })
      });

      const result = await response.json();

      if (result.error) {
        return { success: false, error: result.error };
      }

      return {
        success: true,
        entries: result.entries.map(e => ({
          name: e.name,
          path: e.path,
          type: e.isDirectory ? 'directory' : 'file',
          size: e.size,
          modified: e.modified
        }))
      };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }
};

// ============================================================
// 二、结构化补丁工具（apply_patch 风格）
// ============================================================
const PatchTool = {
  /**
   * 应用补丁
   * 补丁格式：
   * *** Begin Patch
   * *** Add File: path
   * +content line 1
   * +content line 2
   * *** Update File: path
   * @@ -old_line
   * -removed line
   * +new line
   * *** Delete File: path
   * *** End Patch
   */
  async applyPatch(patchString, options = {}) {
    const dryRun = options.dryRun || false;
    const results = [];

    // 解析补丁
    const sections = this.parsePatch(patchString);

    for (const section of sections) {
      let result;

      switch (section.type) {
        case 'add':
          result = await this.handleAddFile(section, dryRun);
          break;
        case 'update':
          result = await this.handleUpdateFile(section, dryRun);
          break;
        case 'delete':
          result = await this.handleDeleteFile(section, dryRun);
          break;
        case 'move':
          result = await this.handleMoveFile(section, dryRun);
          break;
        default:
          result = { success: false, error: `未知操作: ${section.type}` };
      }

      results.push({
        type: section.type,
        path: section.path,
        ...result
      });
    }

    return {
      success: results.every(r => r.success),
      results,
      summary: this.generateSummary(results)
    };
  },

  /**
   * 解析补丁字符串
   */
  parsePatch(patchString) {
    const sections = [];
    const lines = patchString.split('\n');
    let currentSection = null;
    let currentContent = [];

    for (const line of lines) {
      const trimmed = line.trim();

      if (trimmed === '*** Begin Patch') {
        continue;
      }

      if (trimmed === '*** End Patch') {
        if (currentSection) {
          currentSection.content = currentContent.join('\n');
          sections.push(currentSection);
          currentSection = null;
          currentContent = [];
        }
        continue;
      }

      if (trimmed.startsWith('*** Add File:')) {
        if (currentSection) {
          currentSection.content = currentContent.join('\n');
          sections.push(currentSection);
        }
        currentSection = {
          type: 'add',
          path: trimmed.replace('*** Add File:', '').trim()
        };
        currentContent = [];
        continue;
      }

      if (trimmed.startsWith('*** Update File:')) {
        if (currentSection) {
          currentSection.content = currentContent.join('\n');
          sections.push(currentSection);
        }
        currentSection = {
          type: 'update',
          path: trimmed.replace('*** Update File:', '').trim()
        };
        currentContent = [];
        continue;
      }

      if (trimmed.startsWith('*** Delete File:')) {
        if (currentSection) {
          currentSection.content = currentContent.join('\n');
          sections.push(currentSection);
        }
        currentSection = {
          type: 'delete',
          path: trimmed.replace('*** Delete File:', '').trim()
        };
        currentContent = [];
        continue;
      }

      if (trimmed.startsWith('*** Move to:')) {
        if (currentSection) {
          currentSection.newPath = trimmed.replace('*** Move to:', '').trim();
        }
        continue;
      }

      // 内容行
      if (currentSection && (trimmed.startsWith('+') || trimmed.startsWith('-') || trimmed.startsWith('@@'))) {
        currentContent.push(line);
      } else if (currentSection && !trimmed.startsWith('***')) {
        // 新文件内容（+开头）
        currentContent.push('+' + line);
      }
    }

    return sections;
  },

  /**
   * 处理添加文件
   */
  async handleAddFile(section, dryRun) {
    if (dryRun) {
      return {
        success: true,
        action: 'would create',
        path: section.path,
        size: section.content.length
      };
    }

    const content = section.content
      .split('\n')
      .map(line => line.startsWith('+') ? line.substring(1) : line)
      .join('\n')
      .trim();

    return await FileEditor.create(section.path, content);
  },

  /**
   * 处理更新文件
   */
  async handleUpdateFile(section, dryRun) {
    if (dryRun) {
      return {
        success: true,
        action: 'would update',
        path: section.path
      };
    }

    const content = section.content
      .split('\n')
      .map(line => line.startsWith('+') ? line.substring(1) : line)
      .join('\n');

    return await FileEditor.write(section.path, content);
  },

  /**
   * 处理删除文件
   */
  async handleDeleteFile(section, dryRun) {
    if (dryRun) {
      return {
        success: true,
        action: 'would delete',
        path: section.path
      };
    }

    return await FileEditor.delete(section.path);
  },

  /**
   * 处理移动文件
   */
  async handleMoveFile(section, dryRun) {
    if (dryRun) {
      return {
        success: true,
        action: 'would move',
        from: section.path,
        to: section.newPath
      };
    }

    // 读取原文件
    const readResult = await FileEditor.read(section.path);
    if (!readResult.success) {
      return readResult;
    }

    // 写入新位置
    const writeResult = await FileEditor.write(section.newPath, readResult.content);
    if (!writeResult.success) {
      return writeResult;
    }

    // 删除原文件
    return await FileEditor.delete(section.path);
  },

  /**
   * 生成结果摘要
   */
  generateSummary(results) {
    const success = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success);

    let summary = `成功: ${success}/${results.length}`;
    if (failed.length > 0) {
      summary += `\n失败:\n${failed.map(f => `- ${f.path}: ${f.error}`).join('\n')}`;
    }

    return summary;
  }
};

// ============================================================
// 三、字符串替换编辑
// ============================================================
const StrReplaceEditor = {
  /**
   * 精确字符串替换
   */
  async strReplace(path, oldStr, newStr, options = {}) {
    // 读取文件
    const readResult = await FileEditor.read(path);
    if (!readResult.success) {
      return readResult;
    }

    let content = readResult.content;

    // 查找替换
    const index = content.indexOf(oldStr);
    if (index === -1) {
      return {
        success: false,
        error: '未找到要替换的字符串'
      };
    }

    // 执行替换
    if (options.all) {
      content = content.split(oldStr).join(newStr);
    } else {
      content = content.substring(0, index) + newStr + content.substring(index + oldStr.length);
    }

    // 写入
    return await FileEditor.write(path, content);
  },

  /**
   * 插入到指定行之后
   */
  async insertAfter(path, afterLine, newContent) {
    const readResult = await FileEditor.read(path);
    if (!readResult.success) {
      return readResult;
    }

    const lines = readResult.lines;
    const insertIndex = lines.findIndex(l => l.trim() === afterLine.trim());

    if (insertIndex === -1) {
      return {
        success: false,
        error: `未找到行: ${afterLine}`
      };
    }

    // 插入内容
    const newLines = newContent.split('\n');
    lines.splice(insertIndex + 1, 0, ...newLines);

    return await FileEditor.write(path, lines.join('\n'));
  },

  /**
   * 在文件末尾追加内容
   */
  async append(path, content) {
    const readResult = await FileEditor.read(path);
    const currentContent = readResult.success ? readResult.content : '';

    const newContent = currentContent + (currentContent.endsWith('\n') ? '' : '\n') + content;
    return await FileEditor.write(path, newContent);
  }
};

// ============================================================
// 四、JSON 编辑器
// ============================================================
const JsonEditor = {
  /**
   * 读取 JSON 文件
   */
  async read(path) {
    const result = await FileEditor.read(path);
    if (!result.success) {
      return result;
    }

    try {
      const data = JSON.parse(result.content);
      return { success: true, data, raw: result.content };
    } catch (e) {
      return { success: false, error: `JSON 解析错误: ${e.message}` };
    }
  },

  /**
   * 设置 JSON 路径的值
   * 使用类似 lodash 的路径: 'a.b.c' 或 'a[0].b'
   */
  async set(path, jsonPath, value) {
    const result = await this.read(path);
    if (!result.success) {
      return result;
    }

    try {
      // 解析 JSONPath
      const parts = this.parseJsonPath(jsonPath);
      let current = result.data;

      // 导航到父级
      for (let i = 0; i < parts.length - 1; i++) {
        if (current[parts[i]] === undefined) {
          current[parts[i]] = isNaN(parts[i + 1]) ? {} : [];
        }
        current = current[parts[i]];
      }

      // 设置值
      const lastPart = parts[parts.length - 1];
      current[lastPart] = value;

      // 写回文件
      const writeResult = await FileEditor.write(
        path,
        JSON.stringify(result.data, null, 2)
      );

      return writeResult;
    } catch (e) {
      return { success: false, error: e.message };
    }
  },

  /**
   * 解析 JSONPath
   */
  parseJsonPath(path) {
    return path
      .replace(/\[(\d+)\]/g, '.$1')
      .split('.')
      .filter(Boolean);
  },

  /**
   * 添加元素到数组
   */
  async addToArray(path, jsonPath, item) {
    const result = await this.read(path);
    if (!result.success) {
      return result;
    }

    try {
      const parts = this.parseJsonPath(jsonPath);
      let current = result.data;

      for (let i = 0; i < parts.length; i++) {
        if (current[parts[i]] === undefined) {
          current[parts[i]] = [];
        }
        current = current[parts[i]];
      }

      if (!Array.isArray(current)) {
        return { success: false, error: '目标不是数组' };
      }

      current.push(item);

      return await FileEditor.write(path, JSON.stringify(result.data, null, 2));
    } catch (e) {
      return { success: false, error: e.message };
    }
  },

  /**
   * 从数组中删除元素
   */
  async removeFromArray(path, jsonPath, index) {
    const result = await this.read(path);
    if (!result.success) {
      return result;
    }

    try {
      const parts = this.parseJsonPath(jsonPath);
      let current = result.data;

      for (let i = 0; i < parts.length; i++) {
        if (current[parts[i]] === undefined) {
          return { success: false, error: '路径不存在' };
        }
        current = current[parts[i]];
      }

      if (!Array.isArray(current)) {
        return { success: false, error: '目标不是数组' };
      }

      if (index < 0 || index >= current.length) {
        return { success: false, error: '索引超出范围' };
      }

      current.splice(index, 1);

      return await FileEditor.write(path, JSON.stringify(result.data, null, 2));
    } catch (e) {
      return { success: false, error: e.message };
    }
  }
};

// ============================================================
// 五、导出
// ============================================================
window.FileEditor = {
  File: FileEditor,
  Patch: PatchTool,
  StrReplace: StrReplaceEditor,
  Json: JsonEditor,

  // 便捷方法
  read: (path, opts) => FileEditor.read(path, opts),
  write: (path, content, opts) => FileEditor.write(path, content, opts),
  create: (path, content) => FileEditor.create(path, content),
  delete: (path) => FileEditor.delete(path),
  list: (path, opts) => FileEditor.listDir(path, opts),
  patch: (patch, opts) => PatchTool.applyPatch(patch, opts),
  strReplace: (path, oldStr, newStr, opts) => StrReplaceEditor.strReplace(path, oldStr, newStr, opts),
  jsonRead: (path) => JsonEditor.read(path),
  jsonSet: (path, jsonPath, value) => JsonEditor.set(path, jsonPath, value)
};
