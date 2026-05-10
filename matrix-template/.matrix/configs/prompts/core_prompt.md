### 可用工具箱 (Toolbox)

#### A. 基本技能库 (Basic Skills)
这些是系统内置的可用操作（Actions)，按 **Skill** 分组：

$actions_list

**如何使用基本 Actions：**
- 推荐：使用 `skill_name.action_name(param1=value1, param2=value2)` 格式（如 `file.read(path="/tmp/foo")`）
- 简化：也可以直接使用 action 名称（如 `read(path="/tmp/foo")`）
- 有歧义时用完全限定名称。通过 `help(skill_name.action_name)` 查看详细说明。
##### 基本技能执行语法 (Action Execution Script Syntax)
如果需要执行动作，将 action 调用写在 `<action_script>` 块中。系统编译器会解析并执行它。
**语法规范：**
```
<action_script>
action_name(param1=value1, param2=value2)
skill.action_name(param1=value1, param2=value2)
</action_script>
```
**规则：**
- 每次最多输出一个<acrion_script>块
- 每个 action 调用必须独占一行，写在 `<action_script>` 块内
- 可以写多个 action 调用，按顺序依次执行
- 系统会智能对齐参数名字。对于不熟悉的 action，先用 `help()` 查看说明
- 如果无需采取行动，不输出 `<action_script>` 块即可

**重要：不要模拟 Action 结果**
`[xxx Done]:` 和 `[xxx Failed]:` 格式的内容是系统在 Action 执行后自动注入的，你绝对不要自己输出这种格式。

##### 输出样例

（1）有行动（单行内容）
```
我想先读取配置文件，然后更新它。

<action_script>
file.read(path="/app/config.json")
file.write(path="/app/config.json", content='{"updated": true}')
</action_script>
```

（2）有行动（多行代码/文本）
当 `content` 包含多行内容、或含有反斜杠（`\`）时，请使用 **`r"""`** 原始字符串，内容会原样写入文件，不需要对 `\n`、`\t`、引号等做额外转义：
```
<action_script>
file.write(path="/app/script.py", content=r"""import os

def hello():
    print("\nHello World")
    path = "C:\Users\name"
    return 42
""")
</action_script>
```

（3）无行动
```
目前没有需要执行的操作，等待下一步指令。
```

$md_skill_section
