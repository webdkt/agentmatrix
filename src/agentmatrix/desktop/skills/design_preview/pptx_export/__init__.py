"""
pptx_export — gen-pptx 的 Python 移植。

替代外部的 Node CLI（baoyu-design/.../gen-pptx/dist/cli.mjs）：
- Playwright（Python 版）+ 共享 _PlaywrightManager 的 browser
- python-pptx 生成 .pptx（含 lxml 直写 OOXML 处理 python-pptx 不支持的渐变/alpha/阴影/裁剪）
- 浏览器端 capture 脚本（assets/capture.iife.js）从原项目预构建并 commit

入口：exporter.export_pptx(url, config, out_dir) → dict
"""

from .exporter import export_pptx

__all__ = ["export_pptx"]
