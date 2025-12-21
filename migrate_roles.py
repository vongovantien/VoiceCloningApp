import sqlite3

conn = sqlite3.connect('app.db')
c = conn.cursor()

# Create roles table
c.execute('''
CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    permissions TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Add role_id column to users if not exists
try:
    c.execute('ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(role_id)')
except:
    print('role_id column already exists')

# Insert default roles
c.execute('''
INSERT OR IGNORE INTO roles (name, description, permissions, is_active) VALUES
('Quản trị viên', 'Quản trị viên hệ thống - có toàn quyền', '{"manage_users":true,"manage_stories":true,"manage_categories":true,"manage_roles":true}', 1)
''')

c.execute('''
INSERT OR IGNORE INTO roles (name, description, permissions, is_active) VALUES
('Người dùng', 'Người dùng thông thường', '{}', 1)
''')

c.execute('''
INSERT OR IGNORE INTO roles (name, description, permissions, is_active) VALUES
('Biên tập viên', 'Quản lý nội dung truyện', '{"manage_stories":true,"manage_categories":true}', 1)
''')

conn.commit()
print('Migration completed!')

# Check tables
c.execute('SELECT name FROM sqlite_master WHERE type="table"')
print('Tables:', [t[0] for t in c.fetchall()])

# Check roles
c.execute('SELECT * FROM roles')
for row in c.fetchall():
    print('Role:', row)

conn.close()
