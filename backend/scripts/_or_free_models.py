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
import httpx

key = os.environ.get('OPENROUTER_API_KEY', '')
base = os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')

r = httpx.get(base + '/models', headers={'Authorization': f'Bearer {key}'}, timeout=30)
print('status:', r.status_code)
data = r.json().get('data', [])
print('total models:', len(data))

free = [m for m in data if ':free' in (m.get('id') or '')]
print('free models:', len(free))
print()
for m in sorted(free, key=lambda x: x.get('id')):
    m_id = m.get('id')
    # supported params include tool calling?
    sp = m.get('supported_parameters') or []
    tools_ok = 'tools' in sp
    pricing = m.get('pricing') or {}
    prompt_p = pricing.get('prompt')
    ctx = m.get('context_length')
    print('  %-55s ctx=%-8s tools=%s prompt=$%s' % (m_id, ctx, tools_ok, prompt_p))
