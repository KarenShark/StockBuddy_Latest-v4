#!/bin/bash

# 启动 StockBuddy CLI 的便捷脚本

# 获取脚本所在目录并进入项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 初始化 conda
source /opt/anaconda3/etc/profile.d/conda.sh

# 检查 stockbuddy 环境是否存在，如果不存在则创建
if conda env list | grep -q "^stockbuddy "; then
    echo "✓ conda 环境 'stockbuddy' 已存在"
else
    echo "❌ conda 环境 'stockbuddy' 不存在"
    echo "正在创建 conda 环境..."
    conda create -n stockbuddy python=3.10 -y
    echo "✅ conda 环境创建完成"
    echo "正在安装依赖（这可能需要几分钟）..."
    conda run -n stockbuddy pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败，请检查错误信息"
        exit 1
    fi
    echo "✅ 依赖安装完成"
fi

# 验证环境并安装项目
echo "检查环境..."
conda run -n stockbuddy bash -c "cd '$SCRIPT_DIR' && python -c 'from stockbuddy.graph.trading_graph import StockBuddyGraph'" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 项目未正确安装，正在重新安装..."
    conda run -n stockbuddy bash -c "cd '$SCRIPT_DIR' && pip install -e ."
    if [ $? -ne 0 ]; then
        echo "❌ 项目安装失败，请检查错误信息"
        exit 1
    fi
    echo "✅ 安装完成"
fi

# 激活环境并运行 CLI（使用exec确保交互式输入正常工作）
echo "启动 StockBuddy CLI..."
eval "$(conda shell.bash hook)"
conda activate stockbuddy
exec python cli/main.py
