"""
Admin Module for Story Telling App
Handles admin dashboard, user management, and statistics.
"""

import sqlite3
from flask import Blueprint, request, jsonify, g, current_app, render_template

from auth import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


# ==========================================
# Dashboard Routes
# ==========================================

@admin_bp.route('')
@admin_required
def dashboard():
    """Admin dashboard"""
    return render_template('admin/dashboard.html')


@admin_bp.route('/api/stats')
@admin_required
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        db = get_db()
        
        # Total users
        total_users = db.execute('SELECT COUNT(*) as count FROM users').fetchone()['count']
        
        # Verified users
        verified_users = db.execute(
            'SELECT COUNT(*) as count FROM users WHERE is_verified = 1'
        ).fetchone()['count']
        
        # Total stories
        total_stories = db.execute(
            'SELECT COUNT(*) as count FROM stories WHERE is_active = 1'
        ).fetchone()['count']
        
        # Total listens
        total_listens = db.execute(
            'SELECT SUM(listen_count) as count FROM listening_history'
        ).fetchone()['count'] or 0
        
        # Total favorites
        total_favorites = db.execute(
            'SELECT COUNT(*) as count FROM user_favorites'
        ).fetchone()['count']
        
        # New users today
        new_users_today = db.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE DATE(created_at) = DATE('now')
        ''').fetchone()['count']
        
        # Top 10 popular stories
        popular_stories = db.execute('''
            SELECT s.story_id, s.title, s.cover_image, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count,
                   s.view_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE s.is_active = 1
            ORDER BY favorite_count DESC, s.view_count DESC
            LIMIT 10
        ''').fetchall()
        
        # Recent activity (last 10 listens)
        recent_activity = db.execute('''
            SELECT h.*, u.username, s.title as story_title
            FROM listening_history h
            JOIN users u ON h.user_id = u.user_id
            JOIN stories s ON h.story_id = s.story_id
            ORDER BY h.last_listened DESC
            LIMIT 10
        ''').fetchall()
        
        # Stories by category
        stories_by_category = db.execute('''
            SELECT c.name, COUNT(s.story_id) as count
            FROM story_categories c
            LEFT JOIN stories s ON c.category_id = s.category_id AND s.is_active = 1
            WHERE c.is_active = 1
            GROUP BY c.category_id
            ORDER BY count DESC
        ''').fetchall()
        
        return jsonify({
            'status': 'ok',
            'stats': {
                'total_users': total_users,
                'verified_users': verified_users,
                'total_stories': total_stories,
                'total_listens': total_listens,
                'total_favorites': total_favorites,
                'new_users_today': new_users_today
            },
            'popular_stories': [dict(s) for s in popular_stories],
            'recent_activity': [dict(a) for a in recent_activity],
            'stories_by_category': [dict(c) for c in stories_by_category]
        })
        
    except Exception as e:
        print(f"[ADMIN STATS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# User Management Routes
# ==========================================

@admin_bp.route('/users')
@admin_required
def users_page():
    """Users management page"""
    return render_template('admin/users.html')


@admin_bp.route('/api/users')
@admin_required
def get_all_users():
    """Get all users with pagination and filters"""
    try:
        db = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        status = request.args.get('status')  # active, inactive, verified, unverified
        offset = (page - 1) * per_page
        
        # Build query
        query = '''
            SELECT u.*, 
                   (SELECT COUNT(*) FROM listening_history h WHERE h.user_id = u.user_id) as listen_count,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.user_id = u.user_id) as favorite_count
            FROM users u
            WHERE 1=1
        '''
        params = []
        
        if search:
            query += ' AND (u.username LIKE ? OR u.email LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        if status == 'active':
            query += ' AND u.is_active = 1'
        elif status == 'inactive':
            query += ' AND u.is_active = 0'
        elif status == 'verified':
            query += ' AND u.is_verified = 1'
        elif status == 'unverified':
            query += ' AND u.is_verified = 0'
        
        query += ' ORDER BY u.created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        
        users = db.execute(query, params).fetchall()
        
        # Get total count
        count_query = 'SELECT COUNT(*) as total FROM users WHERE 1=1'
        count_params = []
        
        if search:
            count_query += ' AND (username LIKE ? OR email LIKE ?)'
            count_params.extend([f'%{search}%', f'%{search}%'])
        if status == 'active':
            count_query += ' AND is_active = 1'
        elif status == 'inactive':
            count_query += ' AND is_active = 0'
        elif status == 'verified':
            count_query += ' AND is_verified = 1'
        elif status == 'unverified':
            count_query += ' AND is_verified = 0'
        
        total = db.execute(count_query, count_params).fetchone()['total']
        
        # Remove password_hash from response
        users_data = []
        for user in users:
            user_dict = dict(user)
            user_dict.pop('password_hash', None)
            user_dict.pop('verification_token', None)
            users_data.append(user_dict)
        
        return jsonify({
            'status': 'ok',
            'users': users_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        print(f"[GET USERS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/users/<int:user_id>')
@admin_required
def get_user_detail(user_id):
    """Get user detail"""
    try:
        db = get_db()
        
        user = db.execute('''
            SELECT u.*, 
                   (SELECT COUNT(*) FROM listening_history h WHERE h.user_id = u.user_id) as listen_count,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.user_id = u.user_id) as favorite_count
            FROM users u
            WHERE u.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not user:
            return jsonify({'error': 'Không tìm thấy người dùng'}), 404
        
        user_dict = dict(user)
        user_dict.pop('password_hash', None)
        user_dict.pop('verification_token', None)
        
        # Get recent activity
        recent_history = db.execute('''
            SELECT h.*, s.title as story_title
            FROM listening_history h
            JOIN stories s ON h.story_id = s.story_id
            WHERE h.user_id = ?
            ORDER BY h.last_listened DESC
            LIMIT 10
        ''', (user_id,)).fetchall()
        
        return jsonify({
            'status': 'ok',
            'user': user_dict,
            'recent_history': [dict(h) for h in recent_history]
        })
        
    except Exception as e:
        print(f"[GET USER DETAIL ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status"""
    try:
        db = get_db()
        
        user = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user:
            return jsonify({'error': 'Không tìm thấy người dùng'}), 404
        
        # Don't allow deactivating admin
        if user['is_admin']:
            return jsonify({'error': 'Không thể khóa tài khoản admin'}), 400
        
        new_status = 0 if user['is_active'] else 1
        db.execute('UPDATE users SET is_active = ? WHERE user_id = ?', (new_status, user_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã mở khóa tài khoản' if new_status else 'Đã khóa tài khoản',
            'is_active': bool(new_status)
        })
        
    except Exception as e:
        print(f"[TOGGLE USER STATUS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required  
def toggle_admin_role(user_id):
    """Toggle user admin role"""
    try:
        db = get_db()
        user = g.current_user
        
        # Can't modify own admin status
        if user['user_id'] == user_id:
            return jsonify({'error': 'Không thể thay đổi quyền của chính mình'}), 400
        
        target_user = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not target_user:
            return jsonify({'error': 'Không tìm thấy người dùng'}), 404
        
        new_admin = 0 if target_user['is_admin'] else 1
        db.execute('UPDATE users SET is_admin = ? WHERE user_id = ?', (new_admin, user_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã cấp quyền admin' if new_admin else 'Đã thu hồi quyền admin',
            'is_admin': bool(new_admin)
        })
        
    except Exception as e:
        print(f"[TOGGLE ADMIN ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Story Management Routes
# ==========================================

@admin_bp.route('/stories')
@admin_required
def stories_page():
    """Stories management page"""
    return render_template('admin/stories.html')


@admin_bp.route('/stories/add')
@admin_required
def add_story_page():
    """Add story page"""
    return render_template('admin/story_form.html')


@admin_bp.route('/stories/edit/<int:story_id>')
@admin_required
def edit_story_page(story_id):
    """Edit story page"""
    return render_template('admin/story_form.html', story_id=story_id)


@admin_bp.route('/api/stories/all')
@admin_required
def get_all_stories_admin():
    """Get all stories for admin (including inactive)"""
    try:
        db = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        category_id = request.args.get('category_id', type=int)
        status = request.args.get('status')  # active, inactive
        offset = (page - 1) * per_page
        
        query = '''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count,
                   (SELECT COUNT(*) FROM listening_history h WHERE h.story_id = s.story_id) as listen_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE 1=1
        '''
        params = []
        
        if search:
            query += ' AND (s.title LIKE ? OR s.summary LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        if category_id:
            query += ' AND s.category_id = ?'
            params.append(category_id)
        
        if status == 'active':
            query += ' AND s.is_active = 1'
        elif status == 'inactive':
            query += ' AND s.is_active = 0'
        
        query += ' ORDER BY s.created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        
        stories = db.execute(query, params).fetchall()
        
        # Get total
        count_query = 'SELECT COUNT(*) as total FROM stories s WHERE 1=1'
        count_params = []
        if search:
            count_query += ' AND (s.title LIKE ? OR s.summary LIKE ?)'
            count_params.extend([f'%{search}%', f'%{search}%'])
        if category_id:
            count_query += ' AND s.category_id = ?'
            count_params.append(category_id)
        if status == 'active':
            count_query += ' AND s.is_active = 1'
        elif status == 'inactive':
            count_query += ' AND s.is_active = 0'
        
        total = db.execute(count_query, count_params).fetchone()['total']
        
        return jsonify({
            'status': 'ok',
            'stories': [dict(s) for s in stories],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        print(f"[GET ALL STORIES ADMIN ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/stories')
@admin_required
def get_stories_admin():
    """Get stories for admin with filters"""
    try:
        db = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '').strip()
        category_id = request.args.get('category_id', type=int)
        status = request.args.get('status')
        sort = request.args.get('sort', 'newest')
        offset = (page - 1) * per_page
        
        query = '''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count,
                   (SELECT COALESCE(SUM(h.listen_count), 0) FROM listening_history h WHERE h.story_id = s.story_id) as listen_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE 1=1
        '''
        params = []
        
        if search:
            query += ' AND (s.title LIKE ? OR s.summary LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])
        
        if category_id:
            query += ' AND s.category_id = ?'
            params.append(category_id)
        
        if status == 'active':
            query += ' AND s.is_active = 1'
        elif status == 'inactive':
            query += ' AND s.is_active = 0'
        
        # Sorting
        if sort == 'oldest':
            query += ' ORDER BY s.created_at ASC'
        elif sort == 'views':
            query += ' ORDER BY s.view_count DESC'
        elif sort == 'listens':
            query += ' ORDER BY listen_count DESC'
        elif sort == 'favorites':
            query += ' ORDER BY favorite_count DESC'
        else:  # newest
            query += ' ORDER BY s.created_at DESC'
        
        query += ' LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        
        stories = db.execute(query, params).fetchall()
        
        # Get total
        count_query = 'SELECT COUNT(*) as total FROM stories s WHERE 1=1'
        count_params = []
        if search:
            count_query += ' AND (s.title LIKE ? OR s.summary LIKE ?)'
            count_params.extend([f'%{search}%', f'%{search}%'])
        if category_id:
            count_query += ' AND s.category_id = ?'
            count_params.append(category_id)
        if status == 'active':
            count_query += ' AND s.is_active = 1'
        elif status == 'inactive':
            count_query += ' AND s.is_active = 0'
        
        total = db.execute(count_query, count_params).fetchone()['total']
        
        return jsonify({
            'status': 'ok',
            'stories': [dict(s) for s in stories],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        print(f"[GET STORIES ADMIN ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/stories/<int:story_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_story_status(story_id):
    """Toggle story active status"""
    try:
        db = get_db()
        
        story = db.execute('SELECT * FROM stories WHERE story_id = ?', (story_id,)).fetchone()
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        new_status = 0 if story['is_active'] else 1
        db.execute('UPDATE stories SET is_active = ? WHERE story_id = ?', (new_status, story_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã hiển thị truyện' if new_status else 'Đã ẩn truyện',
            'is_active': bool(new_status)
        })
        
    except Exception as e:
        print(f"[TOGGLE STORY STATUS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/stories', methods=['POST'])
@admin_required
def create_story():
    """Create new story"""
    try:
        data = request.get_json()
        
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        summary = data.get('summary', '')
        category_id = data.get('category_id')
        cover_image = data.get('cover_image', '')
        country = data.get('country', 'VN')
        min_age = data.get('min_age', 3)
        max_age = data.get('max_age', 12)
        duration_minutes = data.get('duration_minutes', 10)
        is_active = data.get('is_active', True)
        
        if not title or not content:
            return jsonify({'error': 'Vui lòng nhập tiêu đề và nội dung'}), 400
        
        db = get_db()
        
        cursor = db.execute('''
            INSERT INTO stories (title, content, summary, category_id, cover_image, country, min_age, max_age, duration_minutes, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, summary, category_id, cover_image, country, min_age, max_age, duration_minutes, 1 if is_active else 0))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Thêm truyện thành công!',
            'story_id': cursor.lastrowid
        }), 201
        
    except Exception as e:
        print(f"[CREATE STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/stories/<int:story_id>', methods=['PUT'])
@admin_required
def update_story(story_id):
    """Update existing story"""
    try:
        db = get_db()
        
        story = db.execute('SELECT * FROM stories WHERE story_id = ?', (story_id,)).fetchone()
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        data = request.get_json()
        
        title = data.get('title', story['title']).strip()
        content = data.get('content', story['content']).strip()
        summary = data.get('summary', story['summary'])
        category_id = data.get('category_id', story['category_id'])
        cover_image = data.get('cover_image', story['cover_image'])
        country = data.get('country', story['country'])
        min_age = data.get('min_age', story['min_age'])
        max_age = data.get('max_age', story['max_age'])
        duration_minutes = data.get('duration_minutes', story['duration_minutes'])
        is_active = data.get('is_active', story['is_active'])
        
        db.execute('''
            UPDATE stories SET 
                title = ?, content = ?, summary = ?, category_id = ?, cover_image = ?,
                country = ?, min_age = ?, max_age = ?, duration_minutes = ?, is_active = ?
            WHERE story_id = ?
        ''', (title, content, summary, category_id, cover_image, country, min_age, max_age, duration_minutes, 1 if is_active else 0, story_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Cập nhật truyện thành công!'
        })
        
    except Exception as e:
        print(f"[UPDATE STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/stories/<int:story_id>', methods=['DELETE'])
@admin_required
def delete_story(story_id):
    """Delete story"""
    try:
        db = get_db()
        
        story = db.execute('SELECT * FROM stories WHERE story_id = ?', (story_id,)).fetchone()
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        db.execute('DELETE FROM stories WHERE story_id = ?', (story_id,))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã xóa truyện'
        })
        
    except Exception as e:
        print(f"[DELETE STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Voice Samples Management
# ==========================================

@admin_bp.route('/api/voices')
@admin_required
def get_all_voices_admin():
    """Get all voice samples for admin"""
    try:
        db = get_db()
        
        voices = db.execute('''
            SELECT * FROM voice_samples
            ORDER BY created_at DESC
        ''').fetchall()
        
        return jsonify({
            'status': 'ok',
            'voices': [dict(v) for v in voices]
        })
        
    except Exception as e:
        print(f"[GET VOICES ADMIN ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/voices', methods=['POST'])
@admin_required
def create_voice_sample():
    """Create new voice sample"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        description = data.get('description', '')
        file_path = data.get('file_path', '').strip()
        ref_text = data.get('ref_text', '')
        language = data.get('language', 'vi')
        gender = data.get('gender')
        style = data.get('style')
        
        if not name or not file_path:
            return jsonify({'error': 'Vui lòng nhập tên và đường dẫn file'}), 400
        
        db = get_db()
        
        cursor = db.execute('''
            INSERT INTO voice_samples (name, description, file_path, ref_text, language, gender, style)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, file_path, ref_text, language, gender, style))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Thêm giọng đọc thành công!',
            'sample_id': cursor.lastrowid
        }), 201
        
    except Exception as e:
        print(f"[CREATE VOICE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Roles Management
# ==========================================

@admin_bp.route('/roles')
@admin_required
def roles_page():
    """Roles management page"""
    return render_template('admin/roles.html')


@admin_bp.route('/api/roles')
@admin_required
def get_all_roles():
    """Get all roles"""
    try:
        db = get_db()
        
        roles = db.execute('''
            SELECT r.*, 
                   (SELECT COUNT(*) FROM users u WHERE u.role_id = r.role_id) as user_count
            FROM roles r
            ORDER BY r.created_at DESC
        ''').fetchall()
        
        return jsonify({
            'status': 'ok',
            'roles': [dict(r) for r in roles]
        })
        
    except Exception as e:
        print(f"[GET ROLES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/roles/<int:role_id>')
@admin_required
def get_role_detail(role_id):
    """Get role detail"""
    try:
        db = get_db()
        
        role = db.execute('SELECT * FROM roles WHERE role_id = ?', (role_id,)).fetchone()
        if not role:
            return jsonify({'error': 'Không tìm thấy vai trò'}), 404
        
        return jsonify({
            'status': 'ok',
            'role': dict(role)
        })
        
    except Exception as e:
        print(f"[GET ROLE DETAIL ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/roles', methods=['POST'])
@admin_required
def create_role():
    """Create new role"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        description = data.get('description', '')
        permissions = data.get('permissions', '{}')
        is_active = data.get('is_active', 1)
        
        if not name:
            return jsonify({'error': 'Vui lòng nhập tên vai trò'}), 400
        
        db = get_db()
        
        # Check duplicate name
        existing = db.execute('SELECT * FROM roles WHERE name = ?', (name,)).fetchone()
        if existing:
            return jsonify({'error': 'Tên vai trò đã tồn tại'}), 400
        
        cursor = db.execute('''
            INSERT INTO roles (name, description, permissions, is_active)
            VALUES (?, ?, ?, ?)
        ''', (name, description, permissions, is_active))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Thêm vai trò thành công!',
            'role_id': cursor.lastrowid
        }), 201
        
    except Exception as e:
        print(f"[CREATE ROLE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/roles/<int:role_id>', methods=['PUT'])
@admin_required
def update_role(role_id):
    """Update role"""
    try:
        db = get_db()
        
        role = db.execute('SELECT * FROM roles WHERE role_id = ?', (role_id,)).fetchone()
        if not role:
            return jsonify({'error': 'Không tìm thấy vai trò'}), 404
        
        data = request.get_json()
        
        name = data.get('name', role['name']).strip()
        description = data.get('description', role['description'])
        permissions = data.get('permissions', role['permissions'])
        is_active = data.get('is_active', role['is_active'])
        
        # Check duplicate name  
        existing = db.execute('SELECT * FROM roles WHERE name = ? AND role_id != ?', (name, role_id)).fetchone()
        if existing:
            return jsonify({'error': 'Tên vai trò đã tồn tại'}), 400
        
        db.execute('''
            UPDATE roles SET name = ?, description = ?, permissions = ?, is_active = ?
            WHERE role_id = ?
        ''', (name, description, permissions, is_active, role_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Cập nhật vai trò thành công!'
        })
        
    except Exception as e:
        print(f"[UPDATE ROLE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/roles/<int:role_id>/toggle', methods=['POST'])
@admin_required
def toggle_role_status(role_id):
    """Toggle role active status"""
    try:
        db = get_db()
        
        role = db.execute('SELECT * FROM roles WHERE role_id = ?', (role_id,)).fetchone()
        if not role:
            return jsonify({'error': 'Không tìm thấy vai trò'}), 404
        
        new_status = 0 if role['is_active'] else 1
        db.execute('UPDATE roles SET is_active = ? WHERE role_id = ?', (new_status, role_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã kích hoạt vai trò' if new_status else 'Đã vô hiệu hóa vai trò',
            'is_active': bool(new_status)
        })
        
    except Exception as e:
        print(f"[TOGGLE ROLE STATUS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/roles/<int:role_id>', methods=['DELETE'])
@admin_required
def delete_role(role_id):
    """Delete role"""
    try:
        db = get_db()
        
        role = db.execute('SELECT * FROM roles WHERE role_id = ?', (role_id,)).fetchone()
        if not role:
            return jsonify({'error': 'Không tìm thấy vai trò'}), 404
        
        # Check if role is in use
        users_with_role = db.execute('SELECT COUNT(*) as count FROM users WHERE role_id = ?', (role_id,)).fetchone()['count']
        if users_with_role > 0:
            return jsonify({'error': f'Không thể xóa vai trò đang được sử dụng bởi {users_with_role} người dùng'}), 400
        
        db.execute('DELETE FROM roles WHERE role_id = ?', (role_id,))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã xóa vai trò'
        })
        
    except Exception as e:
        print(f"[DELETE ROLE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Categories Management
# ==========================================

@admin_bp.route('/categories')
@admin_required
def categories_page():
    """Categories management page"""
    return render_template('admin/categories.html')


@admin_bp.route('/api/categories')
@admin_required
def get_all_categories_admin():
    """Get all categories for admin"""
    try:
        db = get_db()
        
        categories = db.execute('''
            SELECT c.*, 
                   (SELECT COUNT(*) FROM stories s WHERE s.category_id = c.category_id) as story_count
            FROM story_categories c
            ORDER BY c.display_order ASC, c.name ASC
        ''').fetchall()
        
        return jsonify({
            'status': 'ok',
            'categories': [dict(c) for c in categories]
        })
        
    except Exception as e:
        print(f"[GET CATEGORIES ADMIN ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/categories/<int:category_id>')
@admin_required
def get_category_detail(category_id):
    """Get category detail"""
    try:
        db = get_db()
        
        category = db.execute('SELECT * FROM story_categories WHERE category_id = ?', (category_id,)).fetchone()
        if not category:
            return jsonify({'error': 'Không tìm thấy thể loại'}), 404
        
        return jsonify({
            'status': 'ok',
            'category': dict(category)
        })
        
    except Exception as e:
        print(f"[GET CATEGORY DETAIL ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/categories', methods=['POST'])
@admin_required
def create_category():
    """Create new category"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        description = data.get('description', '')
        icon = data.get('icon', '📚')
        display_order = data.get('display_order', 0)
        is_active = data.get('is_active', 1)
        
        if not name:
            return jsonify({'error': 'Vui lòng nhập tên thể loại'}), 400
        
        db = get_db()
        
        # Check duplicate name
        existing = db.execute('SELECT * FROM story_categories WHERE name = ?', (name,)).fetchone()
        if existing:
            return jsonify({'error': 'Tên thể loại đã tồn tại'}), 400
        
        cursor = db.execute('''
            INSERT INTO story_categories (name, description, icon, display_order, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, icon, display_order, is_active))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Thêm thể loại thành công!',
            'category_id': cursor.lastrowid
        }), 201
        
    except Exception as e:
        print(f"[CREATE CATEGORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/categories/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    """Update category"""
    try:
        db = get_db()
        
        category = db.execute('SELECT * FROM story_categories WHERE category_id = ?', (category_id,)).fetchone()
        if not category:
            return jsonify({'error': 'Không tìm thấy thể loại'}), 404
        
        data = request.get_json()
        
        name = data.get('name', category['name']).strip()
        description = data.get('description', category['description'])
        icon = data.get('icon', category['icon'])
        display_order = data.get('display_order', category['display_order'])
        is_active = data.get('is_active', category['is_active'])
        
        # Check duplicate name
        existing = db.execute('SELECT * FROM story_categories WHERE name = ? AND category_id != ?', (name, category_id)).fetchone()
        if existing:
            return jsonify({'error': 'Tên thể loại đã tồn tại'}), 400
        
        db.execute('''
            UPDATE story_categories SET name = ?, description = ?, icon = ?, display_order = ?, is_active = ?
            WHERE category_id = ?
        ''', (name, description, icon, display_order, is_active, category_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Cập nhật thể loại thành công!'
        })
        
    except Exception as e:
        print(f"[UPDATE CATEGORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/categories/<int:category_id>/toggle', methods=['POST'])
@admin_required
def toggle_category_status(category_id):
    """Toggle category active status"""
    try:
        db = get_db()
        
        category = db.execute('SELECT * FROM story_categories WHERE category_id = ?', (category_id,)).fetchone()
        if not category:
            return jsonify({'error': 'Không tìm thấy thể loại'}), 404
        
        new_status = 0 if category['is_active'] else 1
        db.execute('UPDATE story_categories SET is_active = ? WHERE category_id = ?', (new_status, category_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã kích hoạt thể loại' if new_status else 'Đã vô hiệu hóa thể loại',
            'is_active': bool(new_status)
        })
        
    except Exception as e:
        print(f"[TOGGLE CATEGORY STATUS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@admin_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    """Delete category"""
    try:
        db = get_db()
        
        category = db.execute('SELECT * FROM story_categories WHERE category_id = ?', (category_id,)).fetchone()
        if not category:
            return jsonify({'error': 'Không tìm thấy thể loại'}), 404
        
        # Check if category has stories
        stories_count = db.execute('SELECT COUNT(*) as count FROM stories WHERE category_id = ?', (category_id,)).fetchone()['count']
        if stories_count > 0:
            return jsonify({'error': f'Không thể xóa thể loại đang chứa {stories_count} truyện'}), 400
        
        db.execute('DELETE FROM story_categories WHERE category_id = ?', (category_id,))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã xóa thể loại'
        })
        
    except Exception as e:
        print(f"[DELETE CATEGORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500

