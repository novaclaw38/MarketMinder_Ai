
#!/usr/bin/env python3
"""MarketMinder AI - Launch Sequence"""
import subprocess
import sys
import time
import os

print("=" * 60)
print("  MarketMinder AI - Launch Sequence")
print("=" * 60)
print()

# Step 1: Verify server is running
print("1. Checking server status...")
import urllib.request
try:
    with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as resp:
        print("   ✓ Server is running")
except:
    print("   ✗ Server not running - starting...")
    subprocess.Popen([sys.executable, "/root/marketminder-ai/scripts/simple_server.py"], 
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    print("   ✓ Server started")

# Step 2: Run content generation
print()
print("2. Generating initial content...")
subprocess.run([sys.executable, "/root/marketminder-ai/scripts/content_engine.py"], 
               timeout=120, capture_output=True)
print("   ✓ Content generated")

# Step 3: Run lead generation
print()
print("3. Generating lead outreach...")
subprocess.run([sys.executable, "/root/marketminder-ai/scripts/lead_engine.py"], 
               timeout=120, capture_output=True)
print("   ✓ Leads generated")

# Step 4: Check health
print()
print("4. Checking business health...")
with urllib.request.urlopen("http://localhost:8000/health-score", timeout=5) as resp:
    import json
    health = json.loads(resp.read().decode())
    print(f"   Health Score: {health['health_score']}")
    print(f"   Status: {health['status']}")
    print(f"   Should Terminate: {health['should_terminate']}")

print()
print("=" * 60)
print("  Launch sequence complete!")
print("  Server: http://localhost:8000")
print("  Dashboard: http://localhost:8000/dashboard")
print("=" * 60)
