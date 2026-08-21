import { useState } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { workflowEngineApi } from '@/api/workflows'
import { useWorkflowStream } from '@/hooks/useWorkflowStream'
import { CheckCircle, Loader, Circle, XCircle } from 'lucide-react'

export default function ExecutionPanel() {
  const { nodes, edges, isExecuting, executionDetail, setIsExecuting, setExecutionDetail } = useEditorStore()
  const [error, setError] = useState<string | null>(null)
  const [executionId, setExecutionId] = useState<string | null>(null)
  const stream = useWorkflowStream(executionId)

  const handleExecute = async () => {
    setIsExecuting(true)
    setError(null)
    try {
      const res = await workflowEngineApi.execute({
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type,
          params: (n.data.params || {}) as Record<string, unknown>,
        })),
        edges: edges.map((e) => ({
          from: e.source,
          to: e.target,
          from_port: e.sourceHandle || '',
          to_port: e.targetHandle || '',
        })),
      })
      setExecutionDetail(res.data.data)
      setExecutionId(res.data.data.execution_id)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '执行失败')
    } finally {
      setIsExecuting(false)
    }
  }

  const handleCancel = async () => {
    if (!executionDetail) return
    try {
      await workflowEngineApi.cancelExecution(executionDetail.execution_id)
    } catch (e) {
      console.error(e)
    }
  }

  // 优先使用 stream 实时数据，回退到 executionDetail 同步数据
  const streamActive = stream.status !== 'idle' && stream.status !== undefined
  const status = streamActive ? stream.status : executionDetail?.status
  const progress = executionDetail?.progress
  const progressPercent = streamActive && stream.total > 0
    ? Math.round(stream.progress * 100)
    : progress ? Math.round(progress.progress * 100) : 0
  const completed = streamActive && stream.total > 0 ? stream.completed : progress?.completed ?? 0
  const total = streamActive && stream.total > 0 ? stream.total : progress?.total ?? 0
  const isRunning = isExecuting || status === 'running'
  const streamNodes = Object.values(stream.nodes)

  return (
    <div className="h-32 bg-[#181825] border-t border-[#313244] flex flex-col px-4 py-2 gap-2">
      <div className="flex items-center gap-4">
        <button
          onClick={handleExecute}
          disabled={isExecuting || nodes.length === 0}
          className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded text-sm font-medium"
        >
          {isExecuting ? '执行中...' : '▶ 执行工作流'}
        </button>

        {isRunning && (
          <button
            onClick={handleCancel}
            className="px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded text-sm"
          >
            取消
          </button>
        )}

        {error && (
          <div className="text-red-400 text-sm">错误: {error}</div>
        )}

        {(executionDetail || streamActive) && (
          <div className="flex-1 flex items-center gap-4">
            <div className="text-sm">
              <span className="text-gray-400">状态: </span>
              <span className={
                status === 'completed' ? 'text-emerald-400' :
                status === 'failed' ? 'text-red-400' :
                status === 'cancelled' ? 'text-yellow-400' :
                'text-blue-400'
              }>
                {status}
              </span>
            </div>
            {total > 0 && (
              <>
                <div className="text-sm text-gray-400">
                  进度: {completed}/{total}
                </div>
                <div className="flex-1 max-w-xs bg-[#313244] rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-indigo-500 h-full transition-all"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="text-sm text-gray-400">
                  {progressPercent}%
                </div>
                {progress?.duration && (
                  <div className="text-sm text-gray-400">
                    耗时: {progress.duration}s
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* 节点实时详情 - 来自 WebSocket stream */}
      {streamNodes.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto flex-1">
          {streamNodes.map((node) => (
            <div
              key={node.nodeId}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs border whitespace-nowrap ${
                node.status === 'completed' ? 'border-emerald-500 text-emerald-400' :
                node.status === 'running' ? 'border-blue-500 text-blue-400' :
                node.status === 'failed' ? 'border-red-500 text-red-400' :
                'border-gray-600 text-gray-400'
              }`}
              title={node.error || `${node.nodeId}: ${node.status}`}
            >
              {node.status === 'completed' && <CheckCircle size={12} />}
              {node.status === 'running' && <Loader size={12} className="animate-spin" />}
              {node.status === 'pending' && <Circle size={12} />}
              {node.status === 'failed' && <XCircle size={12} />}
              <span>{node.nodeId}</span>
              {node.durationMs && (
                <span className="text-gray-500 ml-1">{node.durationMs}ms</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
