

# 程序化图表生成指南 (D2 to PPT)

## 一、 核心工作流与环境设定

我们的目标是通过纯脚本，将开发人员编写的 `.d2` 文件批量转换为 SVG，并自动嵌入 PPT。

### 1. 工具链依赖
- **D2 CLI:** 用于将文本编译为 SVG。
- **Python:** 作为胶水语言，调用 D2 CLI 并处理 PPT。
- **python-pptx:** Python 库，用于自动化生成和排版 PPT。

### 2. 标准编译命令
在脚本中，应始终使用以下参数调用 D2：
```bash
# --layout=tali: 使用为架构图优化的布局引擎（线条呈 90 度折角）
# --theme=104: 使用适合商务 PPT 的高对比度蓝色系主题 (Flagship)
# --pad=50: 为图片四周留出白边，防止导入 PPT 时贴边
d2 --layout=tali --theme=104 --pad=50 input.d2 output.svg
```

---

## 二、 场景化设计指引 (何时用何种写法)

为了适配 PPT 宽屏 (16:9) 的特点，我们需要针对不同图表采用特定的 D2 语法。

### 场景一：业务流程图 (Flowchart)
**目标：** 展现清晰的步骤、判定和分支。
**排版法则：** PPT 页面宽而扁，流程图必须横向延伸。

**D2 语法规范：**
```d2
# 强制从左到右布局，适配 PPT 宽屏
direction: right

# 1. 定义节点并指定形状
用户发起支付: { shape: person }
检查余额: { shape: diamond }  # 菱形用于判断
扣款服务: { shape: step }     # step 形状适合表示动作
生成凭证: { shape: document }

# 2. 建立连接与分支
用户发起支付 -> 检查余额: 调用 API

# 使用靠近线段两端的 label
检查余额 -> 扣款服务: 余额充足 {
  style.stroke: green
}

检查余额 -> 充值页面: 余额不足 {
  style.stroke: red
  style.stroke-dash: 5  # 虚线表示异常或次要流程
}

扣款服务 -> 生成凭证: 成功
```

### 场景二：系统架构图 (Architecture Diagram)
**目标：** 展现系统的物理/逻辑层级、网络边界（VPC、可用区）、容器与组件。
**排版法则：** 利用“嵌套容器”和“网格布局 (Grid)”强制对齐，使得图表看起来像人工精心排列的。

**D2 语法规范：**
```d2
direction: right

# 使用内置图标增强 PPT 的视觉表现力
# D2 原生支持直接调用常见 icon
Client: { shape: person; icon: github }

# 使用嵌套表示边界，加上明确的 label
AWS Region (ap-northeast-1): {
  # 关键：使用 grid 布局，强制内部组件整齐排列为 2 列
  grid-columns: 2
  
  VPC 内部网络: {
    # 容器也可以设置样式
    style: { fill: transparent; stroke: blue; stroke-dash: 5 }
    
    API Gateway: { shape: queue }
    Auth Service: { shape: component }
    Order Service: { shape: component }
  }

  Database Zone: {
    Primary DB: { shape: cylinder; icon: postgresql }
    Replica DB: { shape: cylinder; icon: postgresql }
  }
}

# 跨边界连接
Client -> AWS Region (ap-northeast-1).VPC 内部网络.API Gateway: HTTPS
```

### 场景三：实体关系图 / 数据库模型 (ER Diagram)
**目标：** 展示数据库表结构、外键关联。
**排版法则：** 使用 D2 原生的 `sql_table` 形状，让表结构一目了然。

**D2 语法规范：**
```d2
direction: right

Users: {
  shape: sql_table
  id: uuid { constraint: primary_key }
  username: varchar(50) { constraint: unique }
  created_at: timestamp
}

Orders: {
  shape: sql_table
  id: uuid { constraint: primary_key }
  user_id: uuid { constraint: foreign_key }
  amount: decimal
}

# 关联线
Users.id -> Orders.user_id: 1 to N
```

---

## 三、 生手必备：常见难题与 D2 解决手册

对于刚接触 D2 的开发人员，遇到排版不符预期时，请参照以下规则调整。

### 难题 1：连接线互相交叉，图表像一团乱麻
**解决方案：**
1. **模块化：** 把相关的节点放进一个容器 `{}` 里。D2 引擎会优先计算容器内的布局，再计算容器间的连线，从而大幅减少交叉。
2. **隐形连接线 (Invisible Links)：** 如果需要强制 A 在 B 上面，但它们之间没有业务连线，可以使用不可见的线来引导布局引擎：
   ```d2
   A -> B: { style.stroke: transparent; style.animated: false }
   ```

### 难题 2：我想在图表的任意空白处加一段文字（自由 Text 内嵌）
PPT 中经常需要“旁白”或“标注”。在 D2 中，通过 `shape: text` 和 `near` 属性可以实现极其精准的自由浮动文字。

**解决方案：**
```d2
A -> B

# 1. 定义一个纯文本节点，无背景无边框
Annotation: "⚠️ 注意：这里的 QPS 峰值可能达到 10w+" {
  shape: text
  style: { font-color: "#D32F2F"; bold: true }
}

# 2. 将这段文字强行停靠在 B 节点的右上角
Annotation.near: B.top-right
```

### 难题 3：如何控制连接线上文字（Label）的具体位置？
有时线很长，默认把字放中间会挡住其他东西。

**解决方案：** 使用 `near` 调整线上文本位置。`0` 代表起点，`1` 代表终点。
```d2
ServiceA -> ServiceB: 异步消息 {
  near: 0.1  # 字靠靠近 ServiceA
}
ServiceB -> ServiceC: 写入 DB {
  near: 0.9  # 字靠近 ServiceC
}
```

---

## 四、 样式标准化规范 (为 PPT 护航)

为确保生成的图表在 PPT 中风格统一（例如都符合公司的 UI 规范），**严禁开发人员在节点中随意硬编码颜色 (Hardcode Colors)**。

### 规则：必须使用全局 Classes
所有的 `.d2` 文件顶部，必须引入或定义标准类。自动化脚本在合并时，可以统一向文件头部注入这些规范。

```d2
# 全局样式规范定义区
classes: {
  # 核心服务：深蓝色背景，白字
  core_service: {
    style: { fill: "#1565C0"; font-color: "#FFFFFF"; border-radius: 8 }
  }
  # 第三方依赖：灰色背景，虚线
  external: {
    style: { fill: "#F5F5F5"; stroke-dash: 5; font-color: "#666666" }
  }
  # 高亮告警节点
  alert: {
    style: { fill: "#FFEBEE"; stroke: "#C62828"; stroke-width: 2 }
  }
}

# 实际使用区（开发者只允许引用 class）
订单中心: { class: core_service }
微信支付接口: { class: external }
风控拦截器: { class: alert }

订单中心 -> 微信支付接口
订单中心 -> 风控拦截器
```

---

## 五、 自动化脚本演示 (Pipeline 示例)

以下是一个典型的 Python 脚本逻辑，它展现了如何在没有 GUI 的环境下，将目录下的 `.d2` 批量转化为 PPT。

```python
import os
import subprocess
from pptx import Presentation
from pptx.util import Inches

D2_SRC_DIR = "./architecture_docs"
OUTPUT_PPT = "./Architecture_Review.pptx"

def compile_d2_to_svg(d2_file_path, svg_out_path):
    """调用 D2 CLI 将文本编译为 SVG"""
    cmd = [
        "d2",
        "--layout=tali",   # 架构图正交线条布局
        "--theme=104",     # 商务蓝底主题
        "--pad=30",        # 边缘留白
        d2_file_path,
        svg_out_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Compiled: {d2_file_path} -> {svg_out_path}")

def create_ppt_from_svgs(svg_dir):
    """将所有生成的 SVG 插入到 PPT 中"""
    prs = Presentation()
    
    # 设置为 16:9 比例 (10 x 5.625 英寸)
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)
    
    blank_slide_layout = prs.slide_layouts[6]

    for filename in os.listdir(svg_dir):
        if filename.endswith(".svg"):
            slide = prs.slides.add_slide(blank_slide_layout)
            svg_path = os.path.join(svg_dir, filename)
            
            # 在幻灯片中心插入 SVG 
            # (通常插入后留有一定的边距，PPT 最新版原生支持 SVG 渲染)
            pic = slide.shapes.add_picture(
                svg_path, 
                left=Inches(0.5), 
                top=Inches(0.5), 
                width=Inches(9) # 自动保持宽高比缩放
            )
            print(f"Added slide for {filename}")
            
    prs.save(OUTPUT_PPT)
    print(f"PPT successfully generated at: {OUTPUT_PPT}")

if __name__ == "__main__":
    # 1. 编译目录下所有 .d2 文件
    for file in os.listdir(D2_SRC_DIR):
        if file.endswith(".d2"):
            in_path = os.path.join(D2_SRC_DIR, file)
            out_path = os.path.join(D2_SRC_DIR, file.replace(".d2", ".svg"))
            compile_d2_to_svg(in_path, out_path)
    
    # 2. 打包生成 PPT
    create_ppt_from_svgs(D2_SRC_DIR)
```

## 六、 开发者自检清单 (Checklist)

提交 `.d2` 代码前，开发者应自我检查：
1. [ ] **排版方向：** 是否包含 `direction: right` 以适配 PPT 的宽屏显示？
2. [ ] **样式合规：** 是否全量使用了预定义的 `classes`，而非直接在节点里写颜色代码？
3. [ ] **物理分组：** 节点数量超过 10 个时，是否使用了 `{ }` 容器对逻辑模块进行了合理的分区？
4. [ ] **避免飞线：** 是否使用了 `near` 属性将长连线上的文本固定在不遮挡阅读的位置？
5. [ ] **旁白备注：** 核心的架构抉择，是否通过 `shape: text` 的形式以内嵌标注（Annotation）展现在了图表留白处？