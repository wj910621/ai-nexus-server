/**
 * R4b-1 本机 ComfyUI 渲染 IPC handlers
 * 渲染产物统一落到 userData/renders/，返回 filePath + dataUrl（供渲染层直接预览）。
 */
import { ipcMain, app } from 'electron'
import path from 'path'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { createComfyService, type ComfyRenderInput, type ComfyService } from '../services/comfy-service'

let svc: ComfyService | null = null

function service(): ComfyService {
  if (!svc) svc = createComfyService(path.join(app.getPath('userData'), 'renders'))
  return svc
}

export function registerRenderHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.RENDER_COMFY_PROBE, () => service().probe())
  ipcMain.handle(IPC_CHANNELS.RENDER_COMFY_RUN, (_e, args: ComfyRenderInput) =>
    service().render(args || { prompt: '' }),
  )
}
