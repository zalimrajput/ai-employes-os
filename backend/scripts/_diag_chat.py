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
    print('=== conversations ===')
    rows = c.execute(text('''SELECT id, title, ai_employee_id, created_at FROM ai_conversations WHERE organization_id = :o ORDER BY created_at DESC LIMIT 8'''), {'o': oid}).fetchall()
    for r in rows:
        print(' -', r.id, '|', r.title, '|', r.ai_employee_id, '|', r.created_at)
    print()
    print('=== messages in latest convs ===')
    for r in rows[:3]:
        print('--- conv', r.title, '---')
        msgs = c.execute(text('''SELECT role, message, created_at FROM ai_messages WHERE conversation_id = :c ORDER BY created_at'''), {'c': r.id}).fetchall()
        for m in msgs:
            print('  [', m.role, ']', (m.message or '')[:150].replace(chr(10), ' '))
    print()
    print('=== reminders created recently ===')
    for rr in c.execute(text('''SELECT r.target_type, r.message, r.remind_at, u.email FROM reminders r LEFT JOIN users u ON u.id = r.user_id WHERE r.organization_id = :o ORDER BY r.created_at DESC LIMIT 5'''), {'o': oid}).fetchall():
        print(' -', rr.target_type, '|', (rr.message or '')[:80], '|', rr.remind_at, '|', rr.email)
    print()
    print('=== ai_memory recent ===')
    for mm in c.execute(text('''SELECT employee_id, content FROM ai_memory WHERE organization_id = :o ORDER BY created_at DESC LIMIT 5'''), {'o': oid}).fetchall():
        print(' -', mm.employee_id, '|', (mm.content or '')[:100])
