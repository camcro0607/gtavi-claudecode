# Registers the nightly clip run in Windows Task Scheduler (current user, runs only while logged in).
# usage (PowerShell):  .\install_task.ps1 -Cmd C:\path\to\run_overnight.cmd -At 23:00
# The pipeline itself stops at the end of the window in config/desk.json (default 07:00) and pauses if you are using the PC.
param(
  [Parameter(Mandatory = $true)][string]$Cmd,
  [string]$At = "23:00",
  [string]$Name = "ClipDeskOvernight"
)
$action   = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Cmd`""
$trigger  = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit (New-TimeSpan -Hours 9) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Registered '$Name' daily at $At. Test it now with: Start-ScheduledTask -TaskName $Name"
Write-Host "Remove with: Unregister-ScheduledTask -TaskName $Name -Confirm:`$false"
