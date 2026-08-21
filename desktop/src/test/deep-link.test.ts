import { describe, it, expect } from 'vitest'
import { parseDeepLink, deepLinkToRouterPath, DEEP_LINK_PROTOCOL } from '@main/deep-link'

describe('parseDeepLink', () => {
  it('parses home URL', () => {
    const result = parseDeepLink(`${DEEP_LINK_PROTOCOL}://`)
    expect(result.action).toBe('home')
    expect(result.params).toEqual({})
  })

  it('parses single segment action', () => {
    const result = parseDeepLink(`${DEEP_LINK_PROTOCOL}://settings`)
    expect(result.action).toBe('settings')
    expect(result.params).toEqual({})
  })

  it('parses action with id', () => {
    const result = parseDeepLink(`${DEEP_LINK_PROTOCOL}://projects/abc`)
    expect(result.action).toBe('projects')
    expect(result.params).toEqual({ id: 'abc' })
  })

  it('parses action with sub and id', () => {
    const result = parseDeepLink(`${DEEP_LINK_PROTOCOL}://workflow/run/xyz`)
    expect(result.action).toBe('workflow')
    expect(result.params).toEqual({ sub: 'run', id: 'xyz' })
  })

  it('strips query string', () => {
    const result = parseDeepLink(`${DEEP_LINK_PROTOCOL}://projects/abc?tab=edit`)
    expect(result.action).toBe('projects')
    expect(result.params).toEqual({ id: 'abc' })
  })

  it('throws on invalid protocol', () => {
    expect(() => parseDeepLink('http://example.com')).toThrow(/Invalid deep link protocol/)
  })

  it('handles trailing slash', () => {
    const result = parseDeepLink(`${DEEP_LINK_PROTOCOL}://projects/`)
    expect(result.action).toBe('projects')
    expect(result.params).toEqual({})
  })
})

describe('deepLinkToRouterPath', () => {
  it('home -> /dashboard', () => {
    expect(deepLinkToRouterPath({ action: 'home', params: {} })).toBe('/dashboard')
  })

  it('settings -> /settings', () => {
    expect(deepLinkToRouterPath({ action: 'settings', params: {} })).toBe('/settings')
  })

  it('projects without id -> /projects', () => {
    expect(deepLinkToRouterPath({ action: 'projects', params: {} })).toBe('/projects')
  })

  it('projects with id -> /projects/:id', () => {
    expect(deepLinkToRouterPath({ action: 'projects', params: { id: 'abc' } })).toBe('/projects/abc')
  })

  it('workflow/run/:id -> /projects/:id', () => {
    expect(deepLinkToRouterPath({ action: 'workflow', params: { sub: 'run', id: 'xyz' } })).toBe('/projects/xyz')
  })

  it('unknown action -> /dashboard', () => {
    expect(deepLinkToRouterPath({ action: 'unknown', params: {} })).toBe('/dashboard')
  })

  it('characters -> /characters', () => {
    expect(deepLinkToRouterPath({ action: 'characters', params: {} })).toBe('/characters')
  })
})
