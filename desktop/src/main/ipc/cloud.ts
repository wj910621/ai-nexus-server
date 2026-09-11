/**
 * R3/R4b 云服务 IPC handlers（模板市场 / 云资产同步 / 云渲染队列 / 语音合成）
 * 渲染层 file:// 源无法直连主站 API，统一经主进程代理（同时复用主站 token，token 不出主进程）。
 */
import { ipcMain, app } from 'electron'
import path from 'path'
import fs from 'fs'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { createCloudService, type AssetInput, type CloudService } from '../services/cloud-service'

let svc: CloudService | null = null

function service(): CloudService {
  if (!svc) svc = createCloudService()
  return svc
}

export function registerCloudHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.CLOUD_TEMPLATES, (_e, args: { genre?: string } = {}) =>
    service().templates(args?.genre),
  )
  ipcMain.handle(IPC_CHANNELS.CLOUD_ASSET_LIST, (_e, args: { kind?: string } = {}) =>
    service().listAssets(args?.kind),
  )
  ipcMain.handle(IPC_CHANNELS.CLOUD_ASSET_SAVE, (_e, args: AssetInput) =>
    service().saveAsset(args || { content: '' }),
  )
  ipcMain.handle(IPC_CHANNELS.CLOUD_ASSET_DELETE, (_e, args: { id?: number } = {}) =>
    service().deleteAsset(Number(args?.id)),
  )
  ipcMain.handle(
    IPC_CHANNELS.CLOUD_JOB_ENQUEUE,
    (
      _e,
      args: { templateSlug?: string; premise?: string; idempotency?: string; shots?: { prompt: string }[] } = {},
    ) =>
      service().enqueueJob({
        templateSlug: String(args?.templateSlug || ''),
        premise: args?.premise,
        idempotency: args?.idempotency,
        shots: args?.shots,
      }),
  )
  ipcMain.handle(IPC_CHANNELS.CLOUD_JOB_LIST, () => service().listJobs())

  // R4b-3 语音合成：拿回 base64 后落盘 userData/audio/，返回路径与可直接播放的 dataUrl
  ipcMain.handle(
    IPC_CHANNELS.CLOUD_TTS,
    async (_e, args: { text: string; voice?: string; speed?: number }) => {
      const r = await service().tts(args || { text: '' })
      if (!r.ok) return r
      const data = r.data
      let filePath: string | undefined
      try {
        const dir = path.join(app.getPath('userData'), 'audio')
        fs.mkdirSync(dir, { recursive: true })
        filePath = path.join(dir, `tts_${Date.now()}.${data.format}`)
        fs.writeFileSync(filePath, Buffer.from(data.audioBase64, 'base64'))
      } catch {
        /* 落盘失败不阻断：仍返回 dataUrl 供播放 */
      }
      const mime = data.format === 'mp3' ? 'mpeg' : data.format
      return { ok: true, data: { ...data, filePath, dataUrl: `data:audio/${mime};base64,${data.audioBase64}` } }
    },
  )
}
