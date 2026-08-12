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
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
e = create_engine(url)
with e.connect() as c:
    rows = c.execute(text("""SELECT name, role, model FROM ai_employees
        WHERE organization_id = '88f45e8f-73f3-4b9a-b247-a1c826c08311' ORDER BY created_at LIMIT 15""")).fetchall()
    for r in rows:
        print('  %-28s | %-22s | model=%s' % (r.name, r.role, r.model))
