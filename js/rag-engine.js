/**
 * Y·NEX RAG Engine - 检索增强生成引擎
 * 基于 he-wiki-rag 设计理念
 * 支持混合检索 + Reranker 精排
 */
'use strict';

// ============================================================
// 一、RAG 配置
// ============================================================
const RAG_CONFIG = {
    // 检索配置
    search: {
        topK: 10,              // 初始返回数量
        rerankTopK: 5,        // Reranker 精排后返回数量
        vectorWeight: 0.6,    // 向量检索权重
        bm25Weight: 0.4,     // BM25 权重
        minScore: 0.3,        // 最低相关度阈值
    },
    
    // Reranker 配置
    reranker: {
        enabled: true,
        model: 'BAAI/bge-reranker-v2-m3',
        topK: 5,
    },
    
    // Chunk 配置
    chunk: {
        chunkSize: 500,      // 每个 chunk 的 token 数
        overlap: 50,          // 重叠 token 数
        minLength: 100,       // 最小 chunk 长度
    },
    
    // 嵌入模型
    embedding: {
        model: 'BAAI/bge-m3',
        dimension: 1024,
    }
};

// ============================================================
// 二、混合检索引擎
// ============================================================
class RAGEngine {
    constructor(options = {}) {
        this.config = { ...RAG_CONFIG, ...options };
        this.vectorIndex = new Map();      // 向量索引
        this.bm25Index = null;              // BM25 索引
        this.documents = new Map();         // 文档存储
        this.chunks = new Map();            // Chunk 存储
        this.chapterTrees = new Map();      // 章节树
        
        // 统计信息
        this.stats = {
            totalSearches: 0,
            avgLatency: 0,
            cacheHits: 0,
        };
    }

    // ------------------------------------------------
    // 2.1 文档管理
    // ------------------------------------------------
    
    /**
     * 添加文档到知识库
     * @param {Object} doc - 文档对象 {id, title, content, metadata}
     */
    addDocument(doc) {
        const { id, title, content, metadata = {} } = doc;
        
        // 存储文档
        this.documents.set(id, {
            id,
            title,
            content,
            metadata,
            createdAt: Date.now(),
            updatedAt: Date.now(),
        });
        
        // 切分 chunk
        const docChunks = this.chunkDocument(id, content, metadata);
        
        // 索引 chunks
        docChunks.forEach((chunk, index) => {
            const chunkId = `${id}_${index}`;
            this.chunks.set(chunkId, {
                id: chunkId,
                docId: id,
                title,
                content: chunk.text,
                position: index,
                anchor: chunk.anchor,
                metadata,
            });
            
            // 向量化（模拟）
            this.vectorIndex.set(chunkId, this.embedText(chunk.text));
            
            // BM25 索引
            this.bm25Index = this.bm25Index || new BM25Index();
            this.bm25Index.addDocument(chunkId, chunk.text);
        });
        
        // 生成章节树
        this.chapterTrees.set(id, this.buildChapterTree(content, id));
        
        return { id, chunkCount: docChunks.length };
    }

    /**
     * 文档切分 - 保留语义边界
     */
    chunkDocument(docId, content, metadata) {
        const chunks = [];
        const lines = content.split('\n');
        let currentChunk = [];
        let currentLength = 0;
        let currentAnchor = '';
        
        for (const line of lines) {
            const lineLength = line.length;
            
            // 检测标题（章节边界）
            if (line.match(/^#{1,3}\s/)) {
                currentAnchor = line.replace(/^#+\s*/, '').trim();
            }
            
            currentChunk.push(line);
            currentLength += lineLength;
            
            // 达到 chunk 大小
            if (currentLength >= this.config.chunk.chunkSize) {
                const text = currentChunk.join('\n').trim();
                if (text.length >= this.config.chunk.minLength) {
                    chunks.push({
                        text,
                        anchor: currentAnchor || metadata.title || 'main',
                    });
                }
                currentChunk = [];
                currentLength = 0;
            }
        }
        
        // 处理剩余内容
        if (currentChunk.length > 0) {
            const text = currentChunk.join('\n').trim();
            if (text.length >= this.config.chunk.minLength) {
                chunks.push({
                    text,
                    anchor: currentAnchor || metadata.title || 'main',
                });
            }
        }
        
        return chunks;
    }

    /**
     * 构建章节树
     */
    buildChapterTree(content, docId) {
        const lines = content.split('\n');
        const tree = {
            docId,
            title: '',
            sections: [],
        };
        
        let currentH1 = null;
        let currentH2 = null;
        
        for (const line of lines) {
            if (line.match(/^#\s/)) {
                tree.title = line.replace(/^#\s*/, '').trim();
                currentH1 = {
                    title: tree.title,
                    level: 1,
                    anchor: tree.title,
                    children: [],
                };
                tree.sections.push(currentH1);
                currentH2 = null;
            } else if (line.match(/^##\s/)) {
                const title = line.replace(/^##\s*/, '').trim();
                currentH2 = {
                    title,
                    level: 2,
                    anchor: title,
                    children: [],
                };
                if (currentH1) {
                    currentH1.children.push(currentH2);
                } else {
                    tree.sections.push(currentH2);
                }
            } else if (line.match(/^###\s/)) {
                const title = line.replace(/^###\s*/, '').trim();
                const h3 = {
                    title,
                    level: 3,
                    anchor: title,
                    children: [],
                };
                if (currentH2) {
                    currentH2.children.push(h3);
                } else if (currentH1) {
                    currentH1.children.push(h3);
                }
            }
        }
        
        return tree;
    }

    // ------------------------------------------------
    // 2.2 检索接口
    // ------------------------------------------------
    
    /**
     * 搜索 - 三阶段混合检索
     * @param {string} query - 查询文本
     * @param {Object} options - 检索选项
     */
    async search(query, options = {}) {
        const startTime = Date.now();
        this.stats.totalSearches++;
        
        const config = { ...this.config.search, ...options };
        
        // ========== Stage 1: 问题检索 ==========
        const queryExpanded = this.expandQuery(query);
        const queryVector = this.embedText(queryExpanded);
        
        // 向量检索
        const vectorResults = this.vectorSearch(queryVector, config.topK);
        
        // BM25 检索
        const bm25Results = this.bm25Search(query, config.topK);
        
        // ========== Stage 2: RRF 融合 ==========
        const fusedResults = this.rrfFusion(vectorResults, bm25Results);
        
        // ========== Stage 3: Reranker 精排 ==========
        let finalResults;
        if (config.rerank !== false && this.config.reranker.enabled) {
            finalResults = await this.rerank(query, fusedResults, config.rerankTopK);
        } else {
            finalResults = fusedResults.slice(0, config.rerankTopK);
        }
        
        // 父子节点注入
        const enrichedResults = this.enrichWithParentNodes(finalResults);
        
        // 统计
        this.stats.avgLatency = (
            (this.stats.avgLatency * (this.stats.totalSearches - 1) + (Date.now() - startTime))
            / this.stats.totalSearches
        );
        
        return {
            query,
            queryExpanded,
            results: enrichedResults,
            stats: {
                latency: Date.now() - startTime,
                totalIndexed: this.chunks.size,
                stage: '3-stage',
            }
        };
    }

    /**
     * 查询扩展
     */
    expandQuery(query) {
        // 简单实现：添加同义词扩展
        const expansions = {
            '配置': ['设置', 'config', 'settings', 'options'],
            '部署': ['deploy', '发布', '上线', 'install'],
            '错误': ['error', 'bug', '问题', 'issue'],
            '优化': ['optimize', '性能', 'performance', 'improve'],
        };
        
        let expanded = query;
        for (const [key, synonyms] of Object.entries(expansions)) {
            if (query.includes(key)) {
                expanded += ' ' + synonyms.join(' ');
            }
        }
        
        return expanded;
    }

    /**
     * 向量检索
     */
    vectorSearch(queryVector, topK) {
        const scores = [];
        
        for (const [chunkId, chunkVector] of this.vectorIndex) {
            const similarity = this.cosineSimilarity(queryVector, chunkVector);
            scores.push({ chunkId, score: similarity, type: 'vector' });
        }
        
        return scores
            .sort((a, b) => b.score - a.score)
            .slice(0, topK);
    }

    /**
     * BM25 检索
     */
    bm25Search(query, topK) {
        if (!this.bm25Index) return [];
        return this.bm25Index.search(query, topK);
    }

    /**
     * RRF 融合 (Reciprocal Rank Fusion)
     */
    rrfFusion(vectorResults, bm25Results, k = 60) {
        const fused = new Map();
        
        // 向量结果
        vectorResults.forEach((item, index) => {
            const score = 1 / (k + index + 1) * this.config.search.vectorWeight;
            fused.set(item.chunkId, {
                chunkId: item.chunkId,
                score: fused.get(item.chunkId)?.score || 0 + score,
                sources: ['vector'],
            });
        });
        
        // BM25 结果
        bm25Results.forEach((item, index) => {
            const score = 1 / (k + index + 1) * this.config.search.bm25Weight;
            const existing = fused.get(item.chunkId);
            if (existing) {
                existing.score += score;
                existing.sources.push('bm25');
            } else {
                fused.set(item.chunkId, {
                    chunkId: item.chunkId,
                    score,
                    sources: ['bm25'],
                });
            }
        });
        
        return Array.from(fused.values())
            .sort((a, b) => b.score - a.score);
    }

    /**
     * Reranker 精排
     */
    async rerank(query, results, topK = 5) {
        if (results.length === 0) return [];
        
        // 获取完整 chunk 内容
        const chunks = results.map(r => ({
            ...r,
            chunk: this.chunks.get(r.chunkId),
        })).filter(r => r.chunk);
        
        // 模拟 Reranker（实际应调用 Qwen3-Reranker 或 BGE-Reranker）
        // 这里使用简单的相关性计算
        const reranked = chunks.map(item => {
            const queryTerms = query.toLowerCase().split(/\s+/);
            const content = item.chunk.content.toLowerCase();
            
            // 计算术语覆盖率
            let termCoverage = 0;
            queryTerms.forEach(term => {
                if (content.includes(term)) termCoverage++;
            });
            
            // 综合评分
            const rerankScore = (termCoverage / queryTerms.length) * 0.6 + item.score * 0.4;
            
            return {
                ...item,
                rerankScore,
            };
        });
        
        return reranked
            .sort((a, b) => b.rerankScore - a.rerankScore)
            .slice(0, topK);
    }

    /**
     * 父子节点注入
     */
    enrichWithParentNodes(results) {
        return results.map(result => {
            const chunk = this.chunks.get(result.chunkId);
            if (!chunk) return result;
            
            // 获取父文档
            const parentDoc = this.documents.get(chunk.docId);
            
            // 获取章节树
            const chapterTree = this.chapterTrees.get(chunk.docId);
            
            // 查找当前 chunk 所在的章节
            let section = null;
            if (chapterTree) {
                section = this.findSection(chapterTree, chunk.anchor);
            }
            
            return {
                ...result,
                chunk,
                parentDoc: parentDoc ? {
                    id: parentDoc.id,
                    title: parentDoc.title,
                } : null,
                section,
                chapterTree,
            };
        });
    }

    /**
     * 查找章节
     */
    findSection(tree, anchor) {
        for (const section of tree.sections) {
            if (section.title === anchor || section.anchor === anchor) {
                return section;
            }
            if (section.children) {
                const found = this.findSectionInChildren(section.children, anchor);
                if (found) return found;
            }
        }
        return null;
    }

    findSectionInChildren(children, anchor) {
        for (const child of children) {
            if (child.title === anchor || child.anchor === anchor) {
                return child;
            }
            if (child.children) {
                const found = this.findSectionInChildren(child.children, anchor);
                if (found) return found;
            }
        }
        return null;
    }

    // ------------------------------------------------
    // 2.3 工具函数
    // ------------------------------------------------
    
    /**
     * 文本向量化（模拟）
     */
    embedText(text) {
        // 实际应调用 BGE-M3 API
        // 这里返回模拟向量
        const dim = this.config.embedding.dimension;
        const vector = new Array(dim).fill(0);
        
        // 简单哈希生成伪向量
        for (let i = 0; i < text.length; i++) {
            vector[i % dim] += text.charCodeAt(i);
        }
        
        // L2 归一化
        const norm = Math.sqrt(vector.reduce((sum, v) => sum + v * v, 0));
        return vector.map(v => v / norm);
    }

    /**
     * 余弦相似度
     */
    cosineSimilarity(a, b) {
        let dotProduct = 0;
        for (let i = 0; i < a.length; i++) {
            dotProduct += a[i] * b[i];
        }
        return dotProduct;
    }

    /**
     * 获取统计信息
     */
    getStats() {
        return {
            ...this.stats,
            totalDocuments: this.documents.size,
            totalChunks: this.chunks.size,
            vectorIndexSize: this.vectorIndex.size,
        };
    }

    /**
     * 导出章节树
     */
    exportChapterTrees() {
        return Object.fromEntries(this.chapterTrees);
    }

    /**
     * 清除索引
     */
    clear() {
        this.vectorIndex.clear();
        this.bm25Index = null;
        this.documents.clear();
        this.chunks.clear();
        this.chapterTrees.clear();
        this.stats = {
            totalSearches: 0,
            avgLatency: 0,
            cacheHits: 0,
        };
    }
}

// ============================================================
// 三、BM25 索引（简化实现）
// ============================================================
class BM25Index {
    constructor(k1 = 1.5, b = 0.75) {
        this.k1 = k1;
        this.b = b;
        this.documents = new Map();
        this.avgDocLength = 0;
        this.docCount = 0;
        this.termDocFreq = new Map();  // term -> doc frequency
        this.totalLength = 0;
    }

    addDocument(docId, text) {
        const terms = this.tokenize(text);
        const docLength = terms.length;
        
        this.documents.set(docId, { terms, docLength });
        this.totalLength += docLength;
        this.docCount++;
        this.avgDocLength = this.totalLength / this.docCount;
        
        // 统计词项文档频率
        const uniqueTerms = new Set(terms);
        uniqueTerms.forEach(term => {
            this.termDocFreq.set(term, (this.termDocFreq.get(term) || 0) + 1);
        });
    }

    tokenize(text) {
        return text
            .toLowerCase()
            .replace(/[^\w\s]/g, ' ')
            .split(/\s+/)
            .filter(term => term.length > 1);
    }

    search(query, topK = 10) {
        const queryTerms = this.tokenize(query);
        const scores = [];
        
        for (const [docId, doc] of this.documents) {
            let score = 0;
            
            for (const term of queryTerms) {
                const termFreq = doc.terms.filter(t => t === term).length;
                if (termFreq === 0) continue;
                
                const docFreq = this.termDocFreq.get(term) || 0;
                const idf = Math.log((this.docCount - docFreq + 0.5) / (docFreq + 0.5) + 1);
                
                const numerator = termFreq * (this.k1 + 1);
                const denominator = termFreq + this.k1 * (1 - this.b + this.b * doc.docLength / this.avgDocLength);
                
                score += idf * (numerator / denominator);
            }
            
            if (score > 0) {
                scores.push({ chunkId: docId, score, type: 'bm25' });
            }
        }
        
        return scores.sort((a, b) => b.score - a.score).slice(0, topK);
    }
}

// ============================================================
// 四、全局实例
// ============================================================
const ragEngine = new RAGEngine();

// ============================================================
// 五、导出
// ============================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RAGEngine, BM25Index, ragEngine, RAG_CONFIG };
}
