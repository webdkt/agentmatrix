# "蚂蚁搬家" - 安全的命令迁移策略

## 核心原则

一次只迁移 **一个命令**，每次修改都是安全的、可验证的、可回滚的。

## 迁移步骤（针对单个命令）

### Step 1: Extract - 提取原始代码
```bash
# 提取命令代码（包含 #[tauri::command] 到函数结束）
sed -n 'START,ENDp' main.rs > /tmp/command_original.txt
```

### Step 2: New - 在新模块中创建副本
- 将提取的代码粘贴到新模块文件
- 添加 `pub` 关键字
- **不要**修改 main.rs

### Step 3: Compare - 详细比对验证
```bash
# 比对函数签名
diff -u <原始代码> <新代码>

# 验证关键字：pub, async, 参数类型, 返回值类型
```

### Step 4: Rename old - 重命名旧函数避免冲突
```rust
// 在 main.rs 中，将旧函数重命名为 _DEPRECATED_xxx
#[tauri::command]
fn _DEPRECATED_copy_file(src: String, dest: String) -> Result<(), String> {
    // ... 原始代码
}
```

### Step 5: Test - 验证编译和功能
```bash
cargo check
# 运行应用，测试该功能
```

### Step 6: Update handler - 更新 invoke_handler
```rust
// 将旧引用改为新引用
-invoke_handler![
-   copy_file,
+   commands::filesystem::copy_file,
]
```

### Step 7: Final test - 最终测试
- 编译验证
- 功能测试
- 提交更改

### Step 8: Delete old - 删除旧代码
- 删除 main.rs 中的 `_DEPRECATED_xxx` 函数
- 提交

## 每次迁移的文件清单

1. 提取：`/tmp/command_NAME_original.txt`
2. 比对：`/tmp/command_NAME_diff.txt`
3. 备份：当前分支的 git status

## 验证清单

- [ ] 代码完全一致（除了 pub 关键字）
- [ ] 编译通过
- [ ] 功能测试通过
- [ ] git 提交

## 回滚命令

如果任何步骤出错：
```bash
# 回滚单个命令的修改
git checkout HEAD -- src-tauri/src/main.rs
git checkout HEAD -- src-tauri/src/commands/XXX.rs

# 或回滚到上一个 commit
git reset --hard HEAD~1
```

## 下一步：Phase 3.1

从 **save_llm_config** 开始，这是第一个配置命令。
