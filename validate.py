#!/usr/bin/env python3
import sys, time, urllib.request, socket, subprocess

NGINX_ADDRESS = "http://127.0.0.1:8080"
results = []

def check(name, fn):
    try:
        ok = fn()
    except Exception as e:
        ok = False
        print(f"  error: {e}")
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    return ok

def http_ok(path, expect=200):
    r = urllib.request.urlopen(f"{NGINX_ADDRESS}{path}", timeout=3)
    return r.status == expect

def port_closed(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    result = s.connect_ex((host, port))
    s.close()
    return result != 0

def wait_for(name, fn, tries=10, delay=2):
    """Bounded wait: retry a check up to `tries` times before giving up."""
    for i in range(tries):
        try:
            if fn():
                return check(name, lambda: True)
        except Exception:
            pass
        time.sleep(delay)
    return check(name, lambda: False)

def both_backends_respond(n=6):
    ids = set()
    for _ in range(n):
        r = urllib.request.urlopen(f"{NGINX_ADDRESS}/instance", timeout=3)
        data = r.read().decode()
        if "app-01" in data:
            ids.add("app-01")
        if "app-02" in data:
            ids.add("app-02")
    return ids == {"app-01", "app-02"}

def nginx_isolated_from(host, port):
    # Runs nc from inside the nginx container itself
    result = subprocess.run(
        ["docker", "exec", "nginx", "nc", "-zv", "-w2", host, str(port)],
        capture_output=True, timeout=6
    )
    return result.returncode != 0  # non-zero = connection failed = isolated 

# ---wait for startup, then running the validation ---
wait_for("nginx reachable on 8080", lambda: http_ok("/"))
check("/health returns 200", lambda: http_ok("/health"))
check("/ready returns 200", lambda: http_ok("/ready"))
check("/records returns 200", lambda: http_ok("/records"))
check("/counter returns 200", lambda: http_ok("/counter"))
check("both app-01 and app-02 respond via /instance", both_backends_respond)
check("postgres port not published on host", lambda: port_closed("127.0.0.1", 5432))
check("redis port not published on host", lambda: port_closed("127.0.0.1", 6379))
check("nginx cannot reach postgres directly", lambda: nginx_isolated_from("postgres", 5432))
check("nginx cannot reach redis directly", lambda: nginx_isolated_from("redis", 6379))

# --- summary ---
failed = []

for n, ok in results:
    if not ok:
        failed.append(n)
print(f"\n{len(results)-len(failed)}/{len(results)} passed.")
if failed:
    print(f"FAILED: {failed}")
    sys.exit(1)
sys.exit(0)