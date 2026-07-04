/**
 * TriGen Wiki 知识库管理
 * 基于 he-wiki-rag Wiki 模块设计
 * 支持 Markdown 文档、Frontmatter、章节树
 */
'use strict';

// ============================================================
// 一、知识库配置
// ============================================================
const WIKI_CONFIG = {
    // 文档类型
    types: {
        concept: { icon: '💡', color: '#00d4ff', priority: 'P1' },
        pattern: { icon: '🔧', color: '#7b2ff7', priority: 'P1' },
        architecture: { icon: '🏗️', color: '#ff6b6b', priority: 'P0' },
        faq: { icon: '❓', color: '#ffd93d', priority: 'P2' },
        tutorial: { icon: '📚', color: '#6bcb77', priority: 'P1' },
        reference: { icon: '📖', color: '#4d96ff', priority: 'P2' },
    },
    
    // 优先级
    priorities: ['P0', 'P1', 'P2'],
    
    // 知识库根目录
    rootPath: 'wiki/',
    
    // 自动保存
    autoSave: true,
    autoSaveDelay: 2000,
};

// ============================================================
// 二、知识库管理器
// ============================================================
class WikiKnowledgeBase {
    constructor(options = {}) {
        this.config = { ...WIKI_CONFIG, ...options };
        this.documents = new Map();        // 文档存储
        this.categories = new Map();        // 分类索引
        this.tags = new Map();             // 标签索引
        this.searchIndex = new Map();       // 搜索索引
        
        // 编辑状态
        this.editingDocs = new Set();
        this.unsavedChanges = new Map();
        
        // 统计
        this.stats = {
            totalDocs: 0,
            totalEdits: 0,
            lastSync: null,
        };
    }

    // ------------------------------------------------
    // 2.1 文档操作
    // ------------------------------------------------
    
    /**
     * 创建文档
     */
    createDocument(options = {}) {
        const {
            title = 'Untitled',
            type = 'concept',
            content = '',
            category = 'general',
            tags = [],
            keywords = [],
        } = options;
        
        const id = this.generateId(title);
        const now = Date.now();
        
        const doc = {
            id,
            title,
            type,
            category,
            tags,
            keywords,
            content,
            frontmatter: {
                title,
                type,
                priority: this.config.types[type]?.priority || 'P2',
                category,
                keywords: keywords.length > 0 ? keywords : [title],
                created: this.formatDate(now),
                updated: this.formatDate(now),
            },
            metadata: {
                created: now,
                updated: now,
                views: 0,
                likes: 0,
            },
            headings: this.extractHeadings(content),
            sections: this.splitSections(content),
        };
        
        this.documents.set(id, doc);
        this.indexDocument(doc);
        this.stats.totalDocs++;
        
        return doc;
    }

    /**
     * 更新文档
     */
    updateDocument(id, updates) {
        const doc = this.documents.get(id);
        if (!doc) return null;
        
        const now = Date.now();
        
        // 更新字段
        if (updates.title !== undefined) doc.title = updates.title;
        if (updates.content !== undefined) {
            doc.content = updates.content;
            doc.headings = this.extractHeadings(updates.content);
            doc.sections = this.splitSections(updates.content);
        }
        if (updates.type !== undefined) doc.type = updates.type;
        if (updates.tags !== undefined) doc.tags = updates.tags;
        if (updates.keywords !== undefined) doc.keywords = updates.keywords;
        if (updates.category !== undefined) doc.category = updates.category;
        
        // 更新时间
        doc.metadata.updated = now;
        doc.frontmatter.updated = this.formatDate(now);
        doc.frontmatter.title = doc.title;
        doc.frontmatter.type = doc.type;
        doc.frontmatter.priority = this.config.types[doc.type]?.priority || 'P2';
        
        // 重新索引
        this.indexDocument(doc);
        this.stats.totalEdits++;
        
        return doc;
    }

    /**
     * 删除文档
     */
    deleteDocument(id) {
        const doc = this.documents.get(id);
        if (!doc) return false;
        
        // 从索引中移除
        this.unindexDocument(doc);
        
        // 删除文档
        this.documents.delete(id);
        this.stats.totalDocs--;
        
        return true;
    }

    /**
     * 获取文档
     */
    getDocument(id) {
        return this.documents.get(id);
    }

    /**
     * 获取文档的 Markdown 格式
     */
    getDocumentMarkdown(id) {
        const doc = this.documents.get(id);
        if (!doc) return null;
        
        return this.toMarkdown(doc);
    }

    // ------------------------------------------------
    // 2.2 Frontmatter 处理
    // ------------------------------------------------
    
    /**
     * 解析 Frontmatter
     */
    parseFrontmatter(content) {
        const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
        if (!match) {
            return { frontmatter: {}, content };
        }
        
        const [, yaml, body] = match;
        const frontmatter = {};
        
        // 简单 YAML 解析
        yaml.split('\n').forEach(line => {
            const [key, ...valueParts] = line.split(':');
            if (key && valueParts.length > 0) {
                const value = valueParts.join(':').trim();
                
                // 数组解析
                if (value.startsWith('[') && value.endsWith(']')) {
                    frontmatter[key.trim()] = value
                        .slice(1, -1)
                        .split(',')
                        .map(v => v.trim().replace(/^["']|["']$/g, ''));
                } else {
                    frontmatter[key.trim()] = value.replace(/^["']|["']$/g, '');
                }
            }
        });
        
        return { frontmatter, content: body.trim() };
    }

    /**
     * 生成 Frontmatter
     */
    generateFrontmatter(frontmatter) {
        let yaml = '---\n';
        
        for (const [key, value] of Object.entries(frontmatter)) {
            if (Array.isArray(value)) {
                yaml += `${key}: [${value.join(', ')}]\n`;
            } else {
                yaml += `${key}: ${value}\n`;
            }
        }
        
        yaml += '---\n';
        return yaml;
    }

    /**
     * 转换为 Markdown
     */
    toMarkdown(doc) {
        const fm = doc.frontmatter || {};
        
        let md = this.generateFrontmatter(fm);
        md += '\n' + doc.content;
        
        return md;
    }

    // ------------------------------------------------
    // 2.3 章节解析
    // ------------------------------------------------
    
    /**
     * 提取标题
     */
    extractHeadings(content) {
        const headings = [];
        const lines = content.split('\n');
        
        let currentH1 = null;
        let currentH2 = null;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const h1Match = line.match(/^(#{1})\s+(.+)/);
            const h2Match = line.match(/^(#{2})\s+(.+)/);
            const h3Match = line.match(/^(#{3})\s+(.+)/);
            
            if (h1Match) {
                const heading = {
                    level: 1,
                    text: h1Match[2].trim(),
                    line: i + 1,
                    anchor: this.slugify(h1Match[2]),
                };
                headings.push(heading);
                currentH1 = heading;
                currentH2 = null;
            } else if (h2Match) {
                const heading = {
                    level: 2,
                    text: h2Match[2].trim(),
                    line: i + 1,
                    anchor: this.slugify(h2Match[2]),
                    parent: currentH1,
                };
                headings.push(heading);
                currentH2 = heading;
            } else if (h3Match) {
                const heading = {
                    level: 3,
                    text: h3Match[2].trim(),
                    line: i + 1,
                    anchor: this.slugify(h3Match[2]),
                    parent: currentH2 || currentH1,
                };
                headings.push(heading);
            }
        }
        
        return headings;
    }

    /**
     * 切分章节
     */
    splitSections(content) {
        const sections = [];
        const lines = content.split('\n');
        
        let currentSection = {
            level: 0,
            title: 'Introduction',
            content: [],
            startLine: 0,
        };
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const headingMatch = line.match(/^(#{1,3})\s+(.+)/);
            
            if (headingMatch) {
                // 保存当前章节
                if (currentSection.content.length > 0 || currentSection.level > 0) {
                    sections.push({
                        ...currentSection,
                        content: currentSection.content.join('\n').trim(),
                    });
                }
                
                // 开始新章节
                currentSection = {
                    level: headingMatch[1].length,
                    title: headingMatch[2].trim(),
                    anchor: this.slugify(headingMatch[2]),
                    content: [],
                    startLine: i + 1,
                };
            } else {
                currentSection.content.push(line);
            }
        }
        
        // 保存最后一个章节
        if (currentSection.content.length > 0 || currentSection.level > 0) {
            sections.push({
                ...currentSection,
                content: currentSection.content.join('\n').trim(),
            });
        }
        
        return sections;
    }

    /**
     * 生成锚点链接
     */
    slugify(text) {
        return text
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim();
    }

    // ------------------------------------------------
    // 2.4 索引与搜索
    // ------------------------------------------------
    
    /**
     * 索引文档
     */
    indexDocument(doc) {
        // 标签索引
        doc.tags.forEach(tag => {
            if (!this.tags.has(tag)) {
                this.tags.set(tag, new Set());
            }
            this.tags.get(tag).add(doc.id);
        });
        
        // 分类索引
        if (!this.categories.has(doc.category)) {
            this.categories.set(doc.category, new Set());
        }
        this.categories.get(doc.category).add(doc.id);
        
        // 搜索索引
        const searchText = [
            doc.title,
            doc.content,
            doc.tags.join(' '),
            doc.keywords.join(' '),
        ].join(' ').toLowerCase();
        
        this.searchIndex.set(doc.id, searchText);
    }

    /**
     * 移除索引
     */
    unindexDocument(doc) {
        // 标签
        doc.tags.forEach(tag => {
            if (this.tags.has(tag)) {
                this.tags.get(tag).delete(doc.id);
            }
        });
        
        // 分类
        if (this.categories.has(doc.category)) {
            this.categories.get(doc.category).delete(doc.id);
        }
        
        // 搜索索引
        this.searchIndex.delete(doc.id);
    }

    /**
     * 搜索文档
     */
    search(query, options = {}) {
        const {
            type = null,
            category = null,
            tags = [],
            limit = 20,
        } = options;
        
        const queryLower = query.toLowerCase();
        const results = [];
        
        for (const [id, doc] of this.documents) {
            // 类型过滤
            if (type && doc.type !== type) continue;
            
            // 分类过滤
            if (category && doc.category !== category) continue;
            
            // 标签过滤
            if (tags.length > 0 && !tags.some(t => doc.tags.includes(t))) continue;
            
            // 搜索匹配
            const searchText = this.searchIndex.get(id) || '';
            const queryTerms = queryLower.split(/\s+/);
            
            let score = 0;
            queryTerms.forEach(term => {
                if (doc.title.toLowerCase().includes(term)) score += 10;
                if (doc.tags.some(t => t.includes(term))) score += 5;
                if (doc.keywords.some(k => k.includes(term))) score += 3;
                if (searchText.includes(term)) score += 1;
            });
            
            if (score > 0) {
                results.push({
                    id,
                    doc,
                    score,
                    matches: this.getMatches(doc, queryLower),
                });
            }
        }
        
        return results
            .sort((a, b) => b.score - a.score)
            .slice(0, limit);
    }

    /**
     * 获取匹配片段
     */
    getMatches(doc, query) {
        const matches = [];
        const lines = doc.content.split('\n');
        const queryTerms = query.split(/\s+/);
        
        for (const line of lines) {
            const lineLower = line.toLowerCase();
            for (const term of queryTerms) {
                if (lineLower.includes(term)) {
                    const index = lineLower.indexOf(term);
                    const start = Math.max(0, index - 30);
                    const end = Math.min(line.length, index + term.length + 30);
                    matches.push('...' + line.slice(start, end) + '...');
                    break;
                }
            }
            if (matches.length >= 3) break;
        }
        
        return matches;
    }

    // ------------------------------------------------
    // 2.5 批量操作
    // ------------------------------------------------
    
    /**
     * 批量导入文档
     */
    importDocuments(docs) {
        const results = {
            success: 0,
            failed: 0,
            errors: [],
        };
        
        for (const docOptions of docs) {
            try {
                const doc = this.createDocument(docOptions);
                results.success++;
            } catch (error) {
                results.failed++;
                results.errors.push({
                    title: docOptions.title,
                    error: error.message,
                });
            }
        }
        
        return results;
    }

    /**
     * 导出所有文档
     */
    exportAll() {
        const docs = [];
        
        for (const [id, doc] of this.documents) {
            docs.push({
                ...doc,
                markdown: this.toMarkdown(doc),
            });
        }
        
        return {
            documents: docs,
            stats: this.stats,
            exportedAt: new Date().toISOString(),
        };
    }

    /**
     * 获取统计信息
     */
    getStats() {
        const typeStats = {};
        Object.keys(this.config.types).forEach(type => {
            typeStats[type] = 0;
        });
        
        for (const [, doc] of this.documents) {
            typeStats[doc.type] = (typeStats[doc.type] || 0) + 1;
        }
        
        return {
            ...this.stats,
            byType: typeStats,
            categories: this.categories.size,
            tags: this.tags.size,
        };
    }

    // ------------------------------------------------
    // 2.6 工具函数
    // ------------------------------------------------
    
    generateId(title) {
        return this.slugify(title) + '-' + Date.now().toString(36);
    }

    formatDate(timestamp) {
        return new Date(timestamp).toISOString().split('T')[0];
    }

    /**
     * 获取目录树
     */
    getCategoryTree() {
        const tree = {};
        
        for (const [category, docIds] of this.categories) {
            tree[category] = Array.from(docIds).map(id => ({
                id,
                title: this.documents.get(id)?.title,
                type: this.documents.get(id)?.type,
            }));
        }
        
        return tree;
    }

    /**
     * 清除所有数据
     */
    clear() {
        this.documents.clear();
        this.categories.clear();
        this.tags.clear();
        this.searchIndex.clear();
        this.stats = {
            totalDocs: 0,
            totalEdits: 0,
            lastSync: null,
        };
    }
}

// ============================================================
// 三、全局实例
// ============================================================
const wikiKnowledgeBase = new WikiKnowledgeBase();

// ============================================================
// 四、导出
// ============================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WikiKnowledgeBase, wikiKnowledgeBase, WIKI_CONFIG };
}
