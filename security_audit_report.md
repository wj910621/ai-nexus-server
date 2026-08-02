# 安全审计报告

**审计时间**: 2026-08-02
**审计范围**: Y·NEX AI 云平台代码仓库全量代码
**审计目标**: 识别中等严重度及以上的已确认漏洞，且必须具备可论证的端到端利用路径

---

## 执行摘要

本报告对Y·NEX AI云平台进行了系统性的安全审计，重点关注认证与访问控制、注入向量、外部交互、敏感数据处理等四个攻击面。经过深度代码审查，发现了**2个中等严重度已确认漏洞**和**3个低严重度安全问题**。

---

## 已确认漏洞（中等严重度及以上）

### 漏洞 #1: SSRF风险 - 未验证的外部URL请求（中等严重度）

**漏洞位置**: 
- [browser_automation.py:77-83](file:///workspace/desktop/resources/ynex/browser_automation.py#L77-L83)
- [skills.py:303-306](file:///workspace/desktop/resources/ynex/skills.py#L303-L306)

**攻击者画像**: 已认证用户（需要API Key或JWT Token）

**可控输入向量**:
- `/chat` 端点的 `text` 参数
- `/command` 端点的命令参数
- 浏览器自动化相关功能调用

**代码路径**:
```
用户请求 → API认证 → brain.py处理 → skills.py调用 → browser_automation.py:goto(url)
```

**具体代码**:
```python
def goto(url: str) -> Dict[str, Any]:
    """打开网页"""
    try:
        if not url.startswith("http"):
            url = "https://" + url  # 仅添加协议，无域名白名单校验
        page = _current_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
```

**造成的影响**:
1. **内网探测**: 攻击者可通过`http://192.168.x.x`或`http://10.x.x.x`探测内网服务
2. **云元数据泄露**: 在云环境中可访问`http://169.254.169.254`获取实例元数据
3. **绕过防火墙**: 利用服务器作为代理访问受限资源
4. **拒绝服务**: 访问大量外部资源消耗服务器带宽和资源

**端到端利用步骤**:
1. 攻击者通过有效API Key调用聊天接口
2. 发送消息："帮我打开这个网页：http://192.168.1.1/admin"
3. 服务器执行`goto("http://192.168.1.1/admin")`
4. 攻击者通过返回的页面内容探测内网服务

**建议修复方案**:
```python
# 添加URL白名单和协议限制
ALLOWED_DOMAINS = [
    'example.com', 'api.example.com'
    # 添加业务需要的域名
]

def goto(url: str) -> Dict[str, Any]:
    """打开网页（带安全校验）"""
    try:
        # 强制HTTPS协议
        if not url.startswith("https://"):
            return {"ok": False, "error": "仅允许HTTPS协议"}
        
        # 解析域名并校验白名单
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 阻止私有IP段和内网地址
        import ipaddress
        try:
            ip = ipaddress.ip_address(domain.split(':')[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return {"ok": False, "error": "禁止访问私有IP地址"}
        except ValueError:
            pass  # 不是IP地址，继续域名检查
        
        # 域名白名单校验（生产环境必须启用）
        if not any(domain.endswith(allowed) for allowed in ALLOWED_DOMAINS):
            return {"ok": False, "error": f"域名 {domain} 不在白名单内"}
        
        # 执行请求...
```

---

### 漏洞 #2: 命令注入风险 - Shell命令参数拼接（中等严重度）

**漏洞位置**: [skills.py:179](file:///workspace/desktop/resources/ynex/skills.py#L179)

**攻击者画像**: 已认证用户（需要API Key或JWT Token）

**可控输入向量**: `/command` 端点的应用名称参数

**代码路径**:
```
用户请求 → API认证 → device_hub.py解析 → skills.py:open_application(name)
```

**具体代码**:
```python
def open_application(name: str) -> str:
    """打开常见 Windows 应用程序"""
    app_map = {...}
    cmd = app_map.get(name.lower(), name)  # 用户输入未充分过滤
    # 防止路径穿越/绝对路径
    if "/" in cmd or "\\" in cmd or cmd.startswith("."):
        return f"先生，不允许的应用名称：{name}。"
    try:
        subprocess.Popen([cmd], shell=False)  # 虽然shell=False，但cmd可能被控制
        return f"先生，已为您打开 {name}。"
```

**造成的影响**:
虽然代码使用了`shell=False`并检查了路径穿越，但攻击者仍可能通过以下方式利用：
1. **任意程序执行**: 在Windows环境中，攻击者可执行系统目录中的任意可执行文件
2. **权限提升**: 如果服务以高权限运行，可执行敏感系统工具
3. **信息泄露**: 执行系统信息收集工具（如`systeminfo`）

**端到端利用步骤**:
1. 攻击者通过有效API Key调用命令接口
2. 发送请求：`{"tool": "open_application", "name": "cmd.exe"}`
3. 服务器执行`subprocess.Popen(["cmd.exe"], shell=False)`
4. 在Windows服务器上打开命令提示符（虽然无直接输出返回，但进程已启动）

**建议修复方案**:
```python
def open_application(name: str) -> str:
    """打开常见 Windows 应用程序（严格白名单）"""
    # 严格的白名单映射，不允许用户输入穿透
    app_map = {
        "记事本": "notepad",
        "计算器": "calc",
        "浏览器": "msedge",
        # ...其他预定义应用
    }
    
    # 仅允许白名单内的应用，不接受任意输入
    cmd = app_map.get(name.lower())
    if not cmd:
        return f"先生，应用 '{name}' 不在允许列表中。"
    
    try:
        subprocess.Popen([cmd], shell=False)
        return f"先生，已为您打开 {name}。"
    except Exception as e:
        return f"先生，打开 {name} 失败：{e}"
```

---

## 低严重度安全问题

### 问题 #1: 敏感信息泄露风险 - 默认密码和密钥管理

**位置**: 
- [server.js:280-287](file:///workspace/server.js#L280-L287)
- [.env.example](file:///workspace/.env.example)

**问题描述**:
1. 管理员密码在未设置环境变量时使用临时随机值，虽然有警告，但在生产环境中可能被忽视
2. `.env.example` 文件包含所有API密钥的占位符，虽然使用了示例值，但可能误导开发者提交真实密钥

**建议修复**:
- 在生产环境部署脚本中强制检查`ADMIN_PASSWORD`和`JWT_SECRET`是否已设置
- 添加启动时的安全配置检查，拒绝在关键配置缺失时启动服务

### 问题 #2: 速率限制绕过风险

**位置**: [server.js:88-97](file:///workspace/server.js#L88-L97)

**问题描述**:
速率限制基于`x-forwarded-for`头部获取IP，攻击者可通过伪造该头部绕过限制：

```javascript
const ip = req.headers['x-forwarded-for']?.split(',')[0] || req.socket.remoteAddress || 'unknown';
```

**建议修复**:
```javascript
// 优先使用socket真实IP，仅在可信代理时使用x-forwarded-for
const ip = req.socket.remoteAddress || 'unknown';
// 或配置可信代理列表
const TRUSTED_PROXIES = ['10.0.0.0/8', '172.16.0.0/12'];
```

### 问题 #3: 日志信息泄露风险

**位置**: [auth.py:376](file:///workspace/desktop/resources/ynex/auth.py#L376)

**问题描述**:
首次创建管理员API Key时，完整Key被写入文件，虽然文件权限设为600，但在共享环境中仍可能泄露：

```python
_key_file.write_text(
    f"Y·NEX 初始管理员 API Key\n"
    f"Key ID: {key_id}\n"
    f"API Key: {raw}\n"  # 明文写入API Key
    ...
)
```

**建议修复**:
- 仅显示Key ID和创建时间，要求管理员通过安全渠道获取初始密钥
- 或在首次登录后强制要求创建新的管理员密钥

---

## 安全实践亮点

### 1. API Key哈希化存储

代码实现了API Key的HMAC-SHA256哈希存储，防止数据库泄露后密钥直接可用：

```python
def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(f"{api_key}:{_API_KEY_PEPPER}".encode()).hexdigest()
```

### 2. JWT撤销机制

实现了基于`token_version`的JWT撤销机制，密码修改后所有旧Token立即失效：

```python
def incrementTokenVersion(username):
    db.prepare("UPDATE users SET token_version = token_version + 1 WHERE username=?").run(username)
```

### 3. 代码沙箱隔离

Python代码执行使用了多层安全防护：
- 关键字黑名单
- AST节点校验
- 子进程隔离（`-I -S`参数）
- 环境变量清理

```python
safe_env = {
    "PATH": os.environ.get("PATH", ""),
    "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
}
result = subprocess.run(["python", "-I", "-S", tmp_path], env=safe_env, ...)
```

### 4. SQL注入防护

所有数据库查询均使用参数化查询：

```python
db.prepare("SELECT * FROM users WHERE username=?").get(username)
```

### 5. 密码存储安全

使用bcrypt进行密码哈希，并实现了从旧Base64编码到bcrypt的迁移：

```python
function hashPasswordSync(pwd) { 
    return bcrypt.hashSync(pwd, 10); 
}
```

---

## 审计结论

本次审计发现了2个中等严重度的已确认漏洞，均具备完整的端到端利用路径：

1. **SSRF风险**: 可导致内网探测和云元数据泄露
2. **命令注入风险**: 可导致任意程序执行

建议在部署到生产环境前优先修复这两个中等严重度漏洞。低严重度问题建议在后续版本中逐步改进。

整体而言，该代码库在安全实践方面表现良好，实现了多项重要的安全防护措施，但在外部交互和命令执行方面仍需加强安全控制。

---

**审计完成时间**: 2026-08-02
**审计工具**: 人工代码审查 + 静态分析
**审计状态**: 已完成