# 修复 get_tab 方法返回错误 tab 的 bug

## 问题描述

当 Chrome 打开在线 PDF 时，实际上存在两个 tab：
1. **网页的 tab**（正常的 tab，包含实际网页内容）
2. **Chrome PDF viewer extension 的 tab**（URL 以 `chrome-extension://` 开头）

### 修复前的问题
```python
async def get_tab(self) -> TabHandle:
    """获取当前焦点标签页的句柄"""
    if not self.browser:
        raise RuntimeError("Browser not started. Call start() first.")

    # 直接返回最新的 tab，可能是 chrome extension
    return await asyncio.to_thread(lambda: self.browser.latest_tab)
```

**问题：** `get_tab()` 返回 `browser.latest_tab`，可能错误地返回 chrome extension 的 tab（如 PDF viewer），导致后续操作在错误的 tab 上执行。

## 修复方案

### 1. 修改 `get_tab()` 方法

**新逻辑：**
1. 获取所有 tabs：使用 `browser.get_tabs()`
2. 过滤掉 chrome extension 的 tab（URL 以 `chrome-extension://` 开头）
3. 如果找到正常的 tab，返回最新的
4. 如果找不到正常的 tab，创建并返回一个新 tab

**实现代码：**
```python
async def get_tab(self) -> TabHandle:
    """获取当前焦点标签页的句柄"""
    if not self.browser:
        raise RuntimeError("Browser not started. Call start() first.")

    # 在线程池中获取所有标签页
    all_tabs = await asyncio.to_thread(self.browser.get_tabs)

    # 过滤掉 chrome extension 的 tab（如 PDF viewer）
    normal_tabs = []
    for tab in all_tabs:
        try:
            url = tab.url if hasattr(tab, 'url') else ""
            # 保留 URL 不是 chrome-extension:// 的 tab
            if url and not url.startswith('chrome-extension://'):
                normal_tabs.append(tab)
        except Exception:
            # 如果获取 URL 失败，保留这个 tab（可能是新创建的空白 tab）
            normal_tabs.append(tab)

    # 如果找到正常的 tab，返回最新的
    if normal_tabs:
        self.logger.debug(f"Found {len(normal_tabs)} normal tab(s) out of {len(all_tabs)} total tabs")
        return normal_tabs[-1]  # 最新的 tab

    # 如果找不到正常的 tab，创建一个新的
    self.logger.warning(f"No normal tab found (all {len(all_tabs)} tabs are chrome-extension), creating a new tab")
    return await self.create_tab()
```

### 2. 实现 `create_tab()` 方法

**修复前：**
```python
async def create_tab(self, url: Optional[str] = None) -> TabHandle:
    """打开一个新的标签页，返回句柄"""
    if not self.browser:
        raise RuntimeError("Browser not started. Call start() first.")

    # TODO: 实现创建标签页的逻辑
    pass
```

**修复后：**
```python
async def create_tab(self, url: Optional[str] = None) -> TabHandle:
    """打开一个新的标签页，返回句柄"""
    if not self.browser:
        raise RuntimeError("Browser not started. Call start() first.")

    # 在线程池中创建新标签页
    new_tab = await asyncio.to_thread(self.browser.new_tab)

    # 如果提供了 URL，导航到该 URL
    if url:
        await asyncio.to_thread(new_tab.get, url)
        await asyncio.sleep(0.5)  # 等待页面初始化

    self.logger.info(f"Created new tab{' with URL: ' + url if url else ''}")
    return new_tab
```

## 测试验证

### 测试场景 1：正常过滤
```
输入 tabs:
  1. https://www.example.com
  2. chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html (PDF viewer)
  3. https://www.google.com

预期输出:
  保留 2 个正常 tab
  过滤掉 1 个 extension tab
  返回: https://www.google.com（最新的）
```

### 测试场景 2：所有 tabs 都是 extension（边界情况）
```
输入 tabs:
  1. chrome-extension://abc/index.html
  2. chrome-extension://def/index.html

预期输出:
  没有找到正常 tab
  创建并返回新 tab
```

### 测试场景 3：混合 tabs
```
输入 tabs:
  1. about:blank
  2. https://www.example.com
  3. chrome-extension://abc/index.html
  4. https://www.github.com

预期输出:
  保留 3 个非 extension tab
  返回: https://www.github.com（最新的）
```

## 修复效果

### ✅ 主要改进
1. **正确处理 PDF 场景**：打开在线 PDF 时，返回网页 tab 而不是 PDF viewer tab
2. **过滤所有 chrome extensions**：不只限于 PDF viewer，过滤所有 chrome-extension:// URL
3. **健壮的边界处理**：所有 tabs 都是 extension 时自动创建新 tab
4. **实现 create_tab()**：之前未实现的方法现在可以正常工作

### 📊 影响范围
- `get_tab()` 方法被多个地方调用，修改后保持向后兼容
- 修复后的逻辑更健壮，能够正确处理各种边界情况
- 不影响现有的正常使用场景

### 🔍 适用场景
- ✅ 打开在线 PDF 时正确返回网页 tab
- ✅ 过滤掉所有 chrome extension tabs
- ✅ 保留 about:blank 和其他正常页面
- ✅ 边界情况：所有 tabs 都是 extension 时自动创建新 tab

## 修改文件
- `src/agentmatrix/core/browser/drission_page_adapter.py`

## 测试文件
- `tests/test_get_tab_fix.py`

## 版本历史
- **2026-02-02**: 初始版本，修复 get_tab 返回 chrome extension tab 的 bug
