# Release Notes Template

## Summary

- [用 2-4 条简述本次发布范围]

## Included Capabilities

- [列出本次实际交付能力]

## Verified Commands

```powershell
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts/release_preflight.ps1
```

## Known Limitations

- [列出本次发布接受的已知限制]

## Commit Hash

- `HEAD=<fill-me>`
