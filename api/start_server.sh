#!/bin/bash

echo "========================================="
echo "   StockBuddy API Server Launcher    "
echo "========================================="
echo ""

# 检查是否安装了 Python
if ! command -v python3 &> /dev/null
then
    echo "❌ Python 3 未安装，请先安装 Python 3"
    exit 1
fi

# 检查是否安装了依赖
echo "📦 检查依赖..."
if [ ! -d "../venv" ] && [ ! -d "venv" ]; then
    echo "⚠️  建议创建虚拟环境："
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo ""
fi

echo "📦 安装依赖..."
pip install -r requirements.txt

echo ""
echo "🚀 启动 API 服务器..."
echo ""

python main.py
