import { describe, it, expect } from 'vitest'
import { buildMenuTemplate } from '@main/menu'

describe('buildMenuTemplate', () => {
  it('returns an array of menu items', () => {
    const template = buildMenuTemplate()
    expect(Array.isArray(template)).toBe(true)
    expect(template.length).toBeGreaterThan(0)
  })

  it('includes File menu (文件) with New and Settings', () => {
    const template = buildMenuTemplate()
    const fileMenu = template.find((m) => m.label === '文件')
    expect(fileMenu).toBeDefined()
    const labels = (fileMenu!.submenu as any[]).map((item) => item.label)
    expect(labels).toContain('新建项目')
    expect(labels).toContain('设置')
  })

  it('includes Edit menu (编辑) with undo/redo/copy/paste', () => {
    const template = buildMenuTemplate()
    const editMenu = template.find((m) => m.label === '编辑')
    expect(editMenu).toBeDefined()
    const roles = (editMenu!.submenu as any[]).map((item) => item.role)
    expect(roles).toContain('undo')
    expect(roles).toContain('redo')
    expect(roles).toContain('copy')
    expect(roles).toContain('paste')
  })

  it('includes View menu (视图) with reload and devtools', () => {
    const template = buildMenuTemplate()
    const viewMenu = template.find((m) => m.label === '视图')
    expect(viewMenu).toBeDefined()
    const roles = (viewMenu!.submenu as any[]).map((item) => item.role)
    expect(roles).toContain('reload')
    expect(roles).toContain('toggleDevTools')
    expect(roles).toContain('togglefullscreen')
  })

  it('includes Help menu (帮助) with About', () => {
    const template = buildMenuTemplate()
    const helpMenu = template.find((m) => m.label === '帮助')
    expect(helpMenu).toBeDefined()
    const labels = (helpMenu!.submenu as any[]).map((item) => item.label)
    expect(labels).toContain('关于')
    expect(labels).toContain('官方文档')
    expect(labels).toContain('问题反馈')
  })

  it('invokes onAbout callback when About clicked', () => {
    let called = false
    const template = buildMenuTemplate({ onAbout: () => { called = true } })
    const helpMenu = template.find((m) => m.label === '帮助')!
    const aboutItem = (helpMenu.submenu as any[]).find((item) => item.label === '关于')
    aboutItem.click!()
    expect(called).toBe(true)
  })

  it('invokes onSettings callback when Settings clicked', () => {
    let called = false
    const template = buildMenuTemplate({ onSettings: () => { called = true } })
    const fileMenu = template.find((m) => m.label === '文件')!
    const settingsItem = (fileMenu.submenu as any[]).find((item) => item.label === '设置')
    settingsItem.click!()
    expect(called).toBe(true)
  })

  it('invokes onNewWindow callback when New Project clicked', () => {
    let called = false
    const template = buildMenuTemplate({ onNewWindow: () => { called = true } })
    const fileMenu = template.find((m) => m.label === '文件')!
    const newItem = (fileMenu.submenu as any[]).find((item) => item.label === '新建项目')
    newItem.click!()
    expect(called).toBe(true)
  })

  it('accelerator for New Project is CmdOrCtrl+N', () => {
    const template = buildMenuTemplate()
    const fileMenu = template.find((m) => m.label === '文件')!
    const newItem = (fileMenu.submenu as any[]).find((item) => item.label === '新建项目')
    expect(newItem.accelerator).toBe('CmdOrCtrl+N')
  })

  it('accelerator for Settings is CmdOrCtrl+,', () => {
    const template = buildMenuTemplate()
    const fileMenu = template.find((m) => m.label === '文件')!
    const settingsItem = (fileMenu.submenu as any[]).find((item) => item.label === '设置')
    expect(settingsItem.accelerator).toBe('CmdOrCtrl+,')
  })
})
