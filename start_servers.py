#!/usr/bin/env python3
"""
Startup script to run both Flask server and WebSocket server for Twilio voice integration.
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def start_websocket_server():
    """Start the WebSocket server for Twilio voice streaming."""
    print("Starting WebSocket server on port 5001...")
    # Use the virtual environment Python
    venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
    if os.path.exists(venv_python):
        websocket_cmd = [venv_python, "lgch_todo/http_websocket_server.py"]
    else:
        websocket_cmd = [sys.executable, "lgch_todo/http_websocket_server.py"]
    return subprocess.Popen(websocket_cmd, cwd=os.getcwd())

def start_flask_server():
    """Start the Flask server."""
    print("Starting Flask server on port 5000...")
    # Use the virtual environment Python
    venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
    if os.path.exists(venv_python):
        flask_cmd = [venv_python, "app.py"]
    else:
        flask_cmd = [sys.executable, "app.py"]
    return subprocess.Popen(flask_cmd, cwd=os.getcwd())

def kill_existing_servers():
    """Kill any existing servers on the required ports."""
    print("🔍 Checking for existing servers...")
    
    # Kill any existing WebSocket servers
    try:
        subprocess.run(["pkill", "-f", "http_websocket_server.py"], check=False)
        print("✅ Cleaned up existing WebSocket servers")
    except:
        pass
    
    # Kill any existing Flask servers
    try:
        subprocess.run(["pkill", "-f", "app.py"], check=False)
        print("✅ Cleaned up existing Flask servers")
    except:
        pass
    
    time.sleep(1)  # Give processes time to terminate

def main():
    """Main function to start both servers."""
    print("🚀 Starting LGCH Todo Voice Integration Servers...")
    print("=" * 60)
    
    # Set up environment for virtual environment
    venv_path = os.path.join(os.getcwd(), "venv")
    if os.path.exists(venv_path):
        print("✅ Using virtual environment:", venv_path)
        # Add virtual environment to PATH
        venv_bin = os.path.join(venv_path, "bin")
        if venv_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")
    else:
        print("⚠️  No virtual environment found, using system Python")
    
    # Clean up any existing servers
    kill_existing_servers()
    
    # Start WebSocket server first
    websocket_process = start_websocket_server()
    time.sleep(3)  # Give WebSocket server time to start
    
    # Start Flask server
    flask_process = start_flask_server()
    
    print("=" * 60)
    print("✅ Both servers are starting up...")
    print("📞 Flask Server: http://localhost:5000")
    print("🔌 WebSocket Server: ws://localhost:5001")
    print("📱 Twilio Webhook: http://localhost:5000/lgch_todo/twilio/call")
    print("=" * 60)
    print("Press Ctrl+C to stop both servers")
    
    try:
        # Wait for both processes
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if websocket_process.poll() is not None:
                print("❌ WebSocket server stopped unexpectedly")
                break
            if flask_process.poll() is not None:
                print("❌ Flask server stopped unexpectedly")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Shutting down servers...")
        
        # Terminate both processes
        websocket_process.terminate()
        flask_process.terminate()
        
        # Wait for graceful shutdown
        try:
            websocket_process.wait(timeout=5)
            flask_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️  Force killing processes...")
            websocket_process.kill()
            flask_process.kill()
        
        print("✅ Servers stopped successfully")

if __name__ == "__main__":
    main()
