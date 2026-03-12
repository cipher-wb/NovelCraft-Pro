$ErrorActionPreference = 'Stop'

$hostAddress = if ($env:APP_HOST) { $env:APP_HOST } else { '127.0.0.1' }
$port = if ($env:APP_PORT) { $env:APP_PORT } else { $env:APP_PORT = '8000'; '8000' }
if (-not $env:DATA_ROOT) { $env:DATA_ROOT = '.\smoke-data' }
if (-not $env:PROJECTS_ROOT) { $env:PROJECTS_ROOT = '.\smoke-projects' }
if (-not $env:LLM_MODE) { $env:LLM_MODE = 'mock' }
if (-not $env:OPENAI_BASE_URL) { $env:OPENAI_BASE_URL = 'https://api.openai.com/v1' }
if (-not $env:OPENAI_API_KEY) { $env:OPENAI_API_KEY = '' }

$dataRootFull = [System.IO.Path]::GetFullPath($env:DATA_ROOT)
$projectsRootFull = [System.IO.Path]::GetFullPath($env:PROJECTS_ROOT)

$job = Start-Job -ScriptBlock {
    param($workingDir, $hostAddressArg, $portArg, $dataRootArg, $projectsRootArg, $llmModeArg, $openaiBaseUrlArg, $openaiApiKeyArg)
    Set-Location $workingDir
    $env:DATA_ROOT = $dataRootArg
    $env:PROJECTS_ROOT = $projectsRootArg
    $env:LLM_MODE = $llmModeArg
    $env:OPENAI_BASE_URL = $openaiBaseUrlArg
    $env:OPENAI_API_KEY = $openaiApiKeyArg
    python -m uvicorn backend.app.main:app --host $hostAddressArg --port $portArg
} -ArgumentList (Get-Location).Path, $hostAddress, $port, $dataRootFull, $projectsRootFull, $env:LLM_MODE, $env:OPENAI_BASE_URL, $env:OPENAI_API_KEY

try {
    Start-Sleep -Seconds 3

    $health = Invoke-RestMethod -Uri "http://$hostAddress`:$port/health" -Method Get
    if ($health.status -ne 'ok') {
        throw 'Health check failed.'
    }

    $project = Invoke-RestMethod -Uri "http://$hostAddress`:$port/api/projects" -Method Post -ContentType 'application/json' -Body (@{
        title = 'Smoke Novel'
        genre = 'urban-fantasy'
        target_chapters = 120
        target_words = 1000000
    } | ConvertTo-Json)

    $session = Invoke-RestMethod -Uri "http://$hostAddress`:$port/api/projects/$($project.project_id)/consultant/sessions" -Method Post -ContentType 'application/json' -Body (@{
        brief = 'Build a long-running urban cultivation power fantasy.'
        preferred_subgenres = @('urban-fantasy', 'power-progression')
        constraints = @('author-led', 'serialized-longform')
    } | ConvertTo-Json)

    $answers = @{
        market_hook = 'Office worker awakens a merit system and rises by crushing enemies in modern society.'
        target_audience = 'male power fantasy readers'
        protagonist_design = 'patient protagonist who starts humiliated and rises quickly'
        golden_finger_design = 'merit exchange system with visible upgrade milestones'
        core_conflict_engine = 'modern society collides with hidden cultivation factions'
        early_30_chapter_pacing = 'first ten awaken, second ten dominate, final ten break the first major deadlock'
    }

    $currentQuestion = $session.current_question
    while ($null -ne $currentQuestion) {
        $answerBody = @{
            question_id = $currentQuestion.question_id
            answer = $answers[$currentQuestion.question_id]
        } | ConvertTo-Json
        $state = Invoke-RestMethod -Uri "http://$hostAddress`:$port/api/consultant/sessions/$($session.session_id)/answer" -Method Post -ContentType 'application/json' -Body $answerBody
        $currentQuestion = $state.current_question
    }

    $null = Invoke-RestMethod -Uri "http://$hostAddress`:$port/api/consultant/sessions/$($session.session_id)/finalize" -Method Post
    $expectedDossierPath = Join-Path $projectsRootFull $project.slug
    $expectedDossierPath = Join-Path $expectedDossierPath 'consultant'
    $expectedDossierPath = Join-Path $expectedDossierPath 'dossier.json'
    if (-not (Test-Path $expectedDossierPath)) {
        throw "Dossier file was not created: $expectedDossierPath"
    }

    Write-Host 'Smoke test passed.'
}
finally {
    Stop-Job $job -ErrorAction SilentlyContinue | Out-Null
    Receive-Job $job -Keep -ErrorAction SilentlyContinue | Out-Null
    Remove-Job $job -Force -ErrorAction SilentlyContinue | Out-Null
}
