# AgentVault Services Stopper
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "          STOPPING AGENTVAULT SERVICES                 " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

$ports = @(8545, 8000, 5173)

foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $procIds) {
            if ($p -gt 0) {
                $pName = (Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName
                Write-Host "  Stopping $pName (PID $p) on port $port..." -ForegroundColor Yellow
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# Ensure standalone anvil.exe is killed
$anvils = Get-Process -Name "anvil" -ErrorAction SilentlyContinue
if ($anvils) {
    Write-Host "  Stopping Anvil processes..." -ForegroundColor Yellow
    $anvils | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Host "`n[OK] All services on ports 8545 (Anvil), 8000 (Backend), and 5173 (Frontend) are stopped!" -ForegroundColor Green

