/**
 * Y·NEX 桌面端 + 本地核心管理
 * 后台管理员查看所有桌面端客户端和 Y·NEX 本地核心的连接状态
 */
'use strict';

const express = require('express');
const router = express.Router();

// 内存中维护桌面端/YNEX连接状态（实际生产环境建议用Redis）
const desktopSessions = new Map(); // clientId -> { connectedAt, lastPing, version, platform, userId, username }
const ynexInstances = new Map();     // instanceId -> { connectedAt, lastPing, version, port, platform, userId, username }

// ============================================================
// 辅助：验证管理员
// ============================================================
function requireAdmin(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ error: '未登录' });
  }
  const token = auth.slice(7);
  try {
    const jwt = require('jsonwebtoken');
    // 安全：JWT_SECRET 必须由环境变量提供，与 billing.js 共用同一密钥。
    // 若未设置则拒绝验证（不回退到硬编码值，防止 token 伪造）。
    const secret = process.env.JWT_SECRET;
    if (!secret) {
      return res.status(500).json({ error: '服务器未配置 JWT_SECRET，无法验证身份' });
    }
    const decoded = jwt.verify(token, secret);
    if (decoded.role !== 'admin') {
      return res.status(403).json({ error: '需要管理员权限' });
    }
    req.admin = decoded;
    next();
  } catch (e) {
    return res.status(401).json({ error: 'token无效' });
  }
}

// ============================================================
// 桌面端管理
// ============================================================

// 注册/上报桌面端会话（桌面端启动时调用）
router.post('/desktop/register', (req, res) => {
  const { clientId, version, platform, userId, username } = req.body;
  if (!clientId) return res.status(400).json({ error: '缺少clientId' });
  desktopSessions.set(clientId, {
    connectedAt: desktopSessions.get(clientId)?.connectedAt || new Date().toISOString(),
    lastPing: new Date().toISOString(),
    version: version || 'unknown',
    platform: platform || 'unknown',
    userId: userId || null,
    username: username || null,
  });
  res.json({ ok: true, registered: true });
});

// 桌面端心跳（每30秒调用一次）
router.post('/desktop/ping', (req, res) => {
  const { clientId } = req.body;
  if (!clientId) return res.status(400).json({ error: '缺少clientId' });
  const session = desktopSessions.get(clientId);
  if (session) {
    session.lastPing = new Date().toISOString();
    res.json({ ok: true });
  } else {
    res.json({ ok: false, reason: '未注册' });
  }
});

// 桌面端登出（关闭时调用）
router.post('/desktop/unregister', (req, res) => {
  const { clientId } = req.body;
  if (clientId && desktopSessions.has(clientId)) {
    desktopSessions.delete(clientId);
  }
  res.json({ ok: true });
});

// 管理员：获取所有桌面端会话列表
router.get('/admin/desktop', requireAdmin, (req, res) => {
  const now = Date.now();
  const sessions = Array.from(desktopSessions.entries()).map(([id, s]) => {
    const lastPingTime = new Date(s.lastPing).getTime();
    const isOnline = (now - lastPingTime) < 120000; // 2分钟内有心跳视为在线
    return {
      id,
      ...s,
      isOnline,
      onlineDuration: s.connectedAt ? Math.round((now - new Date(s.connectedAt).getTime()) / 60000) + '分钟' : '未知',
    };
  });
  const onlineCount = sessions.filter(s => s.isOnline).length;
  res.json({
    ok: true,
    total: sessions.length,
    online: onlineCount,
    offline: sessions.length - onlineCount,
    sessions,
  });
});

// ============================================================
// Y·NEX 本地核心管理
// ============================================================

// Y·NEX 本地核心注册/上报
router.post('/ynex/register', (req, res) => {
  const { instanceId, version, port, platform, userId, username } = req.body;
  if (!instanceId) return res.status(400).json({ error: '缺少instanceId' });
  ynexInstances.set(instanceId, {
    connectedAt: ynexInstances.get(instanceId)?.connectedAt || new Date().toISOString(),
    lastPing: new Date().toISOString(),
    version: version || 'unknown',
    port: port || 7777,
    platform: platform || 'unknown',
    userId: userId || null,
    username: username || null,
  });
  res.json({ ok: true, registered: true });
});

// Y·NEX 心跳
router.post('/ynex/ping', (req, res) => {
  const { instanceId } = req.body;
  if (!instanceId) return res.status(400).json({ error: '缺少instanceId' });
  const instance = ynexInstances.get(instanceId);
  if (instance) {
    instance.lastPing = new Date().toISOString();
    res.json({ ok: true });
  } else {
    res.json({ ok: false, reason: '未注册' });
  }
});

// Y·NEX 登出
router.post('/ynex/unregister', (req, res) => {
  const { instanceId } = req.body;
  if (instanceId && ynexInstances.has(instanceId)) {
    ynexInstances.delete(instanceId);
  }
  res.json({ ok: true });
});

// 管理员：获取所有 Y·NEX 实例列表
router.get('/admin/ynex', requireAdmin, (req, res) => {
  const now = Date.now();
  const instances = Array.from(ynexInstances.entries()).map(([id, s]) => {
    const lastPingTime = new Date(s.lastPing).getTime();
    const isOnline = (now - lastPingTime) < 120000;
    return {
      id,
      ...s,
      isOnline,
      onlineDuration: s.connectedAt ? Math.round((now - new Date(s.connectedAt).getTime()) / 60000) + '分钟' : '未知',
    };
  });
  const onlineCount = instances.filter(s => s.isOnline).length;
  res.json({
    ok: true,
    total: instances.length,
    online: onlineCount,
    offline: instances.length - onlineCount,
    instances,
  });
});

// ============================================================
// 统计数据
// ============================================================

// 管理员：获取平台总览（桌面端 + Y·NEX）
router.get('/admin/overview', requireAdmin, (req, res) => {
  const now = Date.now();

  const desktopSessions_ = Array.from(desktopSessions.entries()).map(([id, s]) => {
    const lastPingTime = new Date(s.lastPing).getTime();
    const isOnline = (now - lastPingTime) < 120000;
    return { id, ...s, isOnline };
  });
  const ynexInstances_ = Array.from(ynexInstances.entries()).map(([id, s]) => {
    const lastPingTime = new Date(s.lastPing).getTime();
    const isOnline = (now - lastPingTime) < 120000;
    return { id, ...s, isOnline };
  });

  res.json({
    ok: true,
    desktop: {
      total: desktopSessions_.length,
      online: desktopSessions_.filter(s => s.isOnline).length,
      offline: desktopSessions_.filter(s => !s.isOnline).length,
    },
    ynex: {
      total: ynexInstances_.length,
      online: ynexInstances_.filter(s => s.isOnline).length,
      offline: ynexInstances_.filter(s => !s.isOnline).length,
    },
    timestamp: new Date().toISOString(),
  });
});

module.exports = (app) => {
  app.use('/api/admin-platform', router);
};
