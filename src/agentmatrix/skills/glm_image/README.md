# GLM Image Skill

智谱图像生成技能，使用智谱 AI 的 GLM-Image 模型从文本提示生成高质量图像。

## 功能

- 根据自然语言描述生成高质量图像
- 支持中文提示词
- 自动保存图像到 `~/current_task/tmp/` 目录

## 安装

此 skill 依赖 `aiohttp` 库，已在项目依赖中包含。

## 配置

在使用前，需要设置环境变量 `GLM_API_KEY`：

```bash
export GLM_API_KEY='your-api-key-here'
```

获取 API Key：https://open.bigmodel.cn/usercenter/proj-mgmt/apikeys

## 使用方法

### 在 Agent 配置中使用

在 Agent 的 YAML 配置中添加 `glm_image` skill：

```yaml
name: "ImageBot"
persona: "你是一个图像生成助手"
skills: ["glm_image"]
```

### Action 参数

`generate_image` action 接受以下参数：

- `prompt` (必需): 图像的自然语言描述

### 示例

```python
# 生成一只可爱的小猫
result = await generate_image("一只可爱的小猫咪，坐在阳光明媚的窗台上，背景是蓝天白云")
# 返回: "/Users/username/current_task/tmp/glm_image_20260414_091345.png"

# 生成风景画
result = await generate_image("壮丽的山川河流，日落时分的金色阳光洒在水面上")

# 生成科幻场景
result = await generate_image("未来科技城市，高耸入云的摩天大楼，飞行汽车穿梭其中")
```

## 图像参数

默认配置：
- 模型：`glm-image`
- 尺寸：`1280x1280`
- 质量：`hd`（高清）

这些参数已设置为默认值，无需额外配置。

## 输出

### 容器环境

在 Docker 容器环境中：
- **保存位置**：宿主机 `workspace/agent_files/{agent_name}/work_files/{task_id}/tmp/`
- **返回路径**：容器内路径 `~/current_task/tmp/{filename}`
- Agent 可以通过 `~/current_task/tmp/` 访问生成的图片

### 非容器环境

在非 Docker 环境中：
- **保存位置**：`~/current_task/tmp/`
- **返回路径**：`~/current_task/tmp/{filename}`

### 文件命名

- 文件名格式：`glm_image_YYYYMMDD_HHMMSS.png`
- 返回值：容器内路径（如 `~/current_task/tmp/glm_image_20260414_091345.png`）

## 错误处理

如果 API 调用失败，action 会抛出异常：

- `ValueError`: 未设置 `GLM_API_KEY` 环境变量
- `RuntimeError`: API 调用失败或响应格式错误

## API 限制

根据智谱 AI 的文档：
- 图片链接有效期为 30 天
- 建议及时转存生成的图片

## 测试

运行示例：

```bash
cd /Users/dkt/myprojects/agentmatrix
python3 -m src.agentmatrix.skills.glm_image.example
```

## 技术细节

- 异步 HTTP 请求使用 `aiohttp`
- 图片下载使用流式传输
- 支持大文件下载

## 参考文档

- [智谱 AI 图像生成 API](https://open.bigmodel.cn/dev/api#aigc_image)
- [GLM-Image 模型介绍](https://docs.bigmodel.cn/cn/guide/models/image-generation/glm-image)
