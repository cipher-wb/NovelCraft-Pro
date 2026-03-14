# 演示流程

本流程与 `examples/sample-project-package/` 强绑定，默认你从仓库根目录启动服务，并且本地 `projects/` 中还没有同名演示项目。

## 1. 启动服务

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

预期结果：

- `http://127.0.0.1:8000/health` 返回 `200`
- 返回体至少包含：
  - `"status": "ok"`
  - `"app": "NovelCraft Pro"`

## 2. 导入示例项目包

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/projects/import-package" `
  -ContentType "application/json" `
  -Body '{"package_path":"examples/sample-project-package","new_project_id":"proj_phase11_demo","new_project_slug":"phase11-demo","mode":"create_new"}'
```

预期结果：

- HTTP `200`
- 返回体至少包含：
  - `"package_version": "project_package_v1"`
  - `"project_id": "proj_phase11_demo"`
  - `"project_slug": "phase11-demo"`
  - `"mode": "create_new"`
  - `"post_import_health"`

## 3. 查看只读 health

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/projects/proj_phase11_demo/diagnostics/health"
```

预期结果：

- HTTP `200`
- 返回体至少包含：
  - `"project_id": "proj_phase11_demo"`
  - `"overall_status": "clean"`
  - `"book_artifact": { "status": "finalized", ... }`

## 4. 打开工作台

浏览器访问：

- `http://127.0.0.1:8000/studio`

预期结果：

- 页面标题显示 `NovelCraft Pro`
- 页面中可见：
  - `项目体检`
  - `导出项目包`
  - `导入项目包`
  - `创建归档快照`
  - `创建备份`
  - `加载快照列表`

## 5. 在工作台里加载体检信息

操作：

- 在 `项目 ID` 输入 `proj_phase11_demo`
- 点击 `加载体检`

预期结果：

- `项目体检` 区块显示 JSON
- JSON 中至少包含：
  - `"project_id": "proj_phase11_demo"`
  - `"overall_status": "clean"`

## 6. 导出 project package

操作：

- 点击 `导出项目包`

预期结果：

- 结果区块返回 JSON
- JSON 中至少包含：
  - `"scope": "project"`
  - `"format": "json_package"`
  - `"package_version": "project_package_v1"`
  - `"relative_dir"`

## 7. 创建 archive snapshot

操作：

- 在 `Archive Label` 输入 `phase11-demo`
- 点击 `创建归档快照`

预期结果：

- 返回 JSON
- 至少包含：
  - `"snapshot_type": "archive"`
  - `"label": "phase11-demo"`
  - `"relative_dir"`

## 8. 创建 backup

操作：

- 点击 `创建备份`

预期结果：

- 返回 JSON
- 至少包含：
  - `"snapshot_type": "backup"`
  - `"label": ""`
  - `"relative_dir"`

## 9. 查看 snapshots list

操作：

- 点击 `加载快照列表`

预期结果：

- 返回 JSON
- `items` 至少包含两条记录
- `snapshot_type` 集合至少包含：
  - `archive`
  - `backup`

## 10. 结束条件

满足以下条件即可认为演示流程成功：

- 示例项目包成功导入为新项目
- health 返回 `clean`
- 工作台可用
- 导出项目包成功
- archive snapshot 成功
- backup 成功
- snapshots list 能同时列出 archive 和 backup
