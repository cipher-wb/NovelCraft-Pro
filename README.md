# NovelCraft Pro

NovelCraft Pro 是一个面向中文网文长篇创作的人机协同系统。本仓库当前只实现 Phase 1 最小可运行骨架，用于验证项目初始化、立项顾问 mock 流程、基础 API 与本地工作台占位页。

## 当前范围

- FastAPI 入口与基础 API
- 项目目录骨架初始化
- 文件系统 + SQLite 最小持久化
- consultant mock 会话与结构化立项档案输出
- 极简 studio 占位页
- 单元测试与集成测试

未实现内容：Bible、Planner、Generation、Checks 的真实业务逻辑，Chroma 仅 stub，LLM 仅保留 mock 与 OpenAI-compatible 抽象。

## 环境要求

- Python 3.11 - 3.14
- Pydantic v2

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## 启动

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

启动后访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/studio`

## 测试

```powershell
python -m pytest -q
```

## 冒烟验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

## 目录

```text
backend/app/
  api/           FastAPI 路由
  core/          配置、路径、依赖注入
  domain/models/ Pydantic v2 数据模型
  infra/         SQLite、LLM、Vector stub
  repositories/  文件、SQLite、Vector 仓储
  schemas/       API 请求响应模型
  services/      bootstrap/project/consultant 服务
  static/studio/ 本地占位页
projects/        项目目录根
scripts/         启动与冒烟脚本
tests/           单元与集成测试
```
