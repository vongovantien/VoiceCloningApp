"""Fix admin password in app.db - the CORRECT database Flask uses"""
import sqlite3
import bcrypt
import os

DATABASE = 'app.db'

print(f"Checking database: {DATABASE}")
print(f"File exists: {os.path.exists(DATABASE)}")

# Generate password hash
password = b'admin123'
password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row

# Check if users table exists
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
if not tables:
    print("\n[ERROR] Table 'users' does not exist in app.db!")
    print("Running schema.sql to create tables...")
    
    # Create schema
    with open('schema.sql', 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    print("Schema created!")

# Check existing admin
user = conn.execute('SELECT * FROM users WHERE email = ?', ('admin@storytelling.app',)).fetchone()
if user:
    print(f"\nExisting admin found in app.db:")
    print(f"  ID: {user['user_id']}")
    print(f"  Email: {user['email']}")
    print(f"  is_admin: {user['is_admin']}")
    
    # Update password
    conn.execute('''
        UPDATE users 
        SET password_hash = ?, is_verified = 1, is_active = 1 
        WHERE email = 'admin@storytelling.app'
    ''', (password_hash,))
    conn.commit()
    print("Password updated!")
else:
    print("\nNo admin found! Creating new admin user...")
    conn.execute('''
        INSERT INTO users (username, email, password_hash, is_verified, is_admin, is_active)
        VALUES (?, ?, ?, 1, 1, 1)
    ''', ('admin', 'admin@storytelling.app', password_hash))
    conn.commit()
    print("Admin created!")

# Verify
user = conn.execute('SELECT user_id, username, email, is_admin, is_verified, is_active, password_hash FROM users WHERE email = ?', ('admin@storytelling.app',)).fetchone()
print(f"\nVerification:")
print(f"  User ID: {user['user_id']}")
print(f"  Username: {user['username']}")
print(f"  Email: {user['email']}")
print(f"  is_admin: {user['is_admin']}")
print(f"  is_verified: {user['is_verified']}")
print(f"  is_active: {user['is_active']}")

# Test password
is_valid = bcrypt.checkpw(b'admin123', user['password_hash'].encode('utf-8'))
print(f"  Password valid: {is_valid}")

conn.close()

print("\n" + "=" * 50)
if is_valid:
    print("SUCCESS! Password fixed in app.db")
    print("Login credentials:")
    print("  Email: admin@storytelling.app")
    print("  Password: admin123")
else:
    print("ERROR: Password verification failed!")
print("=" * 50)
