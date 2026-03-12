function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) {
            return
        }

        $parts = $line.Split('=', 2)
        if ($parts.Length -ne 2) {
            return
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (-not [string]::IsNullOrWhiteSpace($name)) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

Import-DotEnv -Path '.env'

$hostAddress = if ($env:APP_HOST) { $env:APP_HOST } else { '127.0.0.1' }
$port = if ($env:APP_PORT) { $env:APP_PORT } else { '8000' }
python -m uvicorn backend.app.main:app --reload --host $hostAddress --port $port
