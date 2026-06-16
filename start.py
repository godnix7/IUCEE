import subprocess
import sys
import os
import time
import shutil

def _resolve_python():
    """Prefer the project venv on a short path (avoids Windows long-path PyTorch issues)."""
    candidates = [
        r"D:\iucee-venv\Scripts\python.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "venv", "Scripts", "python.exe"),
        sys.executable,
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable

def main():
    print("============================================")
    print(" AI-Powered Pixel Annotation Studio")
    print("============================================")
    print()
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root_dir, "frontend")
    backend_dir = os.path.join(root_dir, "backend")
    python_exe = _resolve_python()
    
    # Start the backend server
    print(f"[1/2] Starting FastAPI backend on port 8000 ({python_exe})...")
    backend_process = subprocess.Popen(
        [python_exe, "run.py"], 
        cwd=backend_dir
    )
    
    time.sleep(2)
    
    # Start the frontend dev server
    # Use node directly to run the vite binary, bypassing npm/npx shell scripts
    print("[2/2] Starting Vite React frontend...")
    vite_bin = os.path.join(frontend_dir, "node_modules", ".bin", "vite")
    
    # On Windows, the .bin folder has a vite.CMD wrapper — but we can run 
    # node with the vite JS entry point directly to avoid all shell issues.
    vite_js = os.path.join(frontend_dir, "node_modules", "vite", "bin", "vite.js")
    
    # Find node.exe
    node_exe = os.path.join("C:\\nvm4w\\nodejs", "node.exe")
    if not os.path.exists(node_exe):
        node_exe = shutil.which("node")
    
    if not node_exe or not os.path.exists(node_exe):
        print("ERROR: Could not find node.exe!")
        backend_process.terminate()
        sys.exit(1)
    
    if not os.path.exists(vite_js):
        print(f"ERROR: Vite not found at {vite_js}")
        print("Run 'npm install' in the frontend/ directory first.")
        backend_process.terminate()
        sys.exit(1)
    
    frontend_process = subprocess.Popen(
        [node_exe, vite_js],
        cwd=frontend_dir
    )
    
    try:
        print()
        print("=== All servers are running! ===")
        print("Backend:  http://localhost:8000")
        print("Frontend: http://localhost:5173")
        print()
        print("Press Ctrl+C to stop all servers.")
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()
        print("Servers stopped.")

if __name__ == "__main__":
    main()
