# D2 主题系统完整指南

D2 提供 20 种内置主题（18 亮色 + 2 暗色），包含完整颜色配置。

## 快速参考

| ID | 主题 | 主色 | 强调色 | 用途 |
|----|------|------|--------|------|
| 0 | Neutral Default | 蓝系 | 蓝 | 通用 |
| 1 | Neutral Grey | 灰系 | 灰 | 商务 |
| 3 | Flagship Terrastruct | 蓝紫 | 紫青 | 演示 |
| 4 | Cool Classics | 蓝系 | 青绿 | 文档 |
| 5 | Mixed Berry Blue | 蓝紫 | 紫粉 | 现代 |
| 6 | Grape Soda | 紫系 | 蓝粉 | 活泼 |
| 7 | Aubergine | 深紫 | 蓝青 | 专业 |
| 8 | Colorblind Clear | 蓝系 | 绿黄 | 无障碍 |
| 100 | Vanilla Nitro Cola | 棕系 | 橙蓝 | 清新 |
| 101 | Orange Creamsicle | 橙系 | 绿黄 | 温暖 |
| 102 | Shirley Temple | 粉系 | 橙黄 | 可爱 |
| 103 | Earth Tones | 棕系 | 橙黄 | 自然 |
| 104 | Everglade Green | 绿系 | 橙棕 | 护眼 |
| 105 | Buttered Toast | 黄棕 | 橙黄 | 温暖 |
| 300 | Terminal | 黑蓝 | 绿黄 | 代码 |
| 301 | Terminal Grayscale | 黑白 | 灰 | 打印 |
| 302 | Origami | 红棕 | 蓝粉 | 艺术 |
| 303 | C4 | 多色 | 多色 | 架构 |
| 200 | Dark Mauve | 深紫 | 粉红 | 护眼 |
| 201 | Dark Flagship | 深蓝 | 紫色 | 暗色 |

## 完整颜色配置

格式：`B1-B6` (主色渐变), `AA2,AA4,AA5` (强调色), `AB4,AB5` (辅助色)

---

### 亮色主题

#### 0. Neutral Default
```
B: #0D32B2 #0D32B2 #E3E9FD #E3E9FD #EDF0FD #F7F8FE
AA: #4A6FF3 #EDF0FD #F7F8FE
AB: #EDF0FD #F7F8FE
```

#### 1. Neutral Grey
```
B: #0A0F25 #676C7E #9499AB #CFD2DD #DEE1EB #EEF1F8
AA: #676C7E #CFD2DD #DEE1EB
AB: #CFD2DD #DEE1EB
```

#### 3. Flagship Terrastruct
```
B: #000E3D #234CDA #6B8AFB #A6B8F8 #D2DBFD #E7EAFF
AA: #5829DC #B4AEF8 #E4DBFF
AB: #7FDBF8 #C3F0FF
```

#### 4. Cool Classics
```
B: #000536 #0F66B7 #4393DD #87BFF3 #BCDDFB #E5F3FF
AA: #076F6F #77DEDE #C3F8F8
AB: #C1A2F3 #DACEFB
```

#### 5. Mixed Berry Blue
```
B: #000536 #0F66B7 #4393DD #87BFF3 #BCDDFB #E5F3FF
AA: #7639C5 #C1A2F3 #DACEFB
AB: #EA99C6 #FFDEF1
```

#### 6. Grape Soda
```
B: #170034 #7639C5 #8F70D1 #C1A2F3 #DACEFB #F2EDFF
AA: #0F66B7 #87BFF3 #BCDDFB
AB: #EA99C6 #FFDAEF
```

#### 7. Aubergine
```
B: #170034 #7639C5 #8F70D1 #D0B9F5 #E7DEFF #F4F0FF
AA: #0F66B7 #87BFF3 #BCDDFB
AB: #92E3E3 #D7F5F5
```

#### 8. Colorblind Clear
```
B: #010E31 #173688 #5679D4 #84A1EC #C8D6F9 #E5EDFF
AA: #048E63 #A6E2D0 #CAF2E6
AB: #FFDA90 #FFF0D1
```

#### 100. Vanilla Nitro Cola
```
B: #1E1303 #55452F #9A876C #C9B9A1 #E9DBCA #FAF1E6
AA: #D35F0A #FABA8A #FFE0C7
AB: #84A1EC #D5E0FD
```

#### 101. Orange Creamsicle
```
B: #311602 #D35F0A #F18F47 #FABA8A #FFE0C7 #FFF6EF
AA: #13A477 #A6E2D0 #CAF2E6
AB: #FEEC8C #FFF8CF
```

#### 102. Shirley Temple
```
B: #31021D #9B1A48 #D2517F #EA99B6 #FFDAE7 #FCEDF2
AA: #D35F0A #FABA8A #FFE0C7
AB: #FFE767 #FFF2AA
```

#### 103. Earth Tones
```
B: #1E1303 #55452F #9A876C #C9B9A1 #E9DBCA #FAF1E6
AA: #D35F0A #FABA8A #FFE0C7
AB: #FFE767 #FFF2AA
```

#### 104. Everglade Green
```
B: #023324 #048E63 #49BC99 #A6E2D0 #CAF2E6 #EBFDF7
AA: #D35F0A #FABA8A #FFE0C7
AB: #C9B9A1 #E9DBCA
```

#### 105. Buttered Toast
```
B: #312102 #DF9C18 #FDC659 #FFDA90 #FFF0D1 #FFF7E7
AA: #55452F #C9B9A1 #E9DBCA
AB: #FABA8A #FFE0C7
```

#### 300. Terminal ⭐
```
B: #000410 #0000E4 #5AA4DC #E7E9EE #F5F6F9 #FFFFFF
AA: #008566 #45BBA5 #7ACCBD
AB: #F1C759 #F9E088
```
特点: 单色字体、直角、点状容器

#### 301. Terminal Grayscale
```
B: #000410 #000410 #FFFFFF #E7E9EE #F5F6F9 #FFFFFF
AA: #6D7284 #F5F6F9 #FFFFFF
AB: #F5F6F9 #FFFFFF
```

#### 302. Origami
```
B: #170206 #A62543 #E07088 #F3E0D2 #FAF1E6 #FFFBF8
AA: #0A4EA6 #3182CD #68A8E4
AB: #E07088 #F19CAE
```

#### 303. C4
```
B: #073b6f #08427b #3c7fc0 #438dd5 #8a8a8a #999999
```
专用于 C4 架构模型

---

### 暗色主题

#### 200. Dark Mauve
```
B: #CBA6f7 #CBA6f7 #6C7086 #585B70 #45475A #313244
AA: #f38ba8 #45475A #313244
AB: #45475A #313244
```

#### 201. Dark Flagship Terrastruct
```
B: #F4F6FA #6B8AFB #3733E9 #070B67 #0B1197 #3733E9
AA: #8B5DEE #4918B1 #7240DD
AB: #00607C #01799D
```

---

## 使用方法

### 命令行
```bash
d2 --theme 300 input.d2 output.svg
```

### 代码中
```d2
vars: {
  d2-config: {
    theme-id: 300
  }
}
```

## 颜色说明

- **B1-B6**: 主色渐变（从深到浅）
- **AA2**: 第一强调色
- **AA4**: 第二强调色
- **AA5**: 第三强调色
- **AB4**: 第一辅助色
- **AB5**: 第二辅助色

## 测试主题

```bash
# 批量生成对比
for t in 0 1 3 4 100 300 301; do
  d2 --theme $t input.d2 "theme-$t.svg"
done
```

## 相关文档

- [SYNTAX.md](./SYNTAX.md) - 完整语法参考
- [EXAMPLES.md](./EXAMPLES.md) - 示例集合
