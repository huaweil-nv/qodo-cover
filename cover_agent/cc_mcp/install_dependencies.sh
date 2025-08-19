#!/bin/bash

# Cover Agent MCP Server 依赖安装脚本

echo "🚀 安装 Cover Agent MCP Server 依赖..."

# 检查Python版本
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
echo "📋 Python版本: $python_version"

# 安装MCP库
echo "📦 安装MCP库..."
pip install mcp

# 安装Cover Agent核心依赖
echo "📦 安装Cover Agent依赖..."
pip install jedi-language-server
pip install grep-ast
pip install tree-sitter-languages
pip install litellm
pip install tenacity
pip install wandb
pip install dynaconf

# 安装测试相关依赖
echo "📦 安装测试依赖..."
pip install pytest
pip install pytest-cov

# 安装其他可能需要的依赖
echo "📦 安装其他依赖..."
pip install pydantic
pip install anyio
pip install httpx

echo "✅ 依赖安装完成！"
echo ""
echo "🎯 下一步："
echo "1. 配置Cursor: 创建 .cursor/settings.json"
echo "2. 启动服务器: python -m cover_agent.mcp.hybrid_server"
echo "3. 在Cursor中使用MCP工具"
