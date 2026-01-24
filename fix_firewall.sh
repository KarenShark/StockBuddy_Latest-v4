#!/bin/bash

echo "================================================"
echo "  🔥 修复 macOS 防火墙设置"
echo "================================================"
echo ""

# 检查防火墙状态
echo "1. 当前防火墙状态："
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
echo ""

# 查找 Python 路径
PYTHON_PATH=$(which python)
PYTHON3_PATH="/opt/anaconda3/bin/python"

echo "2. Python 路径："
echo "   - python: $PYTHON_PATH"
echo "   - anaconda: $PYTHON3_PATH"
echo ""

echo "3. 添加 Python 到防火墙允许列表："
echo "   需要管理员权限（会要求输入密码）"
echo ""

# 添加 Python 到防火墙
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add "$PYTHON3_PATH"
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblock "$PYTHON3_PATH"

echo ""
echo "✅ 完成！Python 已添加到防火墙允许列表"
echo ""
echo "================================================"
echo "  📱 下一步："
echo "================================================"
echo "1. 确保手机和电脑在同一 WiFi"
echo "2. 重新在手机上测试 API 连接"
echo "3. 如果还有问题，尝试：" 
echo "   - 系统设置 > 网络 > 防火墙 > 选项"
echo "   - 手动添加 Python 并允许传入连接"
echo ""
