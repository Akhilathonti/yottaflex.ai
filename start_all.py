"""
Unified launcher for LOGIX-ETA Intelligent Logistics System.
Starts both the FastAPI Backend (port 8000) and the Streamlit Dashboard (port 8501).
"""
import os
import sys
import time
import threading
import webbrowser
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

def main():
    print("=" * 68)
    print("  🚚 STARTING LOGIX-ETA INTELLIGENT LOGISTICS PLATFORM")
    print("=" * 68)

    db_path = BASE_DIR / "data" / "logistics.db"
    if not db_path.exists():
        print("Initial database not detected. Generating baseline data & users...")
        subprocess.run([sys.executable, "-m", "src.data_generation.generate_data", "--starter"])
        subprocess.run([sys.executable, "-m", "src.database.seed_users"])

    print("--> 1. Starting FastAPI Backend (Port 8000)...")
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    print("=" * 68)
    print("  ✅ SERVICES ONLINE AND READY:")
    print("=" * 68)
    print("  👉 Web Dashboard URL : http://localhost:8501")
    print("  👉 REST API Docs URL : http://127.0.0.1:8000/docs")
    print("=" * 68)
    print("  Launching Streamlit dashboard and opening your browser...")
    print("  (Press Ctrl+C in this terminal window at any time to shut down)")
    print("=" * 68)

    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8501")

    t = threading.Thread(target=open_browser)
    t.daemon = True
    t.start()

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "dashboard/app.py",
            "--server.port", "8501",
            "--browser.serverAddress", "localhost"
        ])
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=3)
        except Exception:
            api_proc.kill()
        print("All servers stopped successfully.")

if __name__ == "__main__":
    main()
