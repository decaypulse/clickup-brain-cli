# Полностью скрытый запуск ClickUp Brain AI Agent
# Браузер и окно терминала не будут видны

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "clickup_agent.py"

# Запуск в скрытом режиме
Start-Process python -ArgumentList $pythonScript -WindowStyle Hidden -WorkingDirectory $scriptDir
