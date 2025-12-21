"""
Authentication Module for Story Telling App
Handles user registration, login, email verification, and password reset.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from flask import Blueprint, request, jsonify, g, current_app, url_for
from flask_mail import Mail, Message

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Initialize Flask-Mail (will be configured in app.py)
mail = Mail()


def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, password_hash):
    """Check password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def generate_token():
    """Generate secure random token"""
    return secrets.token_urlsafe(32)


def get_user_by_email(email):
    """Get user by email"""
    db = get_db()
    return db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()


def get_user_by_id(user_id):
    """Get user by ID"""
    db = get_db()
    return db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()


def get_user_by_token(token):
    """Get user by verification token"""
    db = get_db()
    return db.execute(
        'SELECT * FROM users WHERE verification_token = ? AND verification_expires > ?',
        (token, datetime.now())
    ).fetchone()


def get_current_user():
    """Get current user from session/token"""
    # Check Authorization header for JWT
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        # Simple token validation (in production, use proper JWT)
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE verification_token = ? AND is_active = 1',
            (token,)
        ).fetchone()
        if user:
            return dict(user)
    
    # Check session
    from flask import session
    user_id = session.get('user_id')
    if user_id:
        user = get_user_by_id(user_id)
        if user:
            return dict(user)
    
    return None


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized', 'message': 'Vui lòng đăng nhập'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized', 'message': 'Vui lòng đăng nhập'}), 401
        if not user.get('is_admin'):
            return jsonify({'error': 'Forbidden', 'message': 'Bạn không có quyền truy cập'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def send_verification_email(user_email, token):
    """Send verification email"""
    try:
        verify_url = f"{current_app.config.get('APP_URL', 'http://localhost:5000')}/api/auth/verify/{token}"
        
        msg = Message(
            subject='Xác thực tài khoản - Story Telling App',
            recipients=[user_email],
            html=f'''
            <h2>Chào mừng bạn đến với Story Telling App!</h2>
            <p>Vui lòng click vào link bên dưới để xác thực tài khoản:</p>
            <p><a href="{verify_url}" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Xác thực tài khoản</a></p>
            <p>Hoặc copy link này: {verify_url}</p>
            <p>Link có hiệu lực trong 24 giờ.</p>
            <br>
            <p>Trân trọng,<br>Story Telling App Team</p>
            '''
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send verification email: {e}")
        return False


def send_reset_password_email(user_email, token):
    """Send password reset email"""
    try:
        reset_url = f"{current_app.config.get('APP_URL', 'http://localhost:5000')}/reset-password?token={token}"
        
        msg = Message(
            subject='Đặt lại mật khẩu - Story Telling App',
            recipients=[user_email],
            html=f'''
            <h2>Đặt lại mật khẩu</h2>
            <p>Bạn đã yêu cầu đặt lại mật khẩu. Click vào link bên dưới:</p>
            <p><a href="{reset_url}" style="background: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Đặt lại mật khẩu</a></p>
            <p>Hoặc copy link này: {reset_url}</p>
            <p>Link có hiệu lực trong 1 giờ.</p>
            <p>Nếu bạn không yêu cầu, vui lòng bỏ qua email này.</p>
            <br>
            <p>Trân trọng,<br>Story Telling App Team</p>
            '''
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send reset email: {e}")
        return False


# ==========================================
# API Routes
# ==========================================

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        age = data.get('age')
        country = data.get('country', 'VN')
        
        if not username or not email or not password:
            return jsonify({'error': 'Vui lòng điền đầy đủ thông tin'}), 400
        
        if len(username) < 3:
            return jsonify({'error': 'Tên người dùng phải có ít nhất 3 ký tự'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Mật khẩu phải có ít nhất 6 ký tự'}), 400
        
        if '@' not in email:
            return jsonify({'error': 'Email không hợp lệ'}), 400
        
        db = get_db()
        
        # Check if email already exists
        if get_user_by_email(email):
            return jsonify({'error': 'Email đã được sử dụng'}), 400
        
        # Check if username already exists
        existing_user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            return jsonify({'error': 'Tên người dùng đã được sử dụng'}), 400
        
        # Generate verification token
        verification_token = generate_token()
        verification_expires = datetime.now() + timedelta(hours=24)
        
        # Get role_id from request
        role_id = data.get('role_id')
        
        # Create user
        password_hash = hash_password(password)
        cursor = db.execute('''
            INSERT INTO users (username, email, password_hash, verification_token, verification_expires, age, country, role_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, verification_token, verification_expires, age, country, role_id))
        db.commit()
        
        user_id = cursor.lastrowid
        
        # Send verification email
        email_sent = send_verification_email(email, verification_token)
        
        return jsonify({
            'status': 'ok',
            'message': 'Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản.',
            'email_sent': email_sent,
            'user_id': user_id
        }), 201
        
    except Exception as e:
        print(f"[REGISTER ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Vui lòng nhập email và mật khẩu'}), 400
        
        user = get_user_by_email(email)
        
        if not user:
            return jsonify({'error': 'Email hoặc mật khẩu không đúng'}), 401
        
        if not check_password(password, user['password_hash']):
            return jsonify({'error': 'Email hoặc mật khẩu không đúng'}), 401
        
        if not user['is_active']:
            return jsonify({'error': 'Tài khoản đã bị khóa'}), 403
        
        # Generate session token
        session_token = generate_token()
        
        db = get_db()
        db.execute('''
            UPDATE users SET verification_token = ?, last_login = ?
            WHERE user_id = ?
        ''', (session_token, datetime.now(), user['user_id']))
        db.commit()
        
        # Set session
        from flask import session
        session['user_id'] = user['user_id']
        
        return jsonify({
            'status': 'ok',
            'message': 'Đăng nhập thành công!',
            'token': session_token,
            'user': {
                'user_id': user['user_id'],
                'username': user['username'],
                'email': user['email'],
                'is_verified': bool(user['is_verified']),
                'is_admin': bool(user['is_admin']),
                'age': user['age'],
                'country': user['country'],
                'avatar_url': user['avatar_url']
            }
        })
        
    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    from flask import session
    session.pop('user_id', None)
    return jsonify({'status': 'ok', 'message': 'Đăng xuất thành công!'})


@auth_bp.route('/verify/<token>')
def verify_email(token):
    """Verify email with token"""
    try:
        user = get_user_by_token(token)
        
        if not user:
            return jsonify({'error': 'Link xác thực không hợp lệ hoặc đã hết hạn'}), 400
        
        db = get_db()
        db.execute('''
            UPDATE users SET is_verified = 1, verification_token = NULL, verification_expires = NULL
            WHERE user_id = ?
        ''', (user['user_id'],))
        db.commit()
        
        # Redirect to login page with success message
        from flask import redirect
        return redirect('/login?verified=1')
        
    except Exception as e:
        print(f"[VERIFY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Vui lòng nhập email'}), 400
        
        user = get_user_by_email(email)
        
        if not user:
            return jsonify({'error': 'Email không tồn tại trong hệ thống'}), 404
        
        if user['is_verified']:
            return jsonify({'error': 'Tài khoản đã được xác thực'}), 400
        
        # Generate new token
        verification_token = generate_token()
        verification_expires = datetime.now() + timedelta(hours=24)
        
        db = get_db()
        db.execute('''
            UPDATE users SET verification_token = ?, verification_expires = ?
            WHERE user_id = ?
        ''', (verification_token, verification_expires, user['user_id']))
        db.commit()
        
        # Send email
        email_sent = send_verification_email(email, verification_token)
        
        return jsonify({
            'status': 'ok',
            'message': 'Email xác thực đã được gửi lại!',
            'email_sent': email_sent
        })
        
    except Exception as e:
        print(f"[RESEND ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Vui lòng nhập email'}), 400
        
        user = get_user_by_email(email)
        
        # Always return success to prevent email enumeration
        if not user:
            return jsonify({
                'status': 'ok',
                'message': 'Nếu email tồn tại, bạn sẽ nhận được link đặt lại mật khẩu.'
            })
        
        # Generate reset token
        reset_token = generate_token()
        expires_at = datetime.now() + timedelta(hours=1)
        
        db = get_db()
        db.execute('''
            INSERT INTO password_resets (user_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', (user['user_id'], reset_token, expires_at))
        db.commit()
        
        # Send email
        send_reset_password_email(email, reset_token)
        
        return jsonify({
            'status': 'ok',
            'message': 'Nếu email tồn tại, bạn sẽ nhận được link đặt lại mật khẩu.'
        })
        
    except Exception as e:
        print(f"[FORGOT PASSWORD ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        token = data.get('token', '')
        new_password = data.get('password', '')
        
        if not token or not new_password:
            return jsonify({'error': 'Thiếu thông tin'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'Mật khẩu phải có ít nhất 6 ký tự'}), 400
        
        db = get_db()
        
        # Find valid reset token
        reset = db.execute('''
            SELECT * FROM password_resets 
            WHERE token = ? AND expires_at > ?
        ''', (token, datetime.now())).fetchone()
        
        if not reset:
            return jsonify({'error': 'Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn'}), 400
        
        # Update password
        password_hash = hash_password(new_password)
        db.execute('''
            UPDATE users SET password_hash = ?
            WHERE user_id = ?
        ''', (password_hash, reset['user_id']))
        
        # Delete used token
        db.execute('DELETE FROM password_resets WHERE id = ?', (reset['id'],))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Mật khẩu đã được đặt lại thành công!'
        })
        
    except Exception as e:
        print(f"[RESET PASSWORD ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/me')
@login_required
def get_current_user_info():
    """Get current user info"""
    user = g.current_user
    return jsonify({
        'status': 'ok',
        'user': {
            'user_id': user['user_id'],
            'username': user['username'],
            'email': user['email'],
            'is_verified': bool(user['is_verified']),
            'is_admin': bool(user['is_admin']),
            'age': user['age'],
            'country': user['country'],
            'avatar_url': user['avatar_url'],
            'created_at': user['created_at']
        }
    })


@auth_bp.route('/update-profile', methods=['PUT'])
@login_required
def update_profile():
    """Update user profile"""
    try:
        user = g.current_user
        data = request.get_json()
        
        username = data.get('username', user['username']).strip()
        age = data.get('age', user['age'])
        country = data.get('country', user['country'])
        avatar_url = data.get('avatar_url', user['avatar_url'])
        
        db = get_db()
        
        # Check if username is taken by another user
        existing = db.execute(
            'SELECT * FROM users WHERE username = ? AND user_id != ?',
            (username, user['user_id'])
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Tên người dùng đã được sử dụng'}), 400
        
        db.execute('''
            UPDATE users SET username = ?, age = ?, country = ?, avatar_url = ?
            WHERE user_id = ?
        ''', (username, age, country, avatar_url, user['user_id']))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Cập nhật thông tin thành công!'
        })
        
    except Exception as e:
        print(f"[UPDATE PROFILE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/change-password', methods=['PUT'])
@login_required
def change_password():
    """Change user password"""
    try:
        user = g.current_user
        data = request.get_json()
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Vui lòng nhập đầy đủ thông tin'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'Mật khẩu mới phải có ít nhất 6 ký tự'}), 400
        
        # Verify current password
        db_user = get_user_by_id(user['user_id'])
        if not check_password(current_password, db_user['password_hash']):
            return jsonify({'error': 'Mật khẩu hiện tại không đúng'}), 400
        
        # Update password
        password_hash = hash_password(new_password)
        db = get_db()
        db.execute('''
            UPDATE users SET password_hash = ?
            WHERE user_id = ?
        ''', (password_hash, user['user_id']))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đổi mật khẩu thành công!'
        })
        
    except Exception as e:
        print(f"[CHANGE PASSWORD ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi. Vui lòng thử lại.'}), 500


@auth_bp.route('/roles')
def get_available_roles():
    """Get available roles for registration"""
    try:
        db = get_db()
        roles = db.execute('''
            SELECT role_id, name, description 
            FROM roles 
            WHERE is_active = 1
            ORDER BY role_id ASC
        ''').fetchall()
        
        return jsonify({
            'status': 'ok',
            'roles': [dict(r) for r in roles]
        })
        
    except Exception as e:
        print(f"[GET ROLES ERROR] {e}")
        return jsonify({'status': 'ok', 'roles': []})

