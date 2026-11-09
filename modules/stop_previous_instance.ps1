# Closes earlier RobotInsight runs so only one instance listens and speaks.
# ROBOT_DIR is the project folder with a trailing backslash, set by the launcher.
$root = $env:ROBOT_DIR.ToLower()
$launcher = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId

$previous = Get-CimInstance Win32_Process | Where-Object {
    $line = ([string]$_.CommandLine).ToLower()
    $path = ([string]$_.ExecutablePath).ToLower()
    $_.ProcessId -ne $launcher -and (
        ($_.Name -eq 'cmd.exe' -and $line.Contains($root + 'start_robotinsight.bat')) -or
        ($_.Name -eq 'python.exe' -and $path -eq ($root + '.venv\scripts\python.exe') -and $line.Contains('main.py'))
    )
}

foreach ($process in $previous) {
    & taskkill.exe /t /f /pid $process.ProcessId 2>&1 | Out-Null
}
if ($previous) {
    Write-Output 'Closed a previous RobotInsight session.'
}
