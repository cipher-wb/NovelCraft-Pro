# Release Checklist

## Must Pass Before Release

- `README.md` 顶部稳定阶段与当前发布范围一致
- `README.md` 中的 productization API 名称与真实路由一致
- `docs/demo-workflow.md` 可直接对应 `examples/sample-project-package/`
- `examples/sample-project-package/` 是可导入的真实 `project_package_v1`
- `python -m pytest -q` 通过
- `powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1` 通过
- `powershell -ExecutionPolicy Bypass -File scripts/release_preflight.ps1` 通过
- sample package 可以通过 `POST /api/projects/import-package` 成功导入
- `/studio` dashboard 可完成：
  - Load Health
  - Export Project Package
  - Create Archive Snapshot
  - Create Backup
  - Load Snapshots
- `POST /api/projects/{project_id}/export` 支持 `scope=project`
- `POST /api/projects/import-package` 可用
- `POST /api/projects/{project_id}/archive-snapshot` 可用
- `POST /api/projects/{project_id}/backup` 可用
- `GET /api/projects/{project_id}/snapshots` 可用
- 工作树干净，没有不应提交的运行时目录
- release notes 已根据 `docs/releases/TEMPLATE.md` 补齐

## Known Limitations Accepted For This Release

- 不新增新的智能写作模块
- 不做 LLM critic
- 不做 book-level repair / rewrite / polish
- import 只支持 `create_new`，不支持覆盖式 restore
- project package 只支持本地目录包，不做云同步
- archive / backup 只做手动本地快照，不做自动定时
- `markdown_package` 只用于阅读/交付，不是恢复核心依赖
- `/studio` dashboard 仍为同步工作台，不提供后台任务队列或复杂运维后台
- 错误码收口只覆盖 productization / dashboard 直连端点，不做全项目错误协议重构
