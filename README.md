# NovelCraft Pro

NovelCraft Pro 是一个面向中文网文长篇创作的人机协同系统。当前仓库已完成：

- Phase 1 最小可运行骨架
- Phase 2 Bible + Planner 结构化规划层
- Phase 2.5 设计对齐与验收修补

当前实现重点是结构化立项、Bible 文档管理、规则化 Planner 脚手架生成，以及对应的 API 与测试。

## 当前范围

已实现：

- FastAPI 入口与基础 API
- 项目目录骨架初始化
- 文件系统 + SQLite 最小持久化
- consultant mock 会话与结构化立项档案输出
- Bible 文档层
  - `story_bible.json`
  - `characters.json`
  - `world.json`
  - `power_system.json`
- Planner 文档层
  - `master_outline.json`
  - `volume/chapter/scene` 计划文件
- Bible / Character / Planner 的读写、confirm、stale 流转
- 规则化 scaffold generation
  - volume generate
  - chapter generate
  - scene generate
- 极简 studio 占位页
- 单元测试、集成测试、GitHub Actions CI

## Phase 2 API 概览

Bible:

- `GET /api/projects/{project_id}/bible`
- `POST /api/projects/{project_id}/bible/from-consultant`
- `GET|PUT|PATCH|POST confirm /api/projects/{project_id}/bible/story-bible`
- `GET|PUT|PATCH|POST confirm /api/projects/{project_id}/bible/world`
- `GET|PUT|PATCH|POST confirm /api/projects/{project_id}/bible/power-system`
- `GET|POST|GET item|PUT item|PATCH item|DELETE item|POST confirm /api/projects/{project_id}/characters`

Planner:

- `GET /api/projects/{project_id}/plans/master-outline`
- `POST /api/projects/{project_id}/plans/master-outline/confirm`
- `POST /api/projects/{project_id}/plans/volumes/generate`
- `GET /api/projects/{project_id}/plans/volumes`
- `GET|PUT|PATCH|POST confirm /api/projects/{project_id}/plans/volumes/{volume_id}`
- `POST /api/projects/{project_id}/plans/volumes/{volume_id}/chapters/generate`
- `GET /api/projects/{project_id}/plans/volumes/{volume_id}/chapters`
- `GET|PUT|PATCH|POST confirm /api/projects/{project_id}/plans/chapters/{chapter_id}`
- `POST /api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate`
- `GET /api/projects/{project_id}/plans/chapters/{chapter_id}/scenes`
- `GET|PUT|PATCH|POST confirm /api/projects/{project_id}/plans/scenes/{scene_id}`

## 关键约束

- Python 版本范围：`>=3.11,<3.15`
- 仅使用 Pydantic v2
- `volume_no` 在项目内唯一
- `chapter_no` 在项目内唯一
- `scene_no` 在同一 chapter 内唯一
- 任一 CharacterCard 的增删改都会使 `characters.json.status = draft`
- 删除被结构化 Story/Plan 引用的角色会返回 `409`
- 所有 generate 接口默认 `overwrite=false`，目标文件已存在时返回 `409`
- `master_outline.json` 读兼容旧字段 `status`，写统一使用 `outline_status`
- Planner 的 generate 是 rule-based scaffold generation，不调用 LLM，不生成正文

## 当前已知限制

- 无正文生成
- 无 memory 真检索
- 无 checks 真校验
- stale 只做结构化传播，不做自动重建
- generate 只产出结构化规划脚手架，不产出章节正文或场景正文
- 编号变更当前仅在服务层支持，公开 API 暂不开放 `volume_no/chapter_no/scene_no` 编辑
- Chroma 仍是 stub，没有接入实际向量库

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
  services/      bootstrap/project/consultant/bible/planner 服务
  static/studio/ 本地占位页
projects/        项目目录根
actions/         GitHub Actions 工作流
tests/           单元与集成测试
```
