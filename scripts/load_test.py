"""Prueba de carga simple (BE-T20), solo biblioteca estándar.

Inicia sesión con los usuarios demo y lanza peticiones concurrentes a las
pantallas principales. Mide latencia (P50/P95/P99), errores y throughput.

Uso (con `seed_demo --password <clave>` y el servidor corriendo):
    LOAD_PASSWORD=<clave> python scripts/load_test.py --base http://127.0.0.1:8000 \
        --threads 10 --requests 50
"""

import argparse
import http.cookiejar
import os
import re
import statistics
import threading
import time
import urllib.parse
import urllib.request

PASSWORD = os.environ["LOAD_PASSWORD"]  # la de `seed_demo --password` (ADR-072)
PAGES = {
    "usuario": ["/inicio/", "/tickets/", "/assistant/"],
    "agente_ti": ["/inicio/", "/agent/inbox/", "/tickets/"],
    "supervisor": ["/agent/inbox/", "/alerts/", "/metrics/", "/tickets/"],
}


def session(base, username):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    page = opener.open(f"{base}/accounts/login/").read().decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
    data = urllib.parse.urlencode(
        {"username": username, "password": PASSWORD, "csrfmiddlewaretoken": token}
    ).encode()
    req = urllib.request.Request(f"{base}/accounts/login/", data, headers={"Referer": base})
    opener.open(req).read()
    return opener


def worker(base, username, n, results, errors, lock):
    opener = session(base, username)
    pages = PAGES[username]
    for i in range(n):
        url = base + pages[i % len(pages)]
        start = time.perf_counter()
        try:
            with opener.open(url, timeout=30) as resp:
                resp.read()
                ok = resp.status == 200
        except Exception:  # noqa: BLE001 - se cuenta como error
            ok = False
        elapsed = (time.perf_counter() - start) * 1000
        with lock:
            (results if ok else errors).append(elapsed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--threads", type=int, default=10)
    parser.add_argument("--requests", type=int, default=50, help="por hilo")
    args = parser.parse_args()
    users = list(PAGES)
    results, errors, lock = [], [], threading.Lock()
    threads = [
        threading.Thread(
            target=worker,
            args=(args.base, users[i % len(users)], args.requests, results, errors, lock),
        )
        for i in range(args.threads)
    ]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_s = time.perf_counter() - start
    ordered = sorted(results)

    def pct(p):
        return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]

    total = len(results) + len(errors)
    print(f"Peticiones: {total} · errores: {len(errors)} · {total / total_s:.1f} req/s")
    if ordered:
        print(
            f"Latencia ms: media {statistics.fmean(ordered):.0f} · P50 {pct(50):.0f} · "
            f"P95 {pct(95):.0f} · P99 {pct(99):.0f} · máx {ordered[-1]:.0f}"
        )


if __name__ == "__main__":
    main()
