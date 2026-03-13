# NovelCraft Pro

当前稳定阶段 = Phase 5B（Author Voice / Style Constraint Minimal Chain）

NovelCraft Pro 是一个面向中文网文长篇创作的人机协同系统。当前仓库已完成：

- Phase 1 最小可运行骨架
- Phase 2 Bible + Planner 结构化规划层
- Phase 2.5 设计对齐与验收修补
- Phase 3A Scene Draft Generation 最小主链
- Phase 3B Memory Ingest + Retrieval 最小链
- Phase 4 Deterministic Checks 最小链
- Phase 5A Targeted Rewrite / Repair 最小链
- Phase 5B Author Voice / Style Constraint 最小链

当前实现重点是：结构化立项、Bible 文档管理、规则化 Planner 脚手架生成、Scene Draft 最小生成链、accepted draft 的结构化 memory 派生沉淀、基于 deterministic retrieval 的 ContextBundle 增量装配、围绕 scene draft 的 deterministic checks 与 accept gating、单 draft 的 targeted repair，以及最小 author voice / style constraint 约束链。

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
- Scene Draft 最小主链
  - `ContextBundle`
  - `SceneDraft`
  - `accept / reject`
  - manifest 一致性维护
- Memory 最小链
  - `memory/accepted_scenes.json`
  - `memory/chapter_summaries.json`
  - `memory/character_state_summaries.json`
  - accepted draft ingest
  - deterministic retrieval
- Checks 最小链
  - draft 生成后自动 checks
  - draft 级检查报告持久化
  - accept 前 preflight checks
  - blocker 阻断 accept，warning 仅展示
- Targeted Repair 最小链
  - 单个 draft 定向修补
  - repair 后自动重跑 checks
  - repaired draft 继续走 accept / reject 主链
- Author Voice / Style Constraint 最小链
  - `voice_profile.json` 启用与严格校验
  - `StyleConstraintBundle`
  - generate / repair 共用 style 约束
  - warning-only style checks
- 极简 studio 页面
  - `/studio`
  - `/studio/scene.html`
  - `/studio/style.html`
- 单元测试、集成测试、GitHub Actions CI

## 当前 API 概览

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

Drafts:

- `POST /api/projects/{project_id}/drafts/scenes/{scene_id}/generate`
- `GET /api/projects/{project_id}/drafts/scenes/{scene_id}`
- `GET /api/projects/{project_id}/drafts/{draft_id}`
- `POST /api/projects/{project_id}/drafts/{draft_id}/repair`
- `POST /api/projects/{project_id}/drafts/{draft_id}/accept`
- `POST /api/projects/{project_id}/drafts/{draft_id}/reject`
- `GET /api/projects/{project_id}/drafts/{draft_id}/checks/latest`
- `POST /api/projects/{project_id}/drafts/{draft_id}/checks/recheck`

Style:

- `GET /api/projects/{project_id}/style/voice-profile`
- `PUT /api/projects/{project_id}/style/voice-profile`

## 关键约束

- Python 版本范围：`>=3.11,<3.15`
- 仅使用 Pydantic v2
- `volume_no` 在项目内唯一
- `chapter_no` 在项目内唯一
- `scene_no` 在同一 chapter 内唯一
- 任一 CharacterCard 的增删改都会使 `characters.json.status = draft`
- 删除被结构化 Story/Plan 引用的角色会返回 `409`
- 所有 planner generate 接口默认 `overwrite=false`，目标文件已存在时返回 `409`
- `master_outline.json` 读兼容旧字段 `status`，写统一使用 `outline_status`
- Scene Draft Generation 的前置条件是硬条件：story_bible / characters / world / power_system / volume / chapter / scene 都必须 `ready`
- 所有 path 字段统一保存为相对于 `projects/<slug>/` 的相对路径
- `accept / reject` 只允许对 `draft` 状态执行；对非 `draft` 状态一律 `409`
- mock generation 是 deterministic，可复现，并且只依赖固定输入字段
- retrieval 只使用 deterministic / rule-based 逻辑，不依赖 Chroma 真检索
- retrieval 缺失或 memory 文档损坏时不阻断 generate，只返回部分结果和 warning
- `chapter_summaries.json` 对当前 chapter 采用全量重算
- `character_state_summaries.json` 只保留每个角色最后一条有效状态
- checks 只使用 deterministic / rule-based 规则，不调用 LLM critic
- `accept_preflight` 与 `generate_auto` 使用同一套规则集，不提升 issue 严重级别
- accept 仅由 blocker 或 checks error 阻断；warning 不阻断
- repair 只允许修改当前 draft 的 `content_md`、`summary` 与 `repair_metadata`
- repair 不修改 canonical Bible/Planner 文档，也不修改 memory 文档
- `voice_profile.json` 采用全量覆盖、严格校验，未知字段和非法枚举值直接 `400`
- 读取损坏的 `voice_profile.json` 不阻断 generate / repair，只会降级到 disabled style bundle + warnings
- style disabled 时，`StyleConstraintBundle` 始终返回固定完整结构，不返回 `null`
- style warnings 只进入 check report，不参与 accept blocker，也默认不进入 auto repair 目标集合

## 当前已知限制

- generate 仍是最小 Scene Draft Generation，不是完整长链写作系统
- checks 当前仅覆盖 ScenePlan 对齐、角色出现、时间顺序、地点/境界字面冲突的最小规则
- style 当前只做最小 author voice / style constraint，不是完整 style engine
- 无自由重写
- 无 polish / expand / compress 多模式改写
- 无 Chroma 真向量检索
- 无 memory debug API
- stale 只做结构化传播，不做自动重建
- memory 文档是派生层，不是 canonical 真相源
- retrieval 当前只服务 scene draft generation，不扩展为通用搜索接口
- 当前 continuity 仍保留 Phase 3A 的上一 accepted 场景摘要兼容字段
- 编号变更当前仅在服务层支持，公开 API 暂不开放 `volume_no/chapter_no/scene_no` 编辑
- repair 当前只支持单 draft targeted repair，不支持 diff/merge、issue 多选 UI 或自由改写
- style 不做作者语料分析、不做 style scoring、不做 embedding 风格检索
- style sanitizer 只做 deterministic 字面级清理，不做自由润色

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
- `http://127.0.0.1:8000/studio/scene.html`
- `http://127.0.0.1:8000/studio/style.html`

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
  services/      bootstrap/project/consultant/bible/planner/context/draft/memory/retrieval/checks/repair/style 服务
  static/studio/ 本地占位页
projects/        项目目录根
actions/         GitHub Actions 工作流
tests/           单元与集成测试
```
