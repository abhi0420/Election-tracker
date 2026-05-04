$interval = 5 * 60  # seconds between triggers

Write-Host "Auto-trigger loop started. Press Ctrl+C to stop."
while ($true) {
    $ts = Get-Date -Format "HH:mm:ss"
    gh workflow run scraper.yml
    Write-Host "[$ts] Triggered scraper run"
    Start-Sleep -Seconds $interval
}
