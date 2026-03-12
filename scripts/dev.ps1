$hostAddress = if ($env:APP_HOST) { $env:APP_HOST } else { '127.0.0.1' }
$port = if ($env:APP_PORT) { $env:APP_PORT } else { '8000' }
python -m uvicorn backend.app.main:app --reload --host $hostAddress --port $port
