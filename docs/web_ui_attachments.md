# Web UI 附件上传功能

## 功能概述

为 AgentMatrix Web 应用的 "New Conversation" 对话框添加了附件上传功能，支持点击选择和拖放上传。

## 实现功能

### 1. 附件上传区域
- **点击上传**：点击上传区域打开文件选择对话框
- **拖放上传**：直接拖放文件到上传区域
- **多文件支持**：支持同时上传多个文件
- **文件类型**：支持所有文件类型

### 2. 附件列表显示
- 显示每个附件的文件名和大小
- 文件图标和大小格式化显示
- 单独删除每个附件的按钮
- 附件总数统计

### 3. 拖放效果
- 拖放时的视觉反馈（边框和背景色变化）
- 平滑的过渡动画

### 4. 表单集成
- 自动传递附件到后端 API
- 表单重置时清空附件
- 发送时显示附件数量

## 使用方法

### 用户界面

1. **打开新对话**
   - 点击左侧边栏的 "New Conversation" 按钮

2. **选择收件人**
   - 在 "To" 字段搜索并选择一个 Agent

3. **编写消息**
   - 在 "Message" 字段输入消息内容

4. **添加附件（新功能）**
   - **方式1：点击上传**
     - 点击 "Attachments" 下方的上传区域
     - 在文件选择对话框中选择一个或多个文件

   - **方式2：拖放上传**
     - 将文件直接拖放到上传区域
     - 松开鼠标完成上传

5. **管理附件**
   - 查看已选择的附件列表
   - 点击附件右侧的 ❌ 按钮删除单个附件
   - 查看附件总数

6. **发送**
   - 点击 "Send" 按钮发送邮件和附件
   - 等待发送完成

## 技术实现

### 前端 (JavaScript)

#### 1. 状态管理
```javascript
newEmail: {
    recipient: '',
    body: '',
    attachments: []  // 新增：存储附件文件
}
```

#### 2. 附件管理函数

```javascript
// 添加附件
addAttachments(files) {
    for (let file of files) {
        // 防止重复添加同名文件
        if (!this.newEmail.attachments.some(f => f.name === file.name)) {
            this.newEmail.attachments.push(file);
        }
    }
}

// 删除附件
removeAttachment(index) {
    this.newEmail.attachments.splice(index, 1);
}

// 处理文件选择
handleFileSelect(event) {
    const files = event.target.files;
    this.addAttachments(files);
    event.target.value = '';  // 清空 input
}

// 处理文件拖放
handleFileDrop(event) {
    event.preventDefault();
    const files = event.dataTransfer.files;
    this.addAttachments(files);
}

// 处理拖放悬停
handleFileDragOver(event) {
    event.preventDefault();
}

// 格式化文件大小
formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}
```

#### 3. 发送邮件

```javascript
async sendEmail() {
    // ... 验证逻辑 ...

    const response = await API.sendEmail('new', {
        recipient: this.newEmail.recipient,
        subject: '',
        body: this.newEmail.body
    }, this.newEmail.attachments);  // 传递附件

    // ... 处理响应 ...
}
```

### 前端 (HTML)

```html
<!-- 附件上传区域 -->
<div @dragover="handleFileDragOver($event)"
     @drop="handleFileDrop($event)"
     class="border-2 border-dashed border-surface-200 rounded-xl p-6 text-center hover:border-primary-300 hover:bg-primary-50/30 transition-all duration-200 cursor-pointer"
     @click="$refs.fileInput.click()">
    <input type="file"
           x-ref="fileInput"
           @change="handleFileSelect($event)"
           multiple
           class="hidden"
           accept="*/*">
    <i class="ti ti-upload text-3xl text-surface-400 mb-2"></i>
    <p class="text-sm text-surface-600 mb-1">
        <span class="font-medium text-primary-600">Click to upload</span> or drag and drop
    </p>
    <p class="text-xs text-surface-400">Any file type supported</p>
</div>

<!-- 附件列表 -->
<div x-show="newEmail.attachments.length > 0" class="mt-3 space-y-2">
    <template x-for="(file, index) in newEmail.attachments" :key="index">
        <div class="flex items-center justify-between p-3 bg-surface-50 rounded-lg">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
                    <i class="ti ti-file text-primary-600"></i>
                </div>
                <div>
                    <p class="text-sm font-medium text-surface-700 truncate" x-text="file.name"></p>
                    <p class="text-xs text-surface-400" x-text="formatFileSize(file.size)"></p>
                </div>
            </div>
            <button @click="removeAttachment(index)">
                <i class="ti ti-x"></i>
            </button>
        </div>
    </template>
</div>
```

### 样式设计

使用 Tailwind CSS 实现现代化的 UI：
- 虚线边框的拖放区域
- 悬停效果（边框和背景色变化）
- 圆角卡片设计
- 图标和颜色系统
- 响应式布局

## 文件变更

### 修改的文件
1. **web/js/app.js**
   - 添加 `attachments` 字段到 `newEmail` 状态
   - 添加附件管理函数（6个）
   - 修改 `sendEmail()` 函数支持附件

2. **web/index.html**
   - 在 New Email Modal 添加附件上传 UI
   - 添加拖放事件处理
   - 添加附件列表显示

## 测试

### 手动测试步骤

1. **基本功能测试**
   - ✅ 打开 New Conversation 对话框
   - ✅ 选择收件人
   - ✅ 输入消息内容

2. **附件上传测试**
   - ✅ 点击上传区域选择文件
   - ✅ 拖放文件到上传区域
   - ✅ 查看附件列表显示
   - ✅ 删除单个附件

3. **发送测试**
   - ✅ 发送带附件的邮件
   - ✅ 验证后端接收附件
   - ✅ 检查附件保存到共享存储

4. **边界情况测试**
   - ✅ 上传同名文件（防止重复）
   - ✅ 上传多个文件
   - ✅ 取消对话框后清空附件
   - ✅ 不同文件类型（文本、图片、PDF等）

## 用户体验

### 视觉反馈
- 悬停时边框和背景色变化
- 文件图标和大小格式化
- 删除按钮的悬停效果
- 平滑的过渡动画

### 交互流程
1. 用户看到清晰的上传区域
2. 拖放或点击上传
3. 立即看到附件列表
4. 可以随时删除附件
5. 发送时自动传递附件

### 错误处理
- 防止上传同名文件
- 文件大小格式化显示
- 发送失败时的错误提示

## 下一步改进

### 短期
1. 添加文件类型图标（根据文件类型显示不同图标）
2. 添加文件大小限制
3. 添加上传进度指示
4. 改进移动端体验

### 长期
1. 支持文件夹上传
2. 支持粘贴上传（截图等）
3. 添加文件预览功能
4. 支持拖放排序

## 浏览器兼容性

- ✅ Chrome/Edge (推荐)
- ✅ Firefox
- ✅ Safari
- ⚠️ IE 11 (不支持 File API)

## 安全考虑

1. **文件类型验证**
   - 前端：接受所有类型（`accept="*/*"`）
   - 后端：建议添加文件类型验证

2. **文件大小限制**
   - 当前：无限制
   - 建议：添加合理的文件大小上限（如 10MB）

3. **文件名处理**
   - 后端已实现文件名清理
   - 防止路径遍历攻击

## 总结

成功为 Web UI 添加了完整的附件上传功能，用户现在可以通过点击或拖放的方式添加附件，体验流畅，界面美观。
