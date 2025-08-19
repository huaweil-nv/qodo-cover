# Cover Agent MCP Server

Cover Agent的MCP服务器，为Cursor提供代码分析和测试生成上下文。

## 🚀 快速开始

### 1. 安装依赖

```bash
# 方法1: 一键安装 (推荐)
./cover_agent/mcp/install_dependencies.sh

# 方法2: 手动安装
pip install mcp jedi-language-server grep-ast tree-sitter-languages litellm tenacity wandb dynaconf pytest pytest-cov
```

### 2. 配置Cursor

```bash
# 创建配置目录
mkdir -p .cursor

# 复制配置模板 (或手动创建)
cp cover_agent/mcp/cursor_config.json .cursor/settings.json
```

或手动创建 `.cursor/settings.json`：

```json
{
  "mcpServers": {
    "cover-agent": {
      "command": "python",
      "args": ["-m", "cover_agent.mcp.hybrid_server"],
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

### 3. 启动服务器

```bash
python -m cover_agent.mcp.hybrid_server
```

## 📋 在Cursor中使用

### 基本用法

在Cursor的AI聊天中使用以下格式：

```
请分析我的calculator模块并提供测试生成上下文。

源文件: src/calculator.py
测试文件: tests/test_calculator.py  
项目根目录: /path/to/my/project
```

### 使用示例

#### 1. 代码结构分析
```
请分析我的calculator模块的代码结构，包括类、函数和依赖关系。

源文件: src/calculator.py
项目根目录: /path/to/my/project
```

#### 2. 覆盖率缺口分析
```
请分析我的calculator模块的覆盖率缺口，找出需要测试的关键代码行。

源文件: src/calculator.py
测试文件: tests/test_calculator.py
项目根目录: /path/to/my/project
```

#### 3. 测试生成上下文
```
请为我的calculator模块提供完整的测试生成上下文。

源文件: src/calculator.py
测试文件: tests/test_calculator.py
项目根目录: /path/to/my/project
```

## 🛠️ 可用工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `analyze_code_context` | 代码结构分析 | source_file, project_root |
| `get_coverage_gaps` | 覆盖率缺口分析 | source_file, test_file, project_root |
| `analyze_test_structure` | 测试结构分析 | test_file, project_root |
| `get_test_generation_context` | 测试生成上下文 | source_file, test_file, project_root |
| `validate_test_coverage` | 覆盖率验证 | source_file, test_file, project_root |

## 🎯 工作流程

1. **代码分析** → Cover Agent提供LSP分析  
2. **覆盖率分析** → 识别未覆盖的代码行  
3. **测试生成** → Cursor内置模型基于上下文生成测试  
4. **验证改进** → Cover Agent验证覆盖率提升

## ✨ 核心优势

- ✅ **无外部API依赖** - 使用Cursor内置模型，无需额外费用
- ✅ **强大的分析能力** - 利用Cover Agent的LSP和覆盖率分析
- ✅ **智能上下文提供** - 为测试生成提供丰富上下文
- ✅ **覆盖率优化** - 自动识别和填补测试缺口

## 🔧 故障排除

### 常见问题

1. **ModuleNotFoundError: No module named 'mcp'**
   ```bash
   pip install mcp
   ```

2. **ModuleNotFoundError: No module named 'jedi'**
   ```bash
   pip install jedi-language-server
   ```

3. **Coverage report not found**
   ```bash
   pip install pytest-cov
   pytest --cov=. --cov-report=xml
   ```

4. **依赖冲突**
   ```bash
   # 使用虚拟环境
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # venv\Scripts\activate   # Windows
   ./cover_agent/mcp/install_dependencies.sh
   ```

### 调试模式

```bash
export COVER_AGENT_DEBUG=1
export MCP_DEBUG=1
python -m cover_agent.mcp.hybrid_server
```

## 📊 最佳实践

### 项目结构建议
```
your_project/
├── src/
│   └── your_module.py          # 源代码
├── tests/
│   └── test_your_module.py     # 测试文件
├── .cursor/
│   └── settings.json           # Cursor MCP配置
└── pytest.ini                  # 测试配置
```

### 测试配置 (pytest.ini)
```ini
[tool:pytest]
addopts = --cov=. --cov-report=xml --cov-report=term
testpaths = tests
```

## 📁 文件结构

```
cover_agent/mcp/
├── __init__.py                 # 包初始化
├── hybrid_server.py            # MCP服务器实现
├── hybrid_config.json          # 服务器配置
├── cursor_config.json          # Cursor配置模板
├── install_dependencies.sh     # 依赖安装脚本
└── README.md                  # 本文档
```

---

**享受Cover Agent + Cursor的强大组合！** 🚀

> 💡 **提示**: 首次使用建议先用 `analyze_code_context` 了解代码结构，再用 `get_test_generation_context` 获取完整上下文进行测试生成。
