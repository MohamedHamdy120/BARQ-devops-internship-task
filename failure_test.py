#!/usr/bin/env python3
import subprocess, urllib.request, time, sys

NGINX_ADDRESS = "http://127.0.0.1:8080"
TARGET = "app-01"

def hit_instance():
    try:
        r = urllib.request.urlopen(f"{NGINX_ADDRESS}/instance", timeout=3)
        return r.status, r.read().decode()
    except Exception as e:
        return None, str(e)

print(f"Stopping {TARGET}...")
subprocess.run(["docker", "stop", TARGET], check=True)

print("Traffic during failure:")
during = []
for i in range(6):
    status, body = hit_instance()
    during.append(status)
    print(f"  {status} {body[:60] if body else ''}")
    time.sleep(1)

print(f"Restarting {TARGET}...")
subprocess.run(["docker", "start", TARGET], check=True)
time.sleep(5)  # waiting for it to become healthy

print("Traffic after recovery:")
after = []
for i in range(6):
    status, body = hit_instance()
    after.append(status)
    print(f"  {status} {body[:60] if body else ''}")
    time.sleep(1)

# pass/fail
stayed_up = all(s == 200 for s in during)
target_recovered = False

for _ in range(4):
    status, body = hit_instance()

    if TARGET in body:
        target_recovered = True
        break
print(f"\n[{'PASS' if stayed_up else 'FAIL'}] service stayed available during backend failure")
print(f"[{'PASS' if target_recovered else 'FAIL'}] {TARGET} serving requests again after restart")

sys.exit(0 if stayed_up and target_recovered else 1)