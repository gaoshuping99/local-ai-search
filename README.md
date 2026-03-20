# Local AI Search

> 本地知识库 AI 搜索，支持 200GB+ 文件的全文检索和自然语言查询

[![Skill](https://img.shields.io/badge/Skill-Local%20AI%20Search-blue)](https://github.com/khoj-ai/khoj)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 触发条件

**当用户说以下内容时，调用此 Skill：**
- "帮我在本地搜索..."
- "帮我在本电脑搜索..."
- "帮我在某个文件夹中搜索..."
- "搜索本地文件..."
- "搜索我的文档..."
- 或任何涉及**本地/本机/文件夹内容检索**的请求

## 快速开始

### 安装

```bash
# 安装依赖
pip install khoj "markitdown[xlsx,pptx]"

# 配置 API Key
export OPENAI_API_KEY="your-api-key"
# 或 DeepSeek
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
```

### 使用

```bash
# 启动服务
local-ai-search start

# 转换文档
local-ai-search convert ~/Documents/source -o ~/Documents/converted

# 索引到知识库
local-ai-search index ~/Documents/converted

# 查询
local-ai-search query "第三季度销售数据"
```

## 特性

- ✅ 支持 200GB+ 大规模文件
- ✅ 支持 xlsx, pptx, pdf, docx, md 等格式
- ✅ 自然语言查询
- ✅ 云端 LLM API（无需本地大模型）
- ✅ 精确定位到源文件位置
- ✅ 轻量级部署（16GB RAM 友好）
- ✅ 内存占用仅 ~70MB

## 文件结构

```
~/.agents/skills/local-ai-search/
├── SKILL.md              # 完整文档
├── khoj_cli.py           # CLI 工具
├── config.yaml           # 配置文件
├── requirements.txt      # 依赖
└── scripts/
    ├── start_server.sh   # 启动脚本
    ├── convert.py        # 转换脚本
    └── query.py          # 查询脚本
```

## 系统要求

- Python 3.10+
- 8GB+ 可用内存
- 足够的磁盘空间（文档大小的 25-40%）

## 文档

完整文档请参阅 [SKILL.md](SKILL.md)

## 许可证

MIT License