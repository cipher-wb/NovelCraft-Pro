# NovelCraft Pro 开发交接文档

本文档用于把当前仓库的开发内容、阶段进度、原始需求约束和继续开发所需入口收拢到一处，方便在别的设备上继续推进项目。

---

## 1. 当前状态

- 当前主分支：`main`
- 当前本地 `main` 目标提交：`9951ba91c8b98ed9d2bd58024d4811e0edb718ae`
- 预览版 tag：`v0.11.0-preview`
- release 锚点分支：`codex/release-v0.11-preview`
- 当前稳定阶段：`Phase 11（Release Hardening / Pre-Ship Cleanup Minimal Chain）`

当前 `main` 已包含：

- Phase 10A：`export / rebuild / diagnostics / health`
- Phase 10B：`project package / import-package / archive / backup / snapshots`
- Phase 11：README / docs 收口、示例项目包、release preflight、工作台错误边界收口

---

## 2. 项目原始目标与长期约束

这个项目的主线目标一直不是“不断叠加智能层”，而是做出一条**可控、可回溯、可交付**的中文长篇网文协同写作链路。

开发过程中反复坚持的原始约束：

- 优先 `deterministic / rule-based`
- 不新增 LLM critic
- 不做 book-level repair / rewrite / polish
- 不修改现有 canonical Bible / Planner 文件格式，除非必要
- 尽量把 scene / chapter / volume / book 做成稳定派生层
- 在成品化阶段优先补 export / import / rebuild / diagnostics / archive / backup，而不是再堆新智能模块

如果后续继续开发，默认仍应把这些约束当作边界条件，而不是每次重开设计。

---

## 3. 阶段进度总览

### Phase 1

- 最小可运行骨架
- 建立基本 FastAPI / 项目结构 / 存储组织方式

### Phase 2

- Bible + Planner 结构化规划层
- 建立 consultant -> bible -> plans 的 canonical 主线

### Phase 3A

- Scene Draft Generation 最小主链
- 支持面向单 scene 的草稿生成

### Phase 3B

- Memory Ingest + Retrieval 最小链
- 让 accepted scene 开始进入检索上下文

### Phase 4

- Deterministic Checks 最小链
- 明确 scene draft 的 rule-based 检查与 gating

### Phase 5A

- Targeted Rewrite / Repair 最小链
- 只做针对性修复，不扩展为整章/整书重写

### Phase 5B

- Author Voice / Style Constraint 最小链
- 增加 style profile 与写作约束注入

### Phase 6

- Chapter Assembly / Chapter Finalization
- 章节 assembled / finalized 派生层落地

### Phase 7

- Volume Assembly / Arc Progression
- 卷 assembled / finalized 派生层落地

### Phase 7.5

- Retrieval 开始消费 `memory/volume_summaries.json`
- 只增强 scene generation / repair 的 retrieval 背景，不新增 checks

### Phase 8A

- Book Assembly / Book Progression 最小链
- 整书 assembled / finalized 派生层落地
- `memory/book_summary.json` 写入链落地

### Phase 8B

- Retrieval 开始消费 `memory/book_summary.json`
- 只在最后两个 canonical planned volumes 中注入整书摘要背景

### Phase 9

- Book-level Checks / Long-arc Continuity 最小链
- 新增整书级连续性检查报告与 finalize preflight

### Phase 10A

- Studio / Export / Rebuild / Productization 最小链
- 打通工作台、导出、重建、项目体检

### Phase 10B

- Export / Import / Archive / Backup 最小链
- 项目包、导入、归档快照、备份、快照列表落地

### Phase 11

- Release Hardening / Pre-Ship Cleanup 最小链
- 收口 README / docs / release notes 模板
- 提供可导入示例项目包
- 提供 `scripts/release_preflight.ps1`

---

## 4. 当前已经可用的能力

### 核心写作链

- consultant 立项问答
- bible / characters / world / power system / planner 结构化确认
- scene draft 生成
- deterministic checks
- accept / reject / targeted repair
- accepted scene 驱动的 memory / retrieval

### 组装与定稿链

- chapter assemble / finalize
- volume assemble / finalize
- book assemble / finalize
- book continuity checks preflight

### 成品化链

- scene / chapter / volume / book / project 导出
- rebuild
- diagnostics / health
- project package
- import-package
- archive snapshot
- backup
- snapshots list

### 交付收尾链

- `/studio` 工作台
- 示例项目包
- 演示流程
- 发布检查清单
- 发布说明模板
- `release_preflight` 只读检查

---

## 5. 当前没有做、也不应误判为已完成的范围

以下内容截至当前版本**没有进入 `main` 的已交付能力**：

- 新的智能写作模块
- LLM critic
- 复杂跨书语义推理
- book-level repair / regeneration
- 整书级 rewrite / polish / style scoring
- 云同步
- 后台任务队列
- 自动发布流水线

后续如果要做这些内容，建议作为新的阶段单独设计，而不是直接在现有 Phase 11 之后无约束扩展。

---

## 6. 关键文档入口

建议在别的设备上先读这些文件：

- [README.md](/F:/AI/codex/写小说工具融合/README.md)
- [使用说明书.md](/F:/AI/codex/写小说工具融合/使用说明书.md)
- [docs/demo-workflow.md](/F:/AI/codex/写小说工具融合/docs/demo-workflow.md)
- [docs/release-checklist.md](/F:/AI/codex/写小说工具融合/docs/release-checklist.md)
- [docs/releases/v0.11.0.md](/F:/AI/codex/写小说工具融合/docs/releases/v0.11.0.md)
- [examples/sample-project-package](/F:/AI/codex/写小说工具融合/examples/sample-project-package)

如果你是为了继续开发而不是演示，优先阅读顺序建议是：

1. `README.md`
2. `docs/project-handoff.md`（本文）
3. `使用说明书.md`
4. `docs/demo-workflow.md`
5. 对应阶段的 service / api / tests

---

## 7. 关键运行与验证命令

### 安装与启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 基础验证

```powershell
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts/release_preflight.ps1
```

### 最短演示路径

1. 导入示例项目包
2. 打开 `/studio`
3. 查看项目体检
4. 触发导出项目包
5. 触发创建归档快照
6. 触发创建备份
7. 查看快照列表

---

## 8. 在别的设备继续开发的推荐步骤

### 方案 A：继续主线开发

适合你要直接在最新 `main` 上继续推进。

步骤：

1. 拉取仓库
2. checkout `main`
3. 确认 `main` 指向包含 Phase 11 的提交
4. 跑安装与验证命令
5. 导入示例项目包确认环境正常
6. 再开始设计新的阶段或补丁

### 方案 B：基于 release 锚点继续

适合你想保留 preview 交付基线，同时在另一条线上试验。

步骤：

1. 拉取仓库
2. checkout `codex/release-v0.11-preview`
3. 从这个分支再切新分支继续开发

---

## 9. 继续开发时建议遵守的规则

- 先做设计，再改代码
- 继续保持 deterministic / rule-based 优先
- 不要随意改 canonical 文件格式
- 新增任何阶段前，先明确边界：是否是 retrieval、checks、repair、productization 还是 release hardening
- 优先补充 tests，再补实现
- 任何“完成”结论前都重新跑验证命令

---

## 10. 当前仓库治理状态

当前分支已经做过一次清理：

- 已保留：
  - `main`
  - `codex/release-v0.11-preview`
  - `v0.11.0-preview`
- 旧的 `codex/phase*` 开发分支已经清理

这意味着：

- GitHub 上现在更适合作为“交付基线 + 继续开发起点”
- 如果后续再开新阶段，建议继续使用 `codex/<topic>` 前缀分支

---

## 11. 交接结论

截至当前仓库状态，项目已经从“阶段性功能开发”推进到了“可预览交付”的版本：

- 主链完整
- 成品化闭环完整
- 发布前文档与演示资产齐全
- 已有 preview tag 与 release 锚点分支

如果你在别的设备继续推进，当前最合适的起点是：

- 直接从 `main` 开始后续工作，或
- 基于 `codex/release-v0.11-preview` 新建下一条开发分支

在此基础上继续开发，不需要再回头补前面阶段的基础设施。
