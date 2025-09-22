#!/usr/bin/env python3
"""
Script to set up ngrok tunnels for both Flask and WebSocket servers.
This is required for Twilio to connect to local servers.
"""

import subprocess
import time
import json
import requests
import sys
import os

def get_ngrok_tunnels():
    """Get active ngrok tunnels."""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        return response.json()
    except Exception as e:
        print(f"⚠️  Could not connect to ngrok API: {e}")
        return None

def create_ngrok_tunnel(port, name, protocol="http"):
    """Create an ngrok tunnel for a specific port."""
    print(f"🔗 Creating ngrok tunnel for {name} on port {port}...")
    
    # Kill any existing tunnels on this port
    subprocess.run(["pkill", "-f", f"ngrok.*{port}"], check=False)
    time.sleep(2)
    
    # Start ngrok tunnel
    if protocol == "http":
        cmd = ["ngrok", "http", str(port), "--log=stdout"]
    else:  # tcp for WebSocket
        cmd = ["ngrok", "tcp", str(port), "--log=stdout"]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for tunnel to be ready
        print(f"⏳ Waiting for {name} tunnel to initialize...")
        time.sleep(5)
        
        # Get tunnel info with retries
        for attempt in range(3):
            tunnels = get_ngrok_tunnels()
            if tunnels and 'tunnels' in tunnels:
                print(f"🔍 Found {len(tunnels['tunnels'])} active tunnels")
                for tunnel in tunnels['tunnels']:
                    # Check for various address formats
                    addr = tunnel['config']['addr']
                    print(f"🔍 Checking tunnel: {addr} (looking for port {port})")
                    
                    # Handle both HTTP and TCP tunnels
                    if protocol == "http":
                        # HTTP tunnel address formats
                        if (addr == f'localhost:{port}' or 
                            addr == f'127.0.0.1:{port}' or 
                            addr == f'http://localhost:{port}' or
                            addr == f'http://127.0.0.1:{port}'):
                            public_url = tunnel['public_url']
                            print(f"✅ {name} tunnel created: {public_url}")
                            return public_url, process
                    else:  # TCP tunnel
                        # TCP tunnel address formats
                        if (addr == f'localhost:{port}' or 
                            addr == f'127.0.0.1:{port}'):
                            public_url = tunnel['public_url']
                            print(f"✅ {name} tunnel created: {public_url}")
                            return public_url, process
            else:
                print(f"⚠️  No tunnels found or API error (attempt {attempt + 1}/3)")
            
            if attempt < 2:
                print(f"⏳ Retrying tunnel detection for {name}... (attempt {attempt + 2}/3)")
                time.sleep(2)
        
        print(f"❌ Failed to create {name} tunnel - could not detect tunnel URL")
        process.terminate()
        return None, None
        
    except Exception as e:
        print(f"❌ Error creating {name} tunnel: {e}")
        return None, None

def check_port_available(port):
    """Check if a port is available (no server running)."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result != 0  # Port is available if connection fails
    except:
        return True

def main():
    print("🚀 Setting up ngrok tunnels for Twilio integration...")
    print("=" * 60)
    
    # Check if ngrok is installed
    try:
        subprocess.run(["ngrok", "version"], check=True, capture_output=True)
    except:
        print("❌ ngrok is not installed or not in PATH")
        print("Please install ngrok: https://ngrok.com/download")
        sys.exit(1)
    
    # Check if servers are running
    print("🔍 Checking if servers are running...")
    flask_running = not check_port_available(5000)
    websocket_running = not check_port_available(5001)
    
    print(f"📞 Flask Server (port 5000): {'✅ Running' if flask_running else '❌ Not running'}")
    print(f"🔌 WebSocket Server (port 5001): {'✅ Running' if websocket_running else '❌ Not running'}")
    
    if not flask_running:
        print("⚠️  Flask server is not running. Please start it first with: python app.py")
    if not websocket_running:
        print("⚠️  WebSocket server is not running. Please start it first with: python lgch_todo/http_websocket_server.py")
    
    # Create tunnels
    flask_url, flask_process = create_ngrok_tunnel(5000, "Flask Server", "http")
    websocket_url, websocket_process = create_ngrok_tunnel(5001, "WebSocket Server", "http")
    
    if flask_url:
        print("\n" + "=" * 60)
        print("✅ Tunnels are ready!")
        print(f"📞 Flask Server: {flask_url}")
        if websocket_url:
            print(f"🔌 WebSocket Server: {websocket_url}")
            # TCP tunnels return format like "tcp://0.tcp.ngrok.io:12345"
            if websocket_url.startswith('tcp://'):
                # Convert TCP URL to WebSocket URL
                ws_url = websocket_url.replace('tcp://', 'ws://')
                wss_url = websocket_url.replace('tcp://', 'wss://')
                print(f"🔌 WebSocket URL (ws): {ws_url}")
                print(f"🔌 WebSocket URL (wss): {wss_url}")
            else:
                print(f"🔌 WebSocket URL (wss): {websocket_url.replace('https://', 'wss://').replace('http://', 'ws://')}")
        else:
            print("⚠️  WebSocket tunnel failed - you may need to start the WebSocket server first")
        print(f"📱 Twilio Webhook URL: {flask_url}/lgch_todo/twilio/call")
        print("\n📋 Update your Twilio webhook URL to:")
        print(f"   {flask_url}/lgch_todo/twilio/call")
        print("\n⚠️  Keep this script running while testing Twilio calls!")
        print("=" * 60)
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping ngrok tunnels...")
            if flask_process:
                flask_process.terminate()
            if websocket_process:
                websocket_process.terminate()
            print("✅ Tunnels stopped.")
    else:
        print("❌ Failed to create Flask tunnel - this is required for Twilio webhooks")
        sys.exit(1)

if __name__ == "__main__":
    main()
