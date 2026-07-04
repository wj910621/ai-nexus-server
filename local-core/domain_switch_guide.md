# Y·NEX 域名切换最终步骤文档

> 目标：将主站入口从 `j3trisheng.com` 迁移到 **`ynexai.cn`**，同时持有保护域名 `ynexai.com`、`y-nex.cn`、`y-nex.com`，全部统一重定向到主站。
> 服务器 IP：`120.79.17.184`
> 当前状态：Nginx 新域名配置已上传至 `/etc/nginx/sites-available/ynex.conf`（未启用），旧域名仍可正常访问。

---

## 一、域名注册

### 1.1 需要注册的域名

| 域名 | 用途 | 优先级 |
|---|---|---|
| **`ynexai.cn`** | 主域名，国内备案，用户主入口 | 必须 |
| `ynexai.com` | 品牌保护 + 海外访问 | 推荐 |
| `y-nex.cn` | 品牌保护，防止混淆 | 推荐 |
| `y-nex.com` | 品牌保护 | 可选 |

> 所有域名解析到同一服务器 IP：`120.79.17.184`。

### 1.2 推荐注册平台

| 平台 | 优势 | 适用域名 |
|---|---|---|
| **阿里云万网** | 国内备案方便、SSL 证书免费、DNS 解析稳定 | `ynexai.cn`、`ynexai.com`、`y-nex.cn`、`y-nex.com` |
| **Cloudflare** | 免费 CDN/SSL/DNS、海外访问快 | 海外版 `ynexai.com` 可切过去 |
| **Namesilo** | 隐私保护免费、续费无套路 | 备用注册 `.com` |

---

## 二、DNS 解析

在域名注册商控制台，为每个域名添加以下记录：

| 主机记录 | 记录类型 | 记录值 | 说明 |
|---|---|---|---|
| `@` | A | `120.79.17.184` | 主域名 |
| `www` | A | `120.79.17.184` | www 子域 |

> 解析生效时间：通常 5 分钟 ~ 48 小时，可用 `ping ynexai.cn` 或 `nslookup ynexai.cn` 检查。

---

## 三、SSL 证书申请

### 方案 A：阿里云免费 DV 证书（推荐 `ynexai.cn`）

1. 登录 [阿里云 SSL 证书控制台](https://www.aliyun.com/product/certify)。
2. 购买/申请「免费 DV 证书」。
3. 按提示添加 DNS 验证记录（TXT 记录）。
4. 审核通过后下载 **Nginx 格式** 证书压缩包。
5. 解压后重命名为：
   - `/etc/nginx/ssl/ynexai.cn.pem`（证书）
   - `/etc/nginx/ssl/ynexai.cn.key`（私钥）

### 方案 B：Let's Encrypt（适合 `.com` 等保护域名）

在服务器上执行：

```bash
# 安装 certbot
apt update
apt install -y certbot python3-certbot-nginx

# 为主域名 + 保护域名申请一张多域名证书
certbot --nginx -d ynexai.cn -d www.ynexai.cn -d ynexai.com -d www.ynexai.com -d y-nex.cn -d www.y-nex.cn -d y-nex.com -d www.y-nex.com
```

> 注意：Let's Encrypt 生成的证书路径可能为 `/etc/letsencrypt/live/ynexai.cn/...`，需要在 Nginx 配置中相应修改。

### 方案 C：保护域名暂时复用主域名证书

如果暂时不想为每个保护域名单独申请证书，可以先让保护域名的 HTTPS 也使用 `ynexai.cn` 的证书。浏览器会提示「证书与域名不匹配」，但 301 重定向仍能生效。用户点击「继续前往」后会跳到 `https://ynexai.cn`。

---

## 四、上传证书到服务器

### 4.1 确保证书目录存在

服务器上已存在：`/etc/nginx/ssl/`

### 4.2 上传主域名证书

将证书文件上传到：

- `/etc/nginx/ssl/ynexai.cn.pem`
- `/etc/nginx/ssl/ynexai.cn.key`

上传方式：

- **SCP**：`scp ynexai.cn.pem ynexai.cn.key root@120.79.17.184:/etc/nginx/ssl/`
- **SFTP 工具**：Termius、WinSCP、FileZilla 等

---

## 五、启用 Nginx 新域名配置

### 5.1 将配置从 `sites-available` 软链到 `sites-enabled`

```bash
ln -sf /etc/nginx/sites-available/ynex.conf /etc/nginx/sites-enabled/ynex.conf
```

### 5.2 检查 Nginx 配置并重新加载

```bash
nginx -t
systemctl reload nginx
```

> 如果 `nginx -t` 报错，请检查证书路径是否正确、域名是否已解析。

### 5.3 验证新域名访问

```bash
curl -I http://ynexai.cn
# 应返回 301 -> https://ynexai.cn/

curl -I https://ynexai.cn
# 应返回 200 OK

curl -I https://ynexai.com
# 应返回 301 -> https://ynexai.cn/

curl -I https://y-nex.cn
# 应返回 301 -> https://ynexai.cn/
```

---

## 六、启用旧域名 301 重定向

当 `ynexai.cn` 稳定运行、备案通过且 SSL 正常后，执行以下操作：

### 6.1 编辑 Nginx 配置文件

```bash
vim /etc/nginx/sites-available/ynex.conf
```

### 6.2 取消注释「阶段二」配置

找到以下内容并删除每行前面的 `#`：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name j3trisheng.com www.j3trisheng.com;
    return 301 https://ynexai.cn$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name j3trisheng.com www.j3trisheng.com;
    ssl_certificate /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin.key;
    return 301 https://ynexai.cn$request_uri;
}
```

> 其中 `origin.pem` / `origin.key` 是 `j3trisheng.com` 当前正在使用的证书，通常位于 `/etc/nginx/ssl/` 下。如文件名不同请修改。

### 6.3 测试并重载

```bash
nginx -t
systemctl reload nginx
```

### 6.4 验证 301 重定向

```bash
curl -I http://j3trisheng.com
# 应返回 301 Moved Permanently -> https://ynexai.cn/

curl -I https://j3trisheng.com
# 应返回 301 Moved Permanently -> https://ynexai.cn/
```

---

## 七、替换站内 `j3trisheng.com` 链接

当前 `landing.html` 中还有 4 处 `j3trisheng.com` 引用：

| 位置 | 用途 | 切换时机 |
|---|---|---|
| API 示例 `curl https://j3trisheng.com/v1/chat/completions` | 文档示例 | 新域名上线后 |
| `base_url="https://j3trisheng.com/v1"` | SDK 示例 | 新域名上线后 |
| `file:` 协议 fallback URL | 本地打开页面时的兜底地址 | 新域名上线后 |
| 推荐链接 `https://j3trisheng.com` | 分销邀请链接 | 新域名上线后 |

### 7.1 执行替换脚本

在本地项目目录运行：

```bash
node -e "
const fs=require('fs');
const path='C:\\\\Users\\\\13111\\\\ai-nexus-server\\\\landing.html';
let c=fs.readFileSync(path,'utf8');
c=c.replace(/https:\\/\\/j3trisheng\\.com/g,'https://ynexai.cn');
fs.writeFileSync(path,c);
console.log('✅ landing.html 域名链接已替换');
"
```

### 7.2 同步到服务器

```bash
scp C:\Users\13111\ai-nexus-server\landing.html root@120.79.17.184:/home/admin/ai-nexus/landing.html
```

---

## 八、最终验证清单

- [ ] `ynexai.cn` / `www.ynexai.cn` 可正常访问并显示 Y·NEX 首页
- [ ] `ynexai.com`、`y-nex.cn`、`y-nex.com` 均 301 重定向到 `https://ynexai.cn/`
- [ ] 浏览器地址栏显示 HTTPS 锁标志（主域名无警告）
- [ ] 首页 Logo 旁显示 `Y·NEX` 和 `亿界互联 · 无界未来`
- [ ] 下载页 `/download/` 可正常下载 `YNEX-Desktop-Setup-2.0.0.exe`
- [ ] 登录/注册/API 调用功能正常
- [ ] `j3trisheng.com` 已 301 重定向到 `ynexai.cn`
- [ ] 站内所有 `j3trisheng.com` 链接已替换为 `ynexai.cn`

---

## 九、常见问题

### Q1：域名备案需要多久？
A：国内 `.cn` 域名首次备案约 7 ~ 20 个工作日。备案期间建议不要直接解析到国内服务器，否则可能被阻断。

### Q2：保护域名使用主域名证书会报警告怎么办？
A：这是正常现象。建议为每个保护域名单独申请免费证书，或购买/申请一张包含所有域名的多域名/泛域名证书。

### Q3：旧域名的 SSL 证书到期后怎么办？
A：开启 301 重定向后，旧域名仍需证书才能正常完成 HTTPS 握手。建议在旧证书到期前用 Let's Encrypt 续期，或购买多年期证书。

### Q4：是否需要更新桌面端安装包里的域名？
A：桌面端通过本地核心通信，不直接依赖主站域名。但如果桌面端内有「打开官网」按钮或更新检查 URL，请同步替换为 `https://ynexai.cn`。

---

## 十、后续优化建议

1. **SEO**：在百度站长平台、Google Search Console 提交新域名 sitemap，并设置 301 重定向以转移权重。
2. **邮件/短信**：将系统内所有邮件模板、短信签名中的 `j3trisheng.com` 替换为 `ynexai.cn`。
3. **社交媒体**：更新微信公众号、GitHub、产品文档中的品牌链接。
4. **监控**：为 `ynexai.cn` 配置 uptime 监控和 HTTPS 证书到期提醒。
5. **品牌保护**：定期检查 `ynexai.cn`、`ynexai.com`、`y-nex.cn`、`y-nex.com` 的到期时间，及时续费。
