import os, time

def load_env(path):
    if not os.path.exists(path): return
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))

load_env('.env')
from app.ai.model_router import complete

try:
    t0 = time.time()
    text = complete([{"role": "user", "content": "Reply with exactly: OK"}], temperature=0.0)
    print('SUCCESS in %.1fs:' % (time.time() - t0), repr((text or '')[:120]))
except Exception as exc:
    print('FAILED:', type(exc).__name__, str(exc)[:300])
