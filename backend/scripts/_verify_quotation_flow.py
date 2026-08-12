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

oid = '88f45e8f-73f3-4b9a-b247-a1c826c08311'

# 1. Sales agent tools
from app.ai.agents import resolve_agent
sales = resolve_agent('Sales Assistant')
print('=== Sales Agent allowed_tools ===')
print(sorted(sales.allowed_tools or []))
t = set(sales.allowed_tools or [])
print()
print('Has search_crm?', 'search_crm' in t)
print('Has list_quotations?', 'list_quotations' in t)
print('Has send_quotation_email?', 'send_quotation_email' in t)

# 2. Live data in TechNova
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
e = create_engine(url)
with e.connect() as c:
    print()
    print('=== Customers matching john (TechNova) ===')
    rows = c.execute(text("""SELECT id, name, email, status FROM customers
        WHERE organization_id = :o AND (lower(name) LIKE '%%john%%' OR lower(coalesce(email,'')) LIKE '%%john%%')"""), {'o': oid}).fetchall()
    for r in rows:
        print(' -', r.name, '|', r.email, '|', r.status)
    print()
    print('=== Quotations in TechNova (all) ===')
    rows = c.execute(text("""SELECT q.quotation_number, q.status, q.total, c.name
        FROM quotations q LEFT JOIN customers c ON c.id = q.customer_id
        WHERE q.organization_id = :o ORDER BY q.created_at DESC LIMIT 10"""), {'o': oid}).fetchall()
    for r in rows:
        print(' - %s | status=%s | total=%s | customer=%s' % (r.quotation_number, r.status, r.total, r.name))
    print()
    print('=== Leads named john? ===')
    rows = c.execute(text("""SELECT name, email, status FROM leads
        WHERE organization_id = :o AND (lower(name) LIKE '%%john%%' OR lower(coalesce(email,'')) LIKE '%%john%%')"""), {'o': oid}).fetchall()
    for r in rows:
        print(' -', r.name, '|', r.email, '|', r.status)
