# Bash 命令执行安全方案

## 需求分析

1. 将 `shell_cmd` 改名为 `bash`
2. 支持 Agent 运行 bash 命令和脚本
3. 处理脚本中的注释行
4. **最大化安全保证**

---

## 多层防御策略

### Layer 1: 输入预处理

#### 1.1 注释过滤
```python
def _remove_bash_comments(script: str) -> str:
    """
    移除 bash 脚本中的注释行

    规则：
    - 移除以 # 开头的行（但保留 shebang #!）
    - 移除行尾的 # 注释
    - 保留字符串中的 # (echo "hello # world")
    """
    lines = []
    for line in script.split('\n'):
        # 跳过空行
        if not line.strip():
            continue

        # 保留 shebang
        if line.strip().startswith('#!'):
            lines.append(line)
            continue

        # 移除注释行
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # 移除行尾注释（但要小心字符串中的 #）
        # 简化版：只在行首且后面有空格时移除
        in_string = False
        quote_char = None
        result = []
        i = 0
        while i < len(line):
            char = line[i]
            if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif quote_char == char:
                    in_string = False
                    quote_char = None
            elif char == '#' and not in_string:
                # 找到注释，跳过剩余部分
                break
            result.append(char)
            i += 1

        cleaned = ''.join(result).strip()
        if cleaned:
            lines.append(cleaned)

    return '\n'.join(lines)
```

#### 1.2 语法检查
```python
async def _validate_bash_syntax(script: str) -> tuple[bool, str]:
    """
    验证 bash 脚本语法

    Returns:
        (is_valid, error_message)
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(script)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['bash', '-n', temp_path],  # -n 只检查语法，不执行
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "语法检查超时"
    finally:
        import os
        os.unlink(temp_path)
```

---

### Layer 2: 命令白名单验证

#### 2.1 分级白名单系统

```python
# 分级白名单设计
BASH_WHITELIST = {
    # ===== 等级 1: 完全安全（无副作用）=====
    "safe": {
        # 文本查看
        "cat", "head", "tail", "less", "more",
        # 搜索
        "grep", "egrep", "fgrep",
        # 排序和统计
        "sort", "uniq", "wc", "nl",
        # 文本处理
        "cut", "tr", "sed", "awk",
        # 系统信息（只读）
        "pwd", "date", "whoami", "hostname", "uname",
        "df", "du", "free", "uptime",
        # 进程查看
        "ps", "top", "htop",
    },

    # ===== 等级 2: 需要参数限制（有文件操作）=====
    "restricted": {
        # 列出文件
        "ls", "ll", "dir",
        # 创建目录
        "mkdir",  # 限制：不允许 -p 递归创建父目录
        # 创建文件
        "touch",
        # 删除文件（需要额外检查）
        "rm",  # 限制：不允许 -rf，需要确认
        # 复制/移动（需要路径检查）
        "cp", "mv",
        # 压缩
        "tar", "gzip", "gunzip", "zip", "unzip",
        # 权限（需要严格限制）
        "chmod",
    },

    # ===== 等级 3: 需要用户确认（危险命令）=====
    "dangerous": {
        # 网络请求
        "curl", "wget",
        # 包管理
        "apt", "yum", "pip", "npm",
        # 开发工具
        "python", "python3", "node", "npm",
        "git",
        # 数据库
        "mysql", "psql",
        # Docker
        "docker",
        # 编辑器
        "vi", "vim", "nano",
    },
}
```

#### 2.2 命令解析和验证

```python
async def _validate_bash_command(command: str) -> tuple[bool, str]:
    """
    验证单个 bash 命令

    Returns:
        (is_allowed, error_message)
    """
    # 解析命令（考虑管道、重定向等）
    tokens = parse_command_tokens(command)

    if not tokens:
        return True, ""  # 空命令

    # 检查每个命令
    for cmd_token in tokens:
        cmd_name = cmd_token['name']

        # 检查是否在白名单中
        if cmd_name in BASH_WHITELIST['safe']:
            # 等级1：完全允许
            continue

        elif cmd_name in BASH_WHITELIST['restricted']:
            # 等级2：参数检查
            if not _validate_restricted_command(cmd_token):
                return False, f"命令 '{cmd_name}' 参数不允许或需要额外限制"

        elif cmd_name in BASH_WHITELIST['dangerous']:
            # 等级3：需要用户确认
            return False, f"命令 '{cmd_name}' 需要用户确认（暂不支持）"

        else:
            # 不在白名单
            return False, f"命令 '{cmd_name}' 不在白名单中"

    return True, ""

def parse_command_tokens(command: str) -> list:
    """
    解析命令，处理管道、重定向等

    Returns:
        list of dict: [{'name': 'ls', 'args': ['-l', '/tmp']}]
    """
    # 简化实现：按管道分割
    parts = command.split('|')

    tokens = []
    for part in parts:
        # 处理重定向（暂时简化）
        if '>' in part:
            part = part.split('>')[0]

        # 解析命令和参数
        words = part.strip().split()
        if words:
            tokens.append({
                'name': words[0],
                'args': words[1:]
            })

    return tokens
```

---

### Layer 3: 沙箱执行

#### 3.1 使用 `bwrap` (bubblewrap) 沙箱

```python
async def _run_bash_in_sandbox(
    command: str,
    working_context,
    timeout: int = 30
) -> tuple[bool, str, str]:
    """
    在沙箱中执行 bash 命令

    Returns:
        (success, stdout, stderr)
    """
    import subprocess

    # 使用 bubblewrap 创建沙箱
    # 如果没有 bwrap，回退到普通模式（但警告）
    use_sandbox = _check_bwrap_available()

    base_cmd = []
    if use_sandbox:
        # 创建沙箱环境
        base_cmd = [
            'bwrap',
            '--ro-bind', '/usr', '/usr',
            '--ro-bind', '/bin', '/bin',
            '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64',
            '--bind', working_context.current_dir, '/workspace',
            '--die-with-parent',
            '--new-session',
            '--unshare-all',
            '--share-net',  # 允许网络（可选）
        ]
    else:
        self.logger.warning("⚠️  bubblewrap 未安装，使用非沙箱模式执行")

    # 构建完整命令
    cmd = base_cmd + ['bash', '-c', command]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=working_context.current_dir,
            timeout=timeout,
            # 资源限制
            # preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (1024*1024*100, 1024*1024*100))  # 100MB 内存限制
        )

        return (result.returncode == 0, result.stdout, result.stderr)

    except subprocess.TimeoutExpired:
        return (False, "", f"命令执行超时（{timeout}秒）")
    except Exception as e:
        return (False, "", str(e))
```

#### 3.2 使用 `firejail` 作为替代方案

```python
async def _run_with_firejail(command: str, working_context) -> tuple[bool, str, str]:
    """
    使用 firejail 沙箱执行命令
    """
    import subprocess

    cmd = [
        'firejail',
        '--quiet',
        '--private=working_context.current_dir',
        '--nosound',
        '--novideo',
        'bash', '-c', command
    ]

    try:
        result = subprocess.run(cmd, ...)
        return (result.returncode == 0, result.stdout, result.stderr)
    except Exception as e:
        return (False, "", str(e))
```

---

### Layer 4: 资源限制

```python
import resource

def _set_resource_limits():
    """
    设置资源限制

    限制：
    - CPU 时间：30秒
    - 内存：512MB
    - 进程数：10个
    """
    # CPU 时间限制
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))

    # 内存限制
    resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))

    # 进程数限制
    resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
```

---

### Layer 5: 审计日志

```python
async def _log_bash_execution(
    command: str,
    success: bool,
    output: str,
    working_context
):
    """
    记录 bash 命令执行日志
    """
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'command': command,
        'working_dir': working_context.current_dir,
        'success': success,
        'output_length': len(output),
        'user': working_context.user_session_id,
    }

    # 写入审计日志
    audit_log_path = os.path.join(
        working_context.base_dir,
        'temp',
        '.bash_audit.log'
    )

    with open(audit_log_path, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
```

---

## 完整实现示例

### 新的 `bash` action

```python
@register_action(
    description="""执行 bash 命令或脚本（安全沙箱模式）

支持：
- 单行命令：bash command="ls -l"
- 多行脚本：bash script="cd /tmp && ls"

安全特性：
- 白名单命令验证
- 语法预检查
- 沙箱执行（bubblewrap）
- 资源限制（CPU 30s, 内存 512MB）
- 审计日志""",
    param_infos={
        "command": "bash 命令或脚本（多行脚本用 \\n 分隔）",
        "timeout": "超时时间（秒，默认30）",
    }
)
async def bash(self, command: str, timeout: int = 30) -> str:
    """
    执行 bash 命令（安全沙箱模式）
    """
    # 1. 预处理：移除注释
    cleaned_command = self._remove_bash_comments(command)

    # 2. 语法检查
    is_valid, syntax_error = await self._validate_bash_syntax(cleaned_command)
    if not is_valid:
        return f"❌ 脚本语法错误：\n{syntax_error}"

    # 3. 命令白名单验证
    is_allowed, allow_error = await self._validate_bash_command(cleaned_command)
    if not is_allowed:
        return f"❌ 命令验证失败：\n{allow_error}"

    # 4. 在沙箱中执行
    success, stdout, stderr = await self._run_bash_in_sandbox(
        cleaned_command,
        self.working_context,
        timeout=timeout
    )

    # 5. 记录审计日志
    await self._log_bash_execution(cleaned_command, success, stdout + stderr, self.working_context)

    # 6. 返回结果
    output = stdout
    if stderr:
        output += f"\n[stderr]\n{stderr}"

    if not output:
        output = "(无输出)"

    return f"✅ 执行成功\n{output}" if success else f"❌ 执行失败\n{output}"
```

---

## 白名单扩展建议

### 推荐的扩展白名单（Unix）

```python
EXTENDED_WHITELIST = {
    # 文件操作（基础）
    "ls", "ll", "dir", "pwd",
    "cd", "mkdir", "touch", "rm", "cp", "mv",

    # 文本查看
    "cat", "head", "tail", "less", "more",

    # 文本搜索
    "grep", "egrep", "fgrep", "find", "locate",

    # 文本处理
    "sed", "awk", "cut", "tr", "sort", "uniq", "wc", "nl",

    # 压缩解压
    "tar", "gzip", "gunzip", "zip", "unzip",

    # 系统信息
    "df", "du", "free", "top", "ps", "uptime", "uname",
    "whoami", "hostname", "date", "cal",

    # 开发工具（谨慎）
    "python3", "node", "git",

    # 网络工具（谨慎）
    "curl", "wget", "ping", "ssh", "scp",

    # 包管理（谨慎）
    "pip", "npm", "apt", "yum",
}
```

---

## 安全配置选项

### 可配置的安全级别

```python
BASH_SECURITY_LEVELS = {
    "strict": {
        "whitelist": {"safe"},  # 只允许完全安全的命令
        "sandbox": True,
        "timeout": 30,
        "memory_limit": "100MB",
    },
    "balanced": {
        "whitelist": {"safe", "restricted"},
        "sandbox": True,
        "timeout": 60,
        "memory_limit": "512MB",
    },
    "permissive": {
        "whitelist": {"safe", "restricted", "dangerous"},
        "sandbox": True,
        "timeout": 300,
        "memory_limit": "1GB",
    },
}
```

---

## 总结

### 安全措施优先级

1. **必须实现**
   - ✅ 注释过滤
   - ✅ 语法检查
   - ✅ 分级白名单
   - ✅ 路径限制（在 working_context 内）

2. **强烈推荐**
   - ✅ 沙箱执行（bubblewrap/firejail）
   - ✅ 资源限制（CPU、内存）
   - ✅ 超时控制

3. **可选增强**
   - 🔄 审计日志
   - 🔄 用户确认机制
   - 🔄 可配置安全级别

### 实施建议

**阶段 1**：基础安全
- 改名 `shell_cmd` → `bash`
- 扩大白名单到常用命令
- 实现注释过滤
- 实现语法检查

**阶段 2**：增强安全
- 实现沙箱执行
- 添加资源限制
- 实现审计日志

**阶段 3**：高级特性
- 可配置安全级别
- 用户确认机制
- 更精细的参数检查
