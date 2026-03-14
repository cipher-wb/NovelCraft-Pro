# NovelCraft Pro

当前稳定阶段 = Phase 11（Release Hardening / Pre-Ship Cleanup Minimal Chain）

NovelCraft Pro 是一个面向中文长篇网文创作的人机协同系统。当前主线已经覆盖 consultant -> bible -> planner -> scene draft -> chapter / volume / book assembled/finalized -> export / rebuild / diagnostics / import / archive / backup，全链保持 deterministic / rule-based 优先，不引入新的智能写作模块。

## Quick Start

只保留最短成功路径：

1. 启动服务

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

2. 导入真实 sample package

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/projects/import-package" `
  -ContentType "application/json" `
  -Body '{"package_path":"examples/sample-project-package","new_project_slug":"phase11-demo","mode":"create_new"}'
```

3. 打开 `/studio`

- `http://127.0.0.1:8000/studio`

4. 在 dashboard 里查看刚导入项目的 `Health`

5. 在 dashboard 上触发：

- `Export Project Package`
- `Create Archive Snapshot`
- `Create Backup`

更细的逐步演示和预期结果见：

- `docs/demo-workflow.md`

## Demo / Release Docs

- `examples/sample-project-package/`
  - 一个真正可导入的 `project_package_v1`
  - 可直接走 `POST /api/projects/import-package`
- `docs/demo-workflow.md`
  - 与 sample package 强绑定的最小演示流程
- `docs/release-checklist.md`
  - 发布前检查清单
- `docs/releases/TEMPLATE.md`
  - 最小 release notes 模板

## 当前能力概览

已完成：

- Phase 1 最小可运行骨架
- Phase 2 Bible + Planner 结构化规划层
- Phase 3A Scene Draft Generation 最小主链
- Phase 3B Memory Ingest + Retrieval 最小链
- Phase 4 Deterministic Checks 最小链
- Phase 5A Targeted Rewrite / Repair 最小链
- Phase 5B Author Voice / Style Constraint 最小链
- Phase 6 Chapter Assembly / Chapter Finalization 最小链
- Phase 7 Volume Assembly / Arc Progression 最小链
- Phase 8A Book Assembly / Book Progression 最小链
- Phase 8B book summary retrieval 增强补丁
- Phase 9 Book-level Checks / Long-arc Continuity 最小链
- Phase 10A Studio / Export / Rebuild / Productization 最小链
- Phase 10B Export / Import / Archive / Backup 最小链
- Phase 11 Release Hardening / Pre-Ship Cleanup 最小链

当前仓库重点能力：

- consultant 会话与结构化立项档案
- Bible / Character / Planner 文档读写、confirm、stale 流转
- deterministic scene draft generation / checks / accept / targeted repair
- accepted draft 派生 memory 与 retrieval
- chapter / volume / book 组装、定稿、checks、continuity checks
- productization：
  - export / rebuild / diagnostics / health
  - project package / import-package
  - archive snapshot / backup / snapshots list
- `/studio` dashboard 与 scene / chapter / volume / book 页面最小工作流

## Productization / Studio

Phase 11 收口后，当前最接近交付的能力是：

- `/studio` dashboard
  - Load Health
  - Rebuild All / Memory / Chapters / Volumes / Book / Checks
  - Export Book
  - Export Project Package
  - Import Package
  - Create Archive Snapshot
  - Create Backup
  - Load Snapshots
- `/studio/scene.html`
  - `Export Scene`
- `/studio/chapter.html`
  - `Export Chapter`
- `/studio/volume.html`
  - `Export Volume`
- `/studio/book.html`
  - `Export Book`
  - continuity 区块

## 当前 API 概览

### Core Writing

- `POST /api/projects`
- `POST /api/projects/{project_id}/consultant/sessions`
- `POST /api/consultant/sessions/{session_id}/answer`
- `POST /api/consultant/sessions/{session_id}/finalize`
- `POST /api/projects/{project_id}/bible/from-consultant`
- `POST /api/projects/{project_id}/characters/confirm`
- `POST /api/projects/{project_id}/bible/world/confirm`
- `POST /api/projects/{project_id}/bible/power-system/confirm`
- `POST /api/projects/{project_id}/bible/story-bible/confirm`
- `POST /api/projects/{project_id}/plans/volumes/generate`
- `POST /api/projects/{project_id}/plans/master-outline/confirm`
- `POST /api/projects/{project_id}/plans/volumes/{volume_id}/confirm`
- `POST /api/projects/{project_id}/plans/volumes/{volume_id}/chapters/generate`
- `POST /api/projects/{project_id}/plans/chapters/{chapter_id}/confirm`
- `POST /api/projects/{project_id}/plans/chapters/{chapter_id}/scenes/generate`
- `POST /api/projects/{project_id}/plans/scenes/{scene_id}/confirm`
- `POST /api/projects/{project_id}/drafts/scenes/{scene_id}/generate`
- `POST /api/projects/{project_id}/drafts/{draft_id}/repair`
- `POST /api/projects/{project_id}/drafts/{draft_id}/accept`
- `POST /api/projects/{project_id}/drafts/{draft_id}/reject`
- `POST /api/projects/{project_id}/chapters/{chapter_id}/assemble`
- `POST /api/projects/{project_id}/chapters/{chapter_id}/finalize`
- `POST /api/projects/{project_id}/volumes/{volume_id}/assemble`
- `POST /api/projects/{project_id}/volumes/{volume_id}/finalize`
- `POST /api/projects/{project_id}/book/assemble`
- `POST /api/projects/{project_id}/book/finalize`
- `GET /api/projects/{project_id}/book/continuity-checks/latest`
- `POST /api/projects/{project_id}/book/continuity-checks/recheck`

### Productization

- `POST /api/projects/{project_id}/export`
  - 支持 `scene | chapter | volume | book | project`
- `POST /api/projects/{project_id}/rebuild`
- `GET /api/projects/{project_id}/diagnostics/health`
- `POST /api/projects/import-package`
- `POST /api/projects/{project_id}/archive-snapshot`
- `POST /api/projects/{project_id}/backup`
- `GET /api/projects/{project_id}/snapshots`

## 关键约束

- Python 版本范围：`>=3.11,<3.15`
- 仅使用 Pydantic v2
- checks / retrieval / continuity checks 保持 deterministic / rule-based
- style 仅做最小 author voice / constraint，不做 LLM critic
- import 当前只支持 `create_new`
- `project package` 固定 `package_version = project_package_v1`
- `markdown_package` 只用于阅读/交付，不是恢复核心依赖
- `/studio` dashboard 继续是同步工作台，不提供后台任务队列或自动运维

## 当前已知限制

- 不新增新的智能写作模块
- 不做 LLM critic
- 不做 book-level repair / rewrite / polish
- continuity 只做 deterministic / rule-based 最小链，不做复杂语义推理
- project package 当前只支持本地目录包，不做云同步
- import 不支持覆盖式 restore，不支持 partial import
- archive / backup 当前只做手动本地快照
- release hardening 只收口 productization / dashboard 直连边界，不做全项目错误协议重构

## 环境要求

- Python 3.11 - 3.14
- Pydantic v2

## 启动与测试

启动：

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

或：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

测试：

```powershell
python -m pytest -q
```

冒烟：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

发布前只读检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_preflight.ps1
```

## 目录

```text
backend/app/
  api/                 FastAPI 路由
  core/                配置、路径、依赖注入
  domain/models/       Pydantic v2 数据模型
  repositories/        文件、SQLite 仓储
  schemas/             API 请求响应模型
  services/            consultant/bible/planner/draft/memory/retrieval/checks/repair/style/chapter/volume/book/productization 服务
  static/studio/       studio 页面
docs/                  demo workflow、release checklist、release notes template
examples/              可导入 sample package
projects/              运行时项目目录根
scripts/               dev / smoke / release_preflight 脚本
tests/                 单元与集成测试
```
