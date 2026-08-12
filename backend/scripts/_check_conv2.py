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
oid = '88f45e8f-73f3-4b9a-b247-a1c826c08311'
with e.connect() as c:
    rows = c.execute(text('''SELECT id, title, ai_employee_id, created_at FROM ai_conversations WHERE organization_id = :o ORDER BY created_at DESC LIMIT 10'''), {'o': oid}).fetchall()
    print('conversations in DB:')
    for r in rows:
        print(' -', r.id, '|', r.title, '|', r.ai_employee_id, '|', r.created_at)
    print()
    print('messages in DB (all):')
    msgs = c.execute(text('''SELECT c.title, m.role, left(m.message, 90), m.created_at FROM ai_messages m JOIN ai_conversations c ON c.id = m.conversation_id WHERE c.organization_id = :o ORDER BY m.created_at ASC'''), {'o': oid}).fetchall()
    for m in msgs:
        print(' -', m[0], '|', m[1], '|', repr(m[2]), '|', m[3])
    print()
    print('total messages:', len(msgs))
