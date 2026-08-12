import os

def load_env(path):
    if not os.path.exists(path): return
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))

load_env('.env')
import httpx, json

key = os.environ.get('OPENROUTER_API_KEY', '')
base = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
print('Base URL:', base)
print('Key present:', bool(key), '(len %d)' % len(key))
print()

for ep in ['/credits', '/key', '/limits']:
    try:
        r = httpx.get(base + ep, headers={'Authorization': f'Bearer {key}'}, timeout=20)
        print(f'--- GET {ep} -> {r.status_code}')
        try:
            print(json.dumps(r.json(), indent=2)[:1200])
        except Exception:
            print(r.text[:400])
    except Exception as exc:
        print(f'--- GET {ep} FAILED: {exc}')
    print()
