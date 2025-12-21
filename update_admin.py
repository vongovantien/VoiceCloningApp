"""Update admin password with correct bcrypt hash"""
import sqlite3
import bcrypt

# Generate new password hash
password = b'admin123'
password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

# Update in database
conn = sqlite3.connect('stories.db')
conn.execute('''
    UPDATE users SET password_hash = ?, is_verified = 1, is_active = 1
    WHERE username = 'admin'
''', (password_hash,))
conn.commit()

# Verify
result = conn.execute('SELECT user_id, username, email, is_admin, is_verified, is_active FROM users WHERE username = ?', ('admin',)).fetchone()
conn.close()

print("=" * 50)
print("Admin account updated successfully!")
print("=" * 50)
print(f"User ID:    {result[0]}")
print(f"Username:   {result[1]}")
print(f"Email:      {result[2]}")
print(f"Is Admin:   {result[3]}")
print(f"Is Verified: {result[4]}")
print(f"Is Active:  {result[5]}")
print("=" * 50)
print("Login credentials:")
print("  Email:    admin@storytelling.app")
print("  Password: admin123")
print("=" * 50)
