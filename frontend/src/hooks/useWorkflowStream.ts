import { useEffect, useState } from 'react'
import { useWebSocket } from './useWebSocket'

export interface WorkflowNodeState {
  nodeId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: unknown
  error?: string
  durationMs?: number
}

export interface WorkflowStreamState {
  nodes: Record<string, WorkflowNodeState>
  completed: number
  total: number
  progress: number
  status: 'idle' | 'running' | 'completed' | 'failed'
  totalDurationMs?: number
}

/**
 * 订阅工作流执行进度
 * @param executionId 执行 ID；传 null 不订阅
 */
export function useWorkflowStream(executionId: string | null): WorkflowStreamState {
  const lastMsg = useWebSocket(executionId ? `workflow:${executionId}` : null)
  const [state, setState] = useState<WorkflowStreamState>({
    nodes: {},
    completed: 0,
    total: 0,
    progress: 0,
    status: 'idle',
  })

  useEffect(() => {
    if (!lastMsg || !executionId) return

    setState((prev) => {
      switch (lastMsg.type) {
        case 'node_start':
          return {
            ...prev,
            status: 'running',
            nodes: {
              ...prev.nodes,
              [lastMsg.node_id as string]: {
                nodeId: lastMsg.node_id as string,
                status: 'running',
              },
            },
          }
        case 'node_complete':
          return {
            ...prev,
            nodes: {
              ...prev.nodes,
              [lastMsg.node_id as string]: {
                nodeId: lastMsg.node_id as string,
                status: 'completed',
                result: lastMsg.result,
                durationMs: lastMsg.duration_ms as number,
              },
            },
          }
        case 'node_error':
          return {
            ...prev,
            nodes: {
              ...prev.nodes,
              [lastMsg.node_id as string]: {
                nodeId: lastMsg.node_id as string,
                status: 'failed',
                error: lastMsg.error as string,
              },
            },
          }
        case 'progress':
          return {
            ...prev,
            completed: lastMsg.completed as number,
            total: lastMsg.total as number,
            progress: lastMsg.progress as number,
          }
        case 'execution_complete':
          return {
            ...prev,
            status: lastMsg.status as 'completed' | 'failed',
            totalDurationMs: lastMsg.total_duration_ms as number,
          }
        default:
          return prev
      }
    })
  }, [lastMsg, executionId])

  return state
}
