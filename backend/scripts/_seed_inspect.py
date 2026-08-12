import os
from sqlalchemy import create_engine, text

def load_env(path):
    if not os.path.exists(path): return
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip(chr(34)).strip(chr(39)))

load_env('.env')
url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
e = create_engine(url)
oid = '88f45e8f-73f3-4b9a-b247-a1c826c08311'
with e.connect() as c:
    print('=== org users ===')
    rows = c.execute(text('''
        SELECT u.id, u.email, u.full_name, array_agg(r.name) as roles
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE u.organization_id = :o
        GROUP BY u.id, u.email, u.full_name
    '''), {'o': oid}).fetchall()
    for r in rows:
        print(' -', r.email, '|', r.full_name, '|', r.roles)
    print()
    print('=== table counts (org) ===')
    for t in ['customers','leads','quotations','deals','quotation_items','products','pipelines']:
        try:
            n = c.execute(text(f'SELECT COUNT(*) FROM {t} WHERE organization_id = :o'), {'o': oid}).scalar()
            print(f' - {t}: {n}')
        except Exception as ex:
            print(f' - {t}: ERROR {ex}')
    print()
    for t in ['customers','leads','quotations','quotation_items']:
        cols = [r[0] for r in c.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position")).fetchall()]
        print(f'{t} columns:', cols)
