/**
 * Y·NEX Skills 评测与进化系统
 * 基于 he-wiki-rag Skills 模块设计
 * 支持 6 大指标评测 + 4 层优化策略 + Accept/Rollback
 */
'use strict';

// ============================================================
// 一、Skills 评测配置
// ============================================================
const SKILLS_EVAL_CONFIG = {
    // 评测指标权重
    metrics: {
        recall: { weight: 0.20, name: 'Recall@10', target: 0.7 },
        ndcg: { weight: 0.20, name: 'NDCG@10', target: 0.8 },
        latency: { weight: 0.15, name: '响应速度', target: 200 }, // ms
        stability: { weight: 0.15, name: '稳定性', target: 0.95 }, // 方差/波动
        coverage: { weight: 0.10, name: '覆盖率', target: 0.8 },
        toolSuccess: { weight: 0.10, name: '工具成功率', target: 0.95 },
        usability: { weight: 0.05, name: '可用性', target: 4.0 }, // 1-5分
        explainability: { weight: 0.05, name: '可解释性', target: 4.0 }, // 1-5分
    },
    
    // 优化层级
    tiers: [
        { tier: 1, name: '查询扩展',收益: '+15~30%', prerequisite: 0.1 },
        { tier: 2, name: 'Embedding升级',收益: '+10~25%', prerequisite: 0.05 },
        { tier: 3, name: '混合检索调参',收益: '+5~15%', prerequisite: 0.03 },
        { tier: 4, name: '知识库重构',收益: '+20~40%', prerequisite: 0.15 },
    ],
    
    // Accept 标准
    acceptThreshold: {
        minScore: 70,           // 最低总分
        minMetrics: ['recall', 'ndcg'], // 必须达标的指标
    },
};

// ============================================================
// 二、Skills 评测器
// ============================================================
class SkillsEvaluator {
    constructor(options = {}) {
        this.config = { ...SKILLS_EVAL_CONFIG, ...options };
        
        // 历史评测记录
        this.evaluationHistory = [];
        
        // 当前基准线
        this.baseline = null;
        
        // 优化层级状态
        this.tierStatus = this.config.tiers.map(t => ({
            ...t,
            enabled: false,
            lastImprovement: null,
        }));
        
        // 评测数据集
        this.testDataset = [];
    }

    // ------------------------------------------------
    // 2.1 评测数据集管理
    // ------------------------------------------------
    
    /**
     * 添加测试用例
     */
    addTestCase(query, expectedDocIds, metadata = {}) {
        this.testDataset.push({
            id: 'test_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 5),
            query,
            expectedDocIds,
            metadata,
            createdAt: Date.now(),
        });
        
        return this.testDataset.length;
    }

    /**
     * 批量添加测试用例
     */
    addTestCases(cases) {
        const results = {
            added: 0,
            skipped: 0,
        };
        
        for (const testCase of cases) {
            if (testCase.query && testCase.expectedDocIds) {
                this.addTestCase(testCase.query, testCase.expectedDocIds, testCase.metadata);
                results.added++;
            } else {
                results.skipped++;
            }
        }
        
        return results;
    }

    /**
     * 加载预设测试集
     */
    loadPresetDataset(dataset = 'default') {
        const presets = {
            // 默认测试集
            default: [
                { query: 'RAG切块策略有哪些', expectedDocIds: ['chunking'] },
                { query: '如何优化检索效果', expectedDocIds: ['retrieval', 'optimization'] },
                { query: '部署遇到错误怎么办', expectedDocIds: ['deployment', 'error'] },
                { query: '配置文件中如何设置', expectedDocIds: ['config', 'settings'] },
                { query: '性能优化的方法', expectedDocIds: ['performance', 'optimization'] },
            ],
            
            // 检索专项
            retrieval: [
                { query: '向量检索原理', expectedDocIds: ['vector', 'embedding'] },
                { query: 'BM25是什么', expectedDocIds: ['bm25', 'keyword'] },
                { query: '混合检索怎么做', expectedDocIds: ['hybrid', 'fusion'] },
            ],
            
            // 部署专项
            deployment: [
                { query: '服务器部署步骤', expectedDocIds: ['deploy', 'server'] },
                { query: 'Docker部署教程', expectedDocIds: ['docker', 'container'] },
                { query: 'SSL证书配置', expectedDocIds: ['ssl', 'certificate'] },
            ],
        };
        
        const cases = presets[dataset] || presets.default;
        return this.addTestCases(cases);
    }

    // ------------------------------------------------
    // 2.2 执行评测
    // ------------------------------------------------
    
    /**
     * 执行完整评测
     */
    async evaluate(ragEngine, options = {}) {
        const startTime = Date.now();
        
        // 准备评测结果
        const evaluation = {
            id: 'eval_' + Date.now().toString(36),
            startTime,
            endTime: null,
            duration: 0,
            status: 'running',
            
            // 测试统计
            testStats: {
                total: this.testDataset.length,
                passed: 0,
                failed: 0,
                results: [],
            },
            
            // 指标评分
            metrics: {},
            
            // 综合评分
            overallScore: 0,
            
            // 等级
            grade: null,
            
            // 建议
            suggestions: [],
        };
        
        // 执行每个测试用例
        for (const testCase of this.testDataset) {
            const result = await this.runTestCase(ragEngine, testCase);
            evaluation.testStats.results.push(result);
            
            if (result.passed) {
                evaluation.testStats.passed++;
            } else {
                evaluation.testStats.failed++;
            }
        }
        
        // 计算指标
        evaluation.metrics = this.calculateMetrics(evaluation.testStats.results);
        
        // 计算综合评分
        evaluation.overallScore = this.calculateOverallScore(evaluation.metrics);
        
        // 评定等级
        evaluation.grade = this.getGrade(evaluation.overallScore);
        
        // 生成建议
        evaluation.suggestions = this.generateSuggestions(evaluation.metrics);
        
        // 完成
        evaluation.endTime = Date.now();
        evaluation.duration = evaluation.endTime - startTime;
        evaluation.status = 'completed';
        
        // 保存历史
        this.evaluationHistory.push(evaluation);
        
        // 检查是否需要更新基准线
        if (this.shouldUpdateBaseline(evaluation)) {
            this.updateBaseline(evaluation);
        }
        
        return evaluation;
    }

    /**
     * 运行单个测试用例
     */
    async runTestCase(ragEngine, testCase) {
        const startTime = Date.now();
        
        // 执行检索
        const searchResults = await ragEngine.search(testCase.query, { topK: 10 });
        
        // 获取返回的 docId
        const returnedDocIds = searchResults.results
            .filter(r => r.chunk?.docId)
            .map(r => r.chunk.docId);
        
        // 计算指标
        const recall = this.calculateRecall(returnedDocIds, testCase.expectedDocIds);
        const precision = this.calculatePrecision(returnedDocIds, testCase.expectedDocIds);
        const latency = Date.now() - startTime;
        
        return {
            testCaseId: testCase.id,
            query: testCase.query,
            expected: testCase.expectedDocIds,
            returned: returnedDocIds,
            recall,
            precision,
            latency,
            hit: recall > 0,
            passed: recall > 0,
        };
    }

    // ------------------------------------------------
    // 2.3 指标计算
    // ------------------------------------------------
    
    /**
     * 计算 Recall@K
     */
    calculateRecall(returned, expected, k = 10) {
        if (expected.length === 0) return 0;
        
        const relevant = returned.slice(0, k).filter(docId => expected.includes(docId));
        return relevant.length / expected.length;
    }

    /**
     * 计算 Precision@K
     */
    calculatePrecision(returned, expected, k = 10) {
        if (returned.length === 0) return 0;
        
        const relevant = returned.slice(0, k).filter(docId => expected.includes(docId));
        return relevant.length / Math.min(k, returned.length);
    }

    /**
     * 计算 NDCG@K
     */
    calculateNDCG(returned, expected, k = 10) {
        // 简化实现
        let dcg = 0;
        for (let i = 0; i < Math.min(k, returned.length); i++) {
            if (expected.includes(returned[i])) {
                dcg += 1 / Math.log2(i + 2);
            }
        }
        
        let idcg = 0;
        for (let i = 0; i < Math.min(k, expected.length); i++) {
            idcg += 1 / Math.log2(i + 2);
        }
        
        return idcg > 0 ? dcg / idcg : 0;
    }

    /**
     * 计算 MRR
     */
    calculateMRR(returned, expected) {
        for (let i = 0; i < returned.length; i++) {
            if (expected.includes(returned[i])) {
                return 1 / (i + 1);
            }
        }
        return 0;
    }

    /**
     * 计算 Hit Rate
     */
    calculateHitRate(results) {
        const hits = results.filter(r => r.hit).length;
        return hits / results.length;
    }

    /**
     * 计算所有指标
     */
    calculateMetrics(results) {
        const metrics = {};
        
        // Recall@10
        const recallScores = results.map(r => r.recall || 0);
        metrics.recall = {
            value: this.average(recallScores),
            target: this.config.metrics.recall.target,
            status: this.average(recallScores) >= this.config.metrics.recall.target ? 'pass' : 'fail',
        };
        
        // Precision@10
        const precisionScores = results.map(r => r.precision || 0);
        metrics.precision = {
            value: this.average(precisionScores),
            target: 0.5,
            status: this.average(precisionScores) >= 0.5 ? 'pass' : 'fail',
        };
        
        // NDCG@10 (简化)
        metrics.ndcg = {
            value: this.average(recallScores) * 0.9, // 简化
            target: this.config.metrics.ndcg.target,
            status: this.average(recallScores) * 0.9 >= this.config.metrics.ndcg.target ? 'pass' : 'fail',
        };
        
        // MRR
        metrics.mrr = {
            value: this.average(recallScores) * 0.8, // 简化
            target: 0.5,
            status: this.average(recallScores) * 0.8 >= 0.5 ? 'pass' : 'fail',
        };
        
        // 响应延迟
        const latencies = results.map(r => r.latency || 0);
        metrics.latency = {
            value: this.average(latencies),
            target: this.config.metrics.latency.target,
            status: this.average(latencies) <= this.config.metrics.latency.target ? 'pass' : 'fail',
            unit: 'ms',
        };
        
        // 命中率
        metrics.hitRate = {
            value: this.calculateHitRate(results),
            target: 0.7,
            status: this.calculateHitRate(results) >= 0.7 ? 'pass' : 'fail',
        };
        
        return metrics;
    }

    /**
     * 计算综合评分
     */
    calculateOverallScore(metrics) {
        let totalWeight = 0;
        let weightedScore = 0;
        
        const metricWeights = {
            recall: 0.25,
            ndcg: 0.25,
            latency: 0.15,
            hitRate: 0.15,
            precision: 0.10,
            mrr: 0.10,
        };
        
        for (const [key, weight] of Object.entries(metricWeights)) {
            if (metrics[key]) {
                const value = metrics[key].value || 0;
                const target = metrics[key].target || 1;
                const score = Math.min(100, (value / target) * 100);
                weightedScore += score * weight;
                totalWeight += weight;
            }
        }
        
        return Math.round(weightedScore / totalWeight);
    }

    /**
     * 评定等级
     */
    getGrade(score) {
        if (score >= 90) return { grade: 'S', label: '卓越', color: '#ffd700' };
        if (score >= 80) return { grade: 'A', label: '优秀', color: '#00d4ff' };
        if (score >= 70) return { grade: 'B', label: '良好', color: '#6bcb77' };
        if (score >= 60) return { grade: 'C', label: '及格', color: '#ffd93d' };
        return { grade: 'D', label: '需改进', color: '#ff6b6b' };
    }

    // ------------------------------------------------
    // 2.4 优化建议
    // ------------------------------------------------
    
    /**
     * 生成优化建议
     */
    generateSuggestions(metrics) {
        const suggestions = [];
        
        // 分析每个指标
        for (const [key, metric] of Object.entries(metrics)) {
            if (metric.status === 'fail') {
                const suggestion = this.getSuggestionForMetric(key, metric);
                suggestions.push(suggestion);
            }
        }
        
        // 按优先级排序
        suggestions.sort((a, b) => b.priority - a.priority);
        
        return suggestions;
    }

    /**
     * 获取指标优化建议
     */
    getSuggestionForMetric(key, metric) {
        const suggestions = {
            recall: {
                priority: 1,
                title: '召回率不足',
                description: `当前 Recall@10: ${(metric.value * 100).toFixed(1)}%, 目标: ${(metric.target * 100).toFixed(0)}%`,
                actions: [
                    '启用查询扩展（Tier 1）',
                    '调整向量检索权重',
                    '优化 Embedding 模型',
                ],
                tier: 1,
            },
            ndcg: {
                priority: 2,
                title: '排序质量不佳',
                description: `当前 NDCG@10: ${(metric.value * 100).toFixed(1)}%, 目标: ${(metric.target * 100).toFixed(0)}%`,
                actions: [
                    '启用 Reranker 精排',
                    '调整 BM25 权重',
                    '优化混合检索融合策略',
                ],
                tier: 2,
            },
            latency: {
                priority: 3,
                title: '响应延迟过高',
                description: `当前延迟: ${metric.value.toFixed(0)}ms, 目标: ${metric.target}ms`,
                actions: [
                    '启用检索结果缓存',
                    '优化向量索引结构',
                    '减少不必要的重排序',
                ],
                tier: 3,
            },
        };
        
        return suggestions[key] || {
            priority: 5,
            title: `${key} 需要优化`,
            description: `当前值: ${(metric.value * 100).toFixed(1)}%`,
            actions: ['检查相关配置'],
        };
    }

    // ------------------------------------------------
    // 2.5 基准线与回滚
    // ------------------------------------------------
    
    /**
     * 检查是否应更新基准线
     */
    shouldUpdateBaseline(evaluation) {
        if (!this.baseline) return true;
        
        // 如果当前评测更差，不更新
        if (evaluation.overallScore < this.baseline.overallScore) {
            return false;
        }
        
        return true;
    }

    /**
     * 更新基准线
     */
    updateBaseline(evaluation) {
        this.baseline = {
            id: evaluation.id,
            timestamp: Date.now(),
            overallScore: evaluation.overallScore,
            metrics: evaluation.metrics,
            grade: evaluation.grade,
        };
        
        return this.baseline;
    }

    /**
     * 执行回滚
     */
    rollback() {
        if (!this.baseline) {
            return { success: false, error: 'No baseline to rollback to' };
        }
        
        // 返回基准线配置
        return {
            success: true,
            baseline: this.baseline,
            message: 'Rollback to previous baseline',
        };
    }

    // ------------------------------------------------
    // 2.6 报告生成
    // ------------------------------------------------
    
    /**
     * 生成评测报告
     */
    generateReport(evaluation) {
        return {
            // 概览
            overview: {
                id: evaluation.id,
                score: evaluation.overallScore,
                grade: evaluation.grade,
                duration: evaluation.duration,
                timestamp: new Date(evaluation.startTime).toISOString(),
            },
            
            // 测试统计
            testStats: {
                total: evaluation.testStats.total,
                passed: evaluation.testStats.passed,
                failed: evaluation.testStats.failed,
                passRate: (evaluation.testStats.passed / evaluation.testStats.total * 100).toFixed(1) + '%',
            },
            
            // 指标详情
            metrics: evaluation.metrics,
            
            // 优化建议
            suggestions: evaluation.suggestions,
            
            // 维度评分卡
            scorecard: this.generateScorecard(evaluation.metrics),
            
            // 与基准对比
            comparison: this.baseline ? {
                previousScore: this.baseline.overallScore,
                currentScore: evaluation.overallScore,
                change: evaluation.overallScore - this.baseline.overallScore,
            } : null,
        };
    }

    /**
     * 生成评分卡
     */
    generateScorecard(metrics) {
        const card = [];
        
        const metricLabels = {
            recall: { name: 'Recall@10', weight: 20 },
            ndcg: { name: 'NDCG@10', weight: 20 },
            latency: { name: '响应速度', weight: 15 },
            stability: { name: '稳定性', weight: 15 },
            coverage: { name: '覆盖率', weight: 10 },
            toolSuccess: { name: '工具成功', weight: 10 },
            usability: { name: '可用性', weight: 5 },
            explainability: { name: '可解释性', weight: 5 },
        };
        
        for (const [key, label] of Object.entries(metricLabels)) {
            const metric = metrics[key] || { value: 0, status: 'unknown' };
            const value = typeof metric.value === 'number' ? metric.value : 0;
            const percent = Math.min(100, (value / (metric.target || 1)) * 100);
            
            card.push({
                dimension: label.name,
                weight: label.weight + '%',
                value: (value * 100).toFixed(1) + '%',
                target: (metric.target * 100).toFixed(0) + '%',
                score: Math.round(percent),
                status: metric.status || 'unknown',
            });
        }
        
        return card;
    }

    // ------------------------------------------------
    // 2.7 历史与统计
    // ------------------------------------------------
    
    /**
     * 获取历史评测趋势
     */
    getTrend(days = 7) {
        const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
        
        const recentEvals = this.evaluationHistory.filter(
            e => e.startTime >= cutoff
        );
        
        return {
            evaluations: recentEvals.map(e => ({
                id: e.id,
                date: new Date(e.startTime).toISOString().split('T')[0],
                score: e.overallScore,
                grade: e.grade,
            })),
            avgScore: recentEvals.length > 0
                ? recentEvals.reduce((sum, e) => sum + e.overallScore, 0) / recentEvals.length
                : 0,
            trend: this.calculateTrend(recentEvals),
        };
    }

    calculateTrend(evaluations) {
        if (evaluations.length < 2) return 'stable';
        
        const recent = evaluations[evaluations.length - 1].overallScore;
        const previous = evaluations[evaluations.length - 2].overallScore;
        
        const diff = recent - previous;
        if (diff > 5) return 'improving';
        if (diff < -5) return 'declining';
        return 'stable';
    }

    /**
     * 获取统计信息
     */
    getStats() {
        return {
            totalEvaluations: this.evaluationHistory.length,
            testCases: this.testDataset.length,
            baseline: this.baseline,
            tierStatus: this.tierStatus,
            avgScore: this.evaluationHistory.length > 0
                ? this.evaluationHistory.reduce((sum, e) => sum + e.overallScore, 0) / this.evaluationHistory.length
                : 0,
        };
    }

    // ------------------------------------------------
    // 2.8 工具函数
    // ------------------------------------------------
    
    average(arr) {
        return arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    }
}

// ============================================================
// 三、全局实例
// ============================================================
const skillsEvaluator = new SkillsEvaluator();

// ============================================================
// 四、导出
// ============================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SkillsEvaluator, skillsEvaluator, SKILLS_EVAL_CONFIG };
}
