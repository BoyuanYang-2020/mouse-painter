#!/bin/bash
# 打包 Mouse Painter 为独立 .app（macOS）
# 运行前确保已安装依赖：pip install pyinstaller pynput Pillow

set -e

echo "📦 安装 PyInstaller..."
pip install pyinstaller --quiet

echo "🔨 打包中..."
pyinstaller \
    --onefile \
    --windowed \
    --name "MousePainter" \
    --clean \
    main.py

echo ""
echo "✅ 完成！"
echo "   macOS App:  dist/MousePainter  (双击即可运行)"
echo ""
echo "发给朋友时，把 dist/MousePainter 文件发过去就可以了。"
echo "朋友如果遇到「无法打开」提示，让他们："
echo "  系统设置 → 隐私与安全性 → 点「仍要打开」"
