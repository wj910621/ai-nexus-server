/**
 * R3 云服务 IPC handlers（模板市场 / 云端资产同步 / 云渲染队列）
 * 渲染层 file:// 源无法直连主站 API，统一经主进程代理（同时复用主站 token，token 不出主进程）。
 */
import { ipcMain } from 'electron'
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
    (_e, args: { templateSlug?: string; premise?: string; idempotency?: string } = {}) =>
      service().enqueueJob({
        templateSlug: String(args?.templateSlug || ''),
        premise: args?.premise,
        idempotency: args?.idempotency,
      }),
  )
  ipcMain.handle(IPC_CHANNELS.CLOUD_JOB_LIST, () => service().listJobs())
}
