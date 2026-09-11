/**
 * R4b-4 节点编辑器页面
 *  - 画布：复用既有 WorkflowEditor（React Flow + 节点面板 + 执行面板）
 *  - 与 ComfyUI 互通：导入/导出 API 格式工作流 JSON，可直接提交本机 ComfyUI 渲染
 */
import { useRef, useState } from 'react'
import { Button, Input, Modal, Space, Tag, Tooltip, Typography, message } from 'antd'
import {
  ImportOutlined, ExportOutlined, DeleteOutlined, ExperimentOutlined, ApartmentOutlined,
} from '@ant-design/icons'
import WorkflowEditor from '@/components/workflow/WorkflowEditor'
import { useEditorStore } from '@/stores/editorStore'
import { canvasToComfy, comfyToCanvas, parseComfyJson, stringifyComfy, type ComfyGraph } from '@/utils/comfyGraph'

/** 内置标准文生图工作流（与桌面端 comfy-service 的默认模板同构） */
const SD15_TXT2IMG: ComfyGraph = {
  '3': {
    class_type: 'KSampler',
    inputs: { seed: 0, steps: 24, cfg: 7, sampler_name: 'dpmpp_2m', scheduler: 'karras', denoise: 1, model: ['4', 0], positive: ['6', 0], negative: ['7', 0], latent_image: ['5', 0] },
  },
  '4': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: 'v1-5-pruned-emaonly.safetensors' } },
  '5': { class_type: 'EmptyLatentImage', inputs: { width: 512, height: 512, batch_size: 1 } },
  '6': { class_type: 'CLIPTextEncode', inputs: { text: 'a hero standing on ruins, cinematic', clip: ['4', 1] } },
  '7': { class_type: 'CLIPTextEncode', inputs: { text: 'lowres, blurry, worst quality', clip: ['4', 1] } },
  '8': { class_type: 'VAEDecode', inputs: { samples: ['3', 0], vae: ['4', 2] } },
  '9': { class_type: 'SaveImage', inputs: { filename_prefix: 'YNEX', images: ['8', 0] } },
}

export default function WorkflowPage() {
  const nodes = useEditorStore((s) => s.nodes)
  const edges = useEditorStore((s) => s.edges)
  const setNodes = useEditorStore((s) => s.setNodes)
  const setEdges = useEditorStore((s) => s.setEdges)

  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const applyGraph = (graph: ComfyGraph, note: string) => {
    const { nodes: n, edges: e } = comfyToCanvas(graph)
    setNodes(n as never)
    setEdges(e as never)
    void message.success(`${note}：${n.length} 节点 / ${e.length} 连线`)
  }

  const doImport = () => {
    const r = parseComfyJson(importText)
    if (!r.ok) {
      void message.error(r.message)
      return
    }
    applyGraph(r.graph, '已导入 ComfyUI 工作流')
    setImportOpen(false)
    setImportText('')
  }

  const onFile = async (f: File | undefined) => {
    if (!f) return
    const text = await f.text()
    const r = parseComfyJson(text)
    if (!r.ok) {
      void message.error(r.message)
      return
    }
    applyGraph(r.graph, `已从 ${f.name} 导入`)
  }

  const doExport = () => {
    if (nodes.length === 0) {
      void message.info('画布为空，无可导出内容')
      return
    }
    const graph = canvasToComfy(nodes as never, edges as never)
    const blob = new Blob([stringifyComfy(graph)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `comfy-workflow-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    void message.success('已导出 ComfyUI 工作流 JSON（可直接提交 /prompt）')
  }

  const doClear = () => {
    setNodes([] as never)
    setEdges([] as never)
    void message.success('画布已清空')
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-3 border-b border-[#313244] flex items-center justify-between">
        <div>
          <Typography.Title level={4} className="!text-white !mb-1 flex items-center gap-2">
            <ApartmentOutlined /> 节点工作流
          </Typography.Title>
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <span>拖拽搭建 / 连线编排，可与 ComfyUI 工作流 JSON 双向互通</span>
            <Tag color="default" style={{ fontSize: 10 }}>{nodes.length} 节点 · {edges.length} 连线</Tag>
          </div>
        </div>
        <Space size={8}>
          <Tooltip title="载入内置 SD1.5 文生图工作流">
            <Button size="small" icon={<ExperimentOutlined />} onClick={() => applyGraph(SD15_TXT2IMG, '已载入内置模板')}>
              载入模板
            </Button>
          </Tooltip>
          <Button size="small" icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>
            导入 JSON
          </Button>
          <Button size="small" icon={<ExportOutlined />} onClick={doExport} disabled={nodes.length === 0}>
            导出 JSON
          </Button>
          <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={doClear} disabled={nodes.length === 0}>
            清空
          </Button>
        </Space>
      </div>

      <div className="flex-1 min-h-0">
        <WorkflowEditor />
      </div>

      <Modal
        title="导入 ComfyUI 工作流"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        onOk={doImport}
        okText="导入"
        width={640}
      >
        <div className="space-y-2">
          <div className="text-xs text-gray-500">
            粘贴 ComfyUI 的 <b>API 格式</b> 工作流（<code>{'{ "3": { "class_type": ... } }'}</code>），
            或从「开发模式 → Save (API Format)」导出的 JSON。
          </div>
          <Input.TextArea
            rows={10}
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder='{"3":{"class_type":"KSampler","inputs":{...}}}'
          />
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            style={{ display: 'none' }}
            onChange={(e) => {
              void onFile(e.target.files?.[0])
              e.target.value = ''
            }}
          />
          <Button size="small" onClick={() => fileRef.current?.click()}>
            从文件选择…
          </Button>
        </div>
      </Modal>
    </div>
  )
}
