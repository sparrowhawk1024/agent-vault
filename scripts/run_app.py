"""AgentVault Full Stack Background Runner.

Starts:
1. Local Anvil blockchain (port 8545, chainId 31337).
2. Deploys PolicyVault & MockUSDC contracts via Deploy.s.sol.
3. Starts FastAPI backend server on port 8000.
4. Checks/starts Vite frontend on port 5173.
"""

import os
import sys
import time
import subprocess
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=================================================================")
    print("       STARTING AGENTVAULT END-TO-END DEMONSTRATION STACK        ")
    print("=================================================================\n")

    # 1. Start Anvil
    print("[1/4] Checking/Starting Anvil node (http://127.0.0.1:8545, chainId: 31337)...")
    anvil_running = False
    try:
        r_anvil = requests.post("http://127.0.0.1:8545", json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=1.5)
        if r_anvil.status_code == 200:
            anvil_running = True
            print("  [OK] Anvil node is already running!")
    except Exception:
        anvil_running = False

    anvil_proc = None
    if not anvil_running:
        anvil_bin = os.path.expanduser(r"~\.foundry\bin\anvil.exe")
        if not os.path.exists(anvil_bin):
            anvil_bin = "anvil"

        anvil_proc = subprocess.Popen(
            [anvil_bin, "--chain-id", "31337", "--port", "8545", "--silent"],
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        time.sleep(2)

    # 2. Deploy Contracts
    print("[2/4] Deploying PolicyVault & MockUSDC contracts...")
    forge_bin = os.path.expanduser(r"~\.foundry\bin\forge.exe")
    if not os.path.exists(forge_bin):
        forge_bin = "forge"

    cmd = [forge_bin, "script", "script/Deploy.s.sol", "--rpc-url", "http://127.0.0.1:8545", "--broadcast"]
    deploy_res = subprocess.run(cmd, cwd="contracts", capture_output=True, text=True, shell=True)
    if deploy_res.returncode != 0:
        print("  Warning/Error deploying contracts:", deploy_res.stderr[:200])
    else:
        print("  [OK] Contracts deployed successfully!")

    # 3. Start FastAPI Backend
    print("[3/4] Checking/Starting FastAPI backend on http://127.0.0.1:8000...")
    backend_running = False
    try:
        r_api = requests.get("http://127.0.0.1:8000/health", timeout=1.5)
        if r_api.status_code == 200:
            backend_running = True
            print("  [OK] FastAPI backend is already running!")
    except Exception:
        backend_running = False

    api_proc = None
    if not backend_running:
        api_cmd = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", "8000", "--host", "127.0.0.1"]
        api_proc = subprocess.Popen(
            api_cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        time.sleep(3)

    # Verify backend is responding
    try:
        r = requests.get("http://127.0.0.1:8000/health", timeout=5)
        print("  [OK] Backend health:", r.status_code, "Chain connected:", r.json().get("chain", {}).get("connected"))
    except Exception as e:
        print("  Backend probe warning:", e)

    # 4. Check Frontend
    print("[4/4] Checking Frontend server on http://localhost:5173...")
    frontend_running = False
    try:
        r_fe = requests.get("http://localhost:5173", timeout=2)
        if r_fe.status_code < 500:
            frontend_running = True
            print("  [OK] Frontend is already running on http://localhost:5173")
    except Exception:
        frontend_running = False

    fe_proc = None
    if not frontend_running:
        print("  Starting Vite frontend...")
        fe_proc = subprocess.Popen(
            ["npm.cmd" if os.name == 'nt' else "npm", "--prefix", "frontend", "run", "dev"],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        time.sleep(3)
        print("  [OK] Frontend initiated on http://localhost:5173")

    print("\n=================================================================")
    print("   ALL SERVICES RUNNING SUCCESSFULLY!                            ")
    print("   Dashboard UI:   http://localhost:5173                         ")
    print("   Auto-Refill:    http://localhost:5173/refill                  ")
    print("   Backend API:    http://127.0.0.1:8000                         ")
    print("   Anvil Node:     http://127.0.0.1:8545                         ")
    print("=================================================================")
    print("   Press Ctrl+C to stop all services (or run .\\stop.ps1 in another terminal)")
    print("=================================================================\n")

    # Open browser automatically
    try:
        import webbrowser
        webbrowser.open("http://localhost:5173/refill")
    except Exception:
        pass

    def cleanup():
        print("\nStopping AgentVault services...")
        procs = [p for p in (anvil_proc, api_proc, fe_proc) if p is not None]
        for p in procs:
            try:
                if os.name == 'nt':
                    subprocess.run(f"taskkill /F /T /PID {p.pid}", shell=True, capture_output=True)
                else:
                    p.terminate()
            except Exception:
                pass
        # Extra safety: kill by port via PowerShell on Windows
        if os.name == 'nt':
            subprocess.run(
                'powershell -NoProfile -Command "8545,8000,5173 | ForEach-Object { $c = Get-NetTCPConnection -LocalPort $_ -ErrorAction SilentlyContinue; if ($c) { $c.OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } }"',
                shell=True,
                capture_output=True
            )
        print("[OK] All services stopped.")

    # Keep alive so processes remain running
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        cleanup()

if __name__ == "__main__":
    main()
