import sqlite3

conn = sqlite3.connect('database/maxek_payroll.db')
c = conn.cursor()
for table in ['subcontractors', 'attendance']:
    print('TABLE', table)
    c.execute(f'PRAGMA table_info({table})')
    for row in c.fetchall():
        print(row)
    print()
conn.close()
