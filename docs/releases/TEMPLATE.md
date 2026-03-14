# 发布说明模板

## 摘要

- [用 2-4 条简述本次发布范围]

## 包含能力

- [列出本次实际交付能力]

## 已验证命令

```powershell
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts/release_preflight.ps1
```

## 已知限制

- [列出本次发布接受的已知限制]

## 提交哈希

- `HEAD=<fill-me>`
