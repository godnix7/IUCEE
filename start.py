import subprocess
import sys
import os
import time

def main():
    print("============================================")
    print(" AI-Powered Pixel Annotation Studio")
    print("============================================")
    print()
    
    root_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root_dir, "frontend")
    backend_dir = os.path.join(root_dir, "backend")
    
    # Start the backend server
    print("[1/2] Starting FastAPI backend on port 8000...")
    backend_process = subprocess.Popen(
        [sys.executable, "run.py"], 
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
        # Fallback: try to find node in PATH
        import shutil
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
