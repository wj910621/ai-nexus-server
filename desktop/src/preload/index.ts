import { contextBridge } from 'electron'
import { api } from './api'

// Expose a controlled API surface to the renderer.
// contextIsolation=true means the renderer cannot directly access Node.js APIs.
contextBridge.exposeInMainWorld('electronAPI', api)
