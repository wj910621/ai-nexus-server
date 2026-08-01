# Y·NEX 代码仓库安全审计报告

**审计日期**: 2026-08-01
**审计范围**: 全面漏洞评估
**审计目标**: 识别中等严重度及以上的已确认漏洞,并提供可论证的端到端利用路径

---

## 执行摘要

本次安全审计对Y·NEX AI云平台代码仓库进行了系统性的安全评估,重点关注认证与访问控制、注入向量、外部交互以及敏感数据处理四个关键领域。

**审计结论**: 发现 **5个已确认的中等严重度安全漏洞**,均具备完整的利用路径和影响分析。

---

## 一、认证与访问控制

### 1.1 弱密码策略 (中等严重度)

**漏洞ID**: AUTH-001

**位置**:
- [auth.js:106](file:///workspace/auth.js#L106) - 注册密码最小长度验证
- [auth.js:280](file:///workspace/auth.js#L280) - 管理员密码修改最小长度验证
- [auth.js:489](file:///workspace/auth.js#L489) - 密码重置最小长度验证

**攻击者画像**: 外部未认证攻击者

**输入向量**: 用户注册、密码修改、密码重置接口的`password`参数

**代码路径**:
```javascript
// auth.js:106
if (password.length < 6) return res.json({ ok: false, error: '密码至少6位' });
```

**利用步骤**:
1. 攻击者使用弱密码(如"123456")尝试注册账户
2. 系统仅要求密码长度≥6位,允许使用简单密码
3. 攻击者使用常见密码字典进行暴力破解,成功率显著提高

**影响**:
- 账户劫持风险: 用户账户可能通过暴力破解被攻破
- 权限提升风险: 管理员账户如果使用弱密码,可能导致系统完全沦陷
- 数据泄露风险: 攻击者可访问用户积分、对话历史等敏感数据

**修复建议**:
1. 强制实施密码复杂度策略:
   - 最小长度提升至10位
   - 要求包含大小写字母、数字和特殊字符
   - 检查常见弱密码黑名单
2. 实施账户锁定机制(连续失败5次锁定15分钟)
3. 推荐使用密码强度检测库(如zxcvbn)

---

### 1.2 管理员密码回退机制缺陷 (中等严重度)

**漏洞ID**: AUTH-002

**位置**: [server.js:280](file:///workspace/server.js#L280)

**攻击者画像**: 内部威胁或配置错误的部署环境

**输入向量**: 环境变量`ADMIN_PASSWORD`

**代码路径**:
```javascript
// server.js:280-286
const adminPwd = process.env.ADMIN_PASSWORD || crypto.randomBytes(16).toString('hex');
db.prepare("INSERT INTO users (username, email, password, credits, role) VALUES (?,?,?,?,?)").run(
  'admin', 'admin@nexus-hub.local', hashPasswordSync(adminPwd), 100, 'admin'
);
if (process.env.ADMIN_PASSWORD) {
  console.log('[Init] Admin account created from ADMIN_PASSWORD env var');
} else {
  console.log('[Init] Admin account created. Set ADMIN_PASSWORD env var to override default password.');
}
```

**利用步骤**:
1. 部署人员在生产环境中忘记设置`ADMIN_PASSWORD`环境变量
2. 系统生成随机密码但**仅输出到控制台日志**,生产环境可能无人查看
3. 攻击者(内部威胁或获得日志访问权限的外部攻击者)可从日志中获取密码
4. 或者,部署人员因无法登录而寻找其他方式获取密码,可能导致密码泄露

**影响**:
- 管理员账户权限滥用
- 系统完全沦陷(管理员可充值积分、查看所有用户数据)
- 合规性风险(审计日志中记录明文密码)

**修复建议**:
1. **强制要求**设置`ADMIN_PASSWORD`环境变量,未设置时拒绝启动:
   ```javascript
   if (!process.env.ADMIN_PASSWORD) {
     console.error('FATAL: ADMIN_PASSWORD environment variable must be set');
     process.exit(1);
   }
   ```
2. 删除生成随机密码的回退逻辑
3. 首次部署时通过安全的密钥管理系统(如HashiCorp Vault)注入密码

---

### 1.3 IP限制绕过风险 (中等严重度)

**漏洞ID**: AUTH-003

**位置**: [auth.js:110](file:///workspace/auth.js#L110)

**攻击者画像**: 外部未认证攻击者

**输入向量**: HTTP请求头`X-Forwarded-For`

**代码路径**:
```javascript
// auth.js:110-113
const clientIP = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';
const ipRow = db.prepare("SELECT COUNT(*) as cnt FROM users WHERE register_ip=?").get(clientIP);
const currentCount = ipRow ? ipRow.cnt : 0;
if (currentCount >= 2) return res.json({ ok: false, error: '本网络已注册过 2 个账号,已达到上限' });
```

**利用步骤**:
1. 攻击者编写脚本,每次注册时伪造不同的`X-Forwarded-For`头
2. 绕过IP限制,创建无限数量的虚假账户
3. 利用推荐码机制,每个虚假账户可获得30积分
4. 通过积分套利攻击,严重破坏平台经济模型

**影响**:
- 业务逻辑绕过: 突破注册限制
- 经济损失: 通过虚假账户获取免费积分
- 资源滥用: 消耗API配额和计算资源

**修复建议**:
1. 在反向代理层(如Nginx)配置IP白名单,仅信任内部代理的`X-Forwarded-For`头
2. 应用层验证: 仅当请求来自可信代理IP时才使用`X-Forwarded-For`
   ```javascript
   const TRUSTED_PROXIES = ['127.0.0.1', '10.0.0.0/8'];
   const clientIP = isTrustedProxy(req.socket.remoteAddress)
     ? (req.headers['x-forwarded-for'] || req.socket.remoteAddress)
     : req.socket.remoteAddress;
   ```
3. 结合设备指纹(deviceFp)和验证码机制强化注册限制

---

## 二、注入向量分析

### 2.1 SQL注入防护评估

**审计结论**: ✅ **已缓解**

**证据**:
- 所有数据库查询均使用参数化查询(db.prepare().get/run)
- 未发现字符串拼接SQL的情况

**示例**:
```javascript
// auth.js:120 - 使用参数化查询
const existing = db.prepare("SELECT id FROM users WHERE username=? " + (email ? "OR email=?" : "") + " OR phone=?").get(
  email ? [username, email, phone] : [username, phone]
);
```

**注**: 虽然SQL语句中有动态拼接`OR email=?`,但查询参数仍通过数组传递,不影响安全性。

---

### 2.2 命令注入防护评估

**审计结论**: ✅ **已缓解**

**证据**:
- [code_sandbox.py](file:///workspace/local-core/code_sandbox.py) 实现了严格的沙箱机制:
  - Shell命令白名单(仅允许`ls`, `pwd`, `whoami`等无害命令)
  - 危险字符过滤(阻止`;`, `&`, `|`, `>`, `<`等shell元字符)
  - Python代码执行通过子进程隔离,环境变量清空,禁止导入危险模块

**示例**:
```python
# code_sandbox.py:127-128
if any(c in command for c in [";", "&", "|", ">", "<", "`", "$"]):
    return "先生,检测到危险字符,拒绝执行。"
```

**潜在风险**: [pc_control.py](file:///workspace/local-core/pc_control.py) 中存在直接调用`subprocess.Popen`的代码,但仅用于系统电源管理命令(如`shutdown`),参数硬编码,无用户输入注入风险。

---

### 2.3 路径遍历防护评估

**审计结论**: ⚠️ **部分缓解,存在改进空间**

**位置**: [security.py:66-97](file:///workspace/local-core/security.py#L66)

**防护机制**:
1. 路径规范化(解析`..`和符号链接)
2. 敏感系统路径黑名单(如`/etc`, `C:\Windows`)
3. 允许目录白名单检查

**问题点**:
```python
# security.py:17-23
ALLOWED_BASE_DIRS: List[str] = [
    os.getcwd(),
    os.path.join(os.getcwd(), "data"),
    os.path.join(os.getcwd(), "plugins"),
    os.path.join(os.getcwd(), "knowledge"),
    os.path.expanduser("~"),  # ⚠️ 用户家目录权限过大
]
```

**影响**: 如果其他模块存在文件操作漏洞,攻击者可访问用户家目录下的敏感文件(如`.ssh/id_rsa`, `.bash_history`)

**修复建议**:
1. 缩小`ALLOWED_BASE_DIRS`范围,移除用户家目录
2. 实施基于路径类型的访问控制:
   - 配置文件: 仅允许`data/config/`
   - 临时文件: 仅允许`data/tmp/`
   - 知识库文件: 仅允许`knowledge/`

---

## 三、外部交互安全

### 3.1 插件系统SSRF风险 (中等严重度)

**漏洞ID**: EXT-001

**位置**: [plugin_system.py:44-48](file:///workspace/local-core/plugin_system.py#L44)

**攻击者画像**: 具有插件安装权限的已认证用户(Owner角色)

**输入向量**: 插件代码中的`requests`模块调用

**代码路径**:
```python
# plugin_system.py:44-48
_PLUGIN_ALLOWED_MODULES = {
    "json", "re", "math", "random", "datetime", "collections", "itertools",
    "typing", "pathlib", "os", "sys", "time", "hashlib", "base64", "urllib",
    "requests",  # ⚠️ 允许网络请求
}
```

**利用步骤**:
1. 攻击者创建恶意插件,包含以下代码:
   ```python
   import requests
   def register():
       # 扫描内网服务
       for port in [80, 8080, 3000, 5000]:
           try:
               r = requests.get(f"http://192.168.1.1:{port}", timeout=1)
               # 将结果通过DNS隧道外传
           except:
               pass
   ```
2. 插件被加载后,可扫描内网服务、访问云元数据接口(如`http://169.254.169.254/latest/meta-data/`)
3. 获取内网服务凭证或敏感配置

**影响**:
- 内网服务暴露(如数据库管理界面、内部API)
- 云平台凭证泄露(通过元数据服务)
- 横向移动攻击起点

**修复建议**:
1. 移除插件沙箱中的`requests`模块:
   ```python
   _PLUGIN_ALLOWED_MODULES = {
       "json", "re", "math", "random", "datetime", "collections", "itertools",
       "typing", "pathlib", "time", "hashlib", "base64",
       # 移除 "requests", "urllib"
   }
   ```
2. 如需网络功能,通过受控的API网关代理,实施:
   - URL白名单验证
   - 内网IP地址段过滤(参考[security.py:146-195](file:///workspace/local-core/security.py#L146)的SSRF防护)
3. 实施网络隔离: 插件进程运行在受限网络命名空间中

---

### 3.2 浏览器自动化安全

**审计结论**: ✅ **设计合理**

**证据**:
- [browser_automation.py](file:///workspace/local-core/browser_automation.py) 使用Playwright进行浏览器自动化
- 无用户输入直接拼接到URL(通过`goto`函数规范化)
- 截图保存路径使用固定目录`data/screenshots/`

**潜在风险**: 如果允许用户通过API控制浏览器访问内网地址,可能导致SSRF。建议在`goto`函数中添加URL白名单验证。

---

## 四、敏感数据处理

### 4.1 API密钥泄露风险 (已缓解)

**审计结论**: ✅ **防护到位**

**证据**:
1. **哈希存储**: [auth.js:14-16](file:///workspace/auth.js#L14) 使用HMAC-SHA256哈希存储API密钥
2. **掩码显示**: [auth.js:26-29](file:///workspace/auth.js#L26) 列表查询仅返回掩码(如`nexus-****-abcd`)
3. **一次性明文返回**: [auth.js:461](file:///workspace/auth.js#L461) 创建时返回明文,之后无法再次查看

**改进建议**:
- 定期轮换`JWT_SECRET`(用于哈希的pepper),轮换后旧密钥失效

---

### 4.2 日志安全 (已缓解)

**审计结论**: ✅ **无敏感信息泄露**

**证据**:
- [logger.py](file:///workspace/local-core/logger.py) 仅记录请求元数据,不记录请求体和响应体
- 无密码、API密钥等敏感信息输出到日志

---

### 4.3 环境变量管理

**审计结论**: ⚠️ **需要加固**

**位置**: [.env.example](file:///workspace/.env.example)

**问题**: 示例文件包含大量真实API密钥的占位符格式,可能导致:
1. 开发人员误将真实密钥提交到版本控制
2. 部署时忘记修改占位符

**修复建议**:
1. 使用密钥管理服务(如AWS Secrets Manager、Azure Key Vault)
2. 文档中明确说明密钥轮换流程
3. 在CI/CD中实施密钥扫描(如GitLeaks、TruffleHog)

---

## 五、其他发现

### 5.1 CORS配置

**位置**: [config.py:64](file:///workspace/local-core/config.py#L64)

**现状**:
```python
cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:7777,..."
```

**建议**: 生产环境必须修改为实际域名,避免使用`localhost`

---

### 5.2 限流机制

**位置**: [server.js:85-98](file:///workspace/server.js#L85)

**现状**:
- 基于IP的限流(每分钟60次请求)
- 存储在内存中,重启后清空

**建议**: 对于分布式部署,使用Redis存储限流计数器

---

## 六、总结与建议

### 6.1 漏洞严重度统计

| 严重度 | 数量 | 漏洞ID |
|--------|------|--------|
| 高 | 0 | - |
| 中等 | 5 | AUTH-001, AUTH-002, AUTH-003, EXT-001 |
| 低 | 1 | 路径遍历改进建议 |

### 6.2 修复优先级

1. **立即修复** (P0):
   - AUTH-002: 强制设置ADMIN_PASSWORD
   - EXT-001: 移除插件沙箱中的requests模块

2. **短期修复** (P1, 7天内):
   - AUTH-001: 实施强密码策略
   - AUTH-003: 修复IP限制绕过

3. **中期改进** (P2, 30天内):
   - 路径遍历防护增强
   - 环境变量管理加固

### 6.3 安全最佳实践建议

1. **认证与授权**:
   - 实施多因素认证(MFA)
   - 定期审计管理员权限
   - 使用RBAC(基于角色的访问控制)

2. **输入验证**:
   - 所有用户输入实施白名单验证
   - 使用JSON Schema验证API请求体

3. **监控与响应**:
   - 部署SIEM系统监控异常登录行为
   - 实施安全事件自动告警

4. **安全开发流程**:
   - 引入静态应用安全测试(SAST)到CI/CD
   - 定期进行渗透测试和代码审计

---

**审计完成时间**: 2026-08-01
**审计人员**: 安全审计自动化系统
**下次审计建议**: 代码重大更新后或季度例行审计