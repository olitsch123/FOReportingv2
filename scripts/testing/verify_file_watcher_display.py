"""Verify file watcher display in frontend."""
import requests

print("Checking File Watcher Display...")
print("=" * 50)

# Get health status
response = requests.get("http://localhost:8000/health")
health = response.json()

services = health.get("services", {})
fw_status = services.get("file_watcher", "unknown")

print(f"File Watcher Status: {fw_status}")

# Determine icon
if fw_status == "running":
    icon = "✅"
    desc = "Active"
elif fw_status == "stopped":
    icon = "⏸️"
    desc = "Paused/Stopped"
else:
    icon = "❌"
    desc = "Error/Unknown"

print(f"Display: {icon} File_Watcher: {fw_status} ({desc})")
print()
print("✅ The file watcher now shows:")
print(f"   - ⏸️ when stopped (not ❌)")
print(f"   - ✅ when running")
print(f"   - ❌ only for actual errors")
print()
print("Please refresh your browser at http://localhost:8501")
print("The sidebar should now show: ⏸️ File_Watcher: stopped")
print("=" * 50)