const fs = require('fs');
const path = require('path');

module.exports = function(app, { staticDir }) {
  // Meshy 3D
  app.post('/api/meshy/txt2d', async (req, res) => {
    try {
      const apiKey = process.env.MESHY_API_KEY;
      if (!apiKey) return res.json({ ok: false, error: 'Meshy API Key 未配置' });
      const { prompt, style = 'realistic' } = req.body;
      if (!prompt) return res.json({ ok: false, error: '请输入3D模型描述' });
      const r = await fetch('https://api.meshy.ai/openapi/v2/text-to-3d', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey },
        body: JSON.stringify({ mode: 'preview', prompt, style_prompt: style, enable_pbr: true }),
      });
      const data = await r.json();
      res.json(data);
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/meshy/result/:taskId', async (req, res) => {
    try {
      const apiKey = process.env.MESHY_API_KEY;
      if (!apiKey) return res.json({ ok: false });
      let r = await fetch('https://api.meshy.ai/openapi/v2/text-to-3d/' + req.params.taskId, {
        headers: { 'Authorization': 'Bearer ' + apiKey },
      });
      let data = await r.json();
      if (data.error) {
        r = await fetch('https://api.meshy.ai/openapi/v2/image-to-3d/' + req.params.taskId, {
          headers: { 'Authorization': 'Bearer ' + apiKey },
        });
        data = await r.json();
      }
      res.json(data);
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  app.post('/api/meshy/img2d', async (req, res) => {
    try {
      const apiKey = process.env.MESHY_API_KEY;
      if (!apiKey) return res.json({ ok: false, error: 'Meshy API Key 未配置' });
      const { image_data, prompt = '' } = req.body;
      if (!image_data) return res.json({ ok: false, error: '请提供图片数据' });
      const base64Data = image_data.replace(/^data:image\/\w+;base64,/, '');
      const buffer = Buffer.from(base64Data, 'base64');
      const imgDir = path.join(staticDir, 'uploads');
      fs.mkdirSync(imgDir, { recursive: true });
      const fileName = 'meshy_' + Date.now() + '.png';
      const filePath = path.join(imgDir, fileName);
      fs.writeFileSync(filePath, buffer);
      const imgUrl = (process.env.BASE_URL || 'http://localhost:3001') + '/uploads/' + fileName;
      const r = await fetch('https://api.meshy.ai/openapi/v2/image-to-3d', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + apiKey },
        body: JSON.stringify({ image_url: imgUrl, enable_pbr: true, prompt: prompt || undefined }),
      });
      const data = await r.json();
      res.json(data);
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  // Agnes AI Video
  app.post('/api/agnes-video', async (req, res) => {
    try {
      const apiKey = process.env.AGNES_API_KEY;
      if (!apiKey) return res.json({ ok: false, error: 'Agnes API Key 未配置' });
      const { prompt, width, height, num_frames, frame_rate, negative_prompt, seed, image, mode } = req.body;
      if (!prompt) return res.json({ ok: false, error: '缺少视频描述' });
      const body = {
        model: 'agnes-video-v2.0', prompt,
        width: width || 1152, height: height || 768,
        num_frames: num_frames || 121, frame_rate: frame_rate || 24,
      };
      if (negative_prompt) body.negative_prompt = negative_prompt;
      if (seed != null) body.seed = seed;
      if (image) body.image = image;
      if (mode) body.mode = mode;
      const r = await fetch('https://apihub.agnes-ai.com/v1/videos', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + apiKey, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      res.json({ ok: true, ...data });
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  app.get('/api/agnes-video/:taskId', async (req, res) => {
    try {
      const apiKey = process.env.AGNES_API_KEY;
      if (!apiKey) return res.json({ ok: false, error: 'Agnes API Key 未配置' });
      const r = await fetch('https://apihub.agnes-ai.com/v1/videos/' + req.params.taskId, {
        headers: { 'Authorization': 'Bearer ' + apiKey },
      });
      const data = await r.json();
      res.json({ ok: true, ...data });
    } catch (e) { res.json({ ok: false, error: e.message }); }
  });

  // Suno Music
  const SUNO_BASE = process.env.SUNO_API_BASE || 'https://open.suno.cn/api/v1';
  const SUNO_KEY = process.env.SUNO_API_KEY || '';

  app.post('/api/music/generate', async (req, res) => {
    const { prompt, title, instrumental, model } = req.body;
    if (!SUNO_KEY) return res.json({ ok: false, error: 'Suno API Key 未配置' });
    try {
      const body = {
        gpt_description_prompt: prompt,
        make_instrumental: !!instrumental,
        mv: model || 'chirp-crow',
        title: title || '未命名歌曲'
      };
      const r = await fetch(`${SUNO_BASE}/music/generate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${SUNO_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await r.json();
      res.json(data);
    } catch(e) { res.status(500).json({ ok: false, error: 'Suno API 调用失败: ' + e.message }); }
  });

  app.get('/api/music/task', async (req, res) => {
    const { id } = req.query;
    if (!id) return res.json({ ok: false, error: '缺少 task_id' });
    try {
      const r = await fetch(`${SUNO_BASE}/music/task?id=${id}`, {
        headers: { 'Authorization': `Bearer ${SUNO_KEY}` }
      });
      const data = await r.json();
      res.json(data);
    } catch(e) { res.status(500).json({ ok: false, error: '查询失败: ' + e.message }); }
  });

  // Kling
  const KLING_AK = process.env.KLING_AK || '';
  const KLING_SK = process.env.KLING_SK || '';
  const KLING_BASE = 'https://api.klingai.com';

  function generateKlingToken() {
    const now = Math.floor(Date.now() / 1000);
    return require('jsonwebtoken').sign(
      { iss: KLING_AK, exp: now + 1800, nbf: now - 5 },
      KLING_SK,
      { algorithm: 'HS256', header: { alg: 'HS256', typ: 'JWT' } }
    );
  }

  app.post('/api/kling/text2video', async (req, res) => {
    try {
      const { prompt, model = 'kling-v1.6', duration = 5, mode = 'pro' } = req.body;
      if (!prompt) return res.status(400).json({ error: '请输入提示词' });
      const token = generateKlingToken();
      const r = await fetch(`${KLING_BASE}/v1/videos/text2video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ model_name: model, prompt, duration, mode, image_tailor: 'none' })
      });
      res.json(await r.json());
    } catch(e) { res.status(500).json({ error: '视频生成失败: ' + e.message }); }
  });

  app.post('/api/kling/image2video', async (req, res) => {
    try {
      const { image, prompt, model = 'kling-v1.6', duration = 5 } = req.body;
      if (!image) return res.status(400).json({ error: '请上传图片' });
      const token = generateKlingToken();
      const r = await fetch(`${KLING_BASE}/v1/videos/image2video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ model_name: model, image, prompt: prompt || '', duration, mode: 'pro' })
      });
      res.json(await r.json());
    } catch(e) { res.status(500).json({ error: '图生视频失败: ' + e.message }); }
  });

  app.get('/api/kling/task', async (req, res) => {
    try {
      const { id } = req.query;
      if (!id) return res.status(400).json({ error: '缺少任务ID' });
      const token = generateKlingToken();
      const r = await fetch(`${KLING_BASE}/v1/videos/${id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      res.json(await r.json());
    } catch(e) { res.status(500).json({ error: '查询任务失败: ' + e.message }); }
  });
};
