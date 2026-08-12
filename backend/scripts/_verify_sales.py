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

# 1. Mapping in the access module
from app.ai.chat_access import HUMAN_ROLE_TO_AGENT_ROLES
print('=== Sales mapping (backend) ===')
print(' Sales Manager   ->', sorted(HUMAN_ROLE_TO_AGENT_ROLES.get('Sales Manager', [])))
print(' Sales Executive ->', sorted(HUMAN_ROLE_TO_AGENT_ROLES.get('Sales Executive', [])))

# 2. Frontend mapping
import re
fe = open('../frontend/src/lib/agents.ts', encoding='utf-8').read()
print()
print('=== Sales mapping (frontend agents.ts) ===')
for line in fe.splitlines():
    if 'SALES' in line and ':' in line:
        print(' ', line.strip())

# 3. Live DB: roles actually assigned to TechNova users + the sales AI employee
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
e = create_engine(url)
with e.connect() as c:
    print()
    print('=== Live roles in TechNova (sample) ===')
    rows = c.execute(text('''
        SELECT u.email, r.name
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.organization_id = '88f45e8f-73f3-4b9a-b247-a1c826c08311'
        ORDER BY u.email LIMIT 10
    ''')).fetchall()
    for r in rows:
        print('  %-40s -> %s' % (r[0] or '?', r[1]))
    print()
    print('=== AI Sales Assistant (live) ===')
    rows = c.execute(text('''
        SELECT name, role, active FROM ai_employees
        WHERE organization_id = '88f45e8f-73f3-4b9a-b247-a1c826c08311' AND role = 'Sales Assistant'
    ''')).fetchall()
    for r in rows:
        print('  %s | role=%s | active=%s' % (r[0], r[1], r[2]))
