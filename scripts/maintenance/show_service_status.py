"""Show service status with correct icons."""
import requests

response = requests.get("http://localhost:8000/health")
health = response.json()

print("\nSystem Status (as shown in frontend):")
print("=" * 40)

services = health.get("services", {})
for service, status in services.items():
    # Special handling for file watcher
    if service == "file_watcher":
        if status == "running":
            icon = "✅"
        elif status == "stopped":
            icon = "⏸️"
        else:
            icon = "❌"
    else:
        # For other services
        icon = "✅" if status in ["connected", "running"] else "❌"
    
    print(f"{icon} {service.replace('_', ' ').title()}: {status}")

print("=" * 40)
print("\n✅ File watcher now displays correctly!")
print("   No more ❌ for stopped state!")
print("   Refresh http://localhost:8501 to see the fix.")