@echo off
REM 打包 Mouse Painter 为独立 .exe（Windows）
REM 运行前确保已安装依赖：pip install pyinstaller pynput Pillow

echo 安装 PyInstaller...
pip install pyinstaller --quiet

echo 打包中...
pyinstaller --onefile --windowed --name "MousePainter" --clean main.py

echo.
echo 完成！
echo    Windows EXE:  dist\MousePainter.exe
echo.
echo 把 dist\MousePainter.exe 发给朋友即可直接运行。
pause
