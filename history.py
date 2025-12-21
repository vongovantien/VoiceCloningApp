"""
History and Favorites Module for Story Telling App
Handles listening history and user favorites.
"""

import sqlite3
from flask import Blueprint, request, jsonify, g, current_app

from auth import login_required, get_current_user

history_bp = Blueprint('history', __name__, url_prefix='/api')


def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


# ==========================================
# Listening History Routes
# ==========================================

@history_bp.route('/history')
@login_required
def get_history():
    """Get user's listening history"""
    try:
        user = g.current_user
        db = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        offset = (page - 1) * per_page
        
        history = db.execute('''
            SELECT h.*, s.title, s.summary, s.cover_image, s.country,
                   v.name as voice_name
            FROM listening_history h
            JOIN stories s ON h.story_id = s.story_id
            LEFT JOIN voice_samples v ON h.voice_id = v.sample_id
            WHERE h.user_id = ?
            ORDER BY h.last_listened DESC
            LIMIT ? OFFSET ?
        ''', (user['user_id'], per_page, offset)).fetchall()
        
        # Get total count
        total = db.execute(
            'SELECT COUNT(*) as total FROM listening_history WHERE user_id = ?',
            (user['user_id'],)
        ).fetchone()['total']
        
        return jsonify({
            'status': 'ok',
            'history': [dict(h) for h in history],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        print(f"[GET HISTORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/history', methods=['POST'])
@login_required
def add_to_history():
    """Add or update listening history"""
    try:
        user = g.current_user
        data = request.get_json()
        
        story_id = data.get('story_id')
        voice_id = data.get('voice_id')
        audio_path = data.get('audio_path')
        progress_percent = data.get('progress_percent', 0)
        completed = data.get('completed', False)
        
        if not story_id:
            return jsonify({'error': 'Thiếu story_id'}), 400
        
        db = get_db()
        
        # Check if already in history
        existing = db.execute('''
            SELECT * FROM listening_history 
            WHERE user_id = ? AND story_id = ?
        ''', (user['user_id'], story_id)).fetchone()
        
        if existing:
            # Update existing entry
            db.execute('''
                UPDATE listening_history 
                SET voice_id = COALESCE(?, voice_id),
                    audio_path = COALESCE(?, audio_path),
                    progress_percent = ?,
                    completed = ?,
                    listen_count = listen_count + 1,
                    last_listened = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (voice_id, audio_path, progress_percent, completed, existing['id']))
        else:
            # Create new entry
            db.execute('''
                INSERT INTO listening_history (user_id, story_id, voice_id, audio_path, progress_percent, completed)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user['user_id'], story_id, voice_id, audio_path, progress_percent, completed))
        
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã cập nhật lịch sử'
        })
        
    except Exception as e:
        print(f"[ADD HISTORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/history/<int:history_id>', methods=['PUT'])
@login_required
def update_history_progress(history_id):
    """Update listening progress"""
    try:
        user = g.current_user
        data = request.get_json()
        
        progress_percent = data.get('progress_percent', 0)
        completed = data.get('completed', False)
        
        db = get_db()
        
        # Verify ownership
        history = db.execute(
            'SELECT * FROM listening_history WHERE id = ? AND user_id = ?',
            (history_id, user['user_id'])
        ).fetchone()
        
        if not history:
            return jsonify({'error': 'Không tìm thấy mục lịch sử'}), 404
        
        db.execute('''
            UPDATE listening_history 
            SET progress_percent = ?, completed = ?, last_listened = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (progress_percent, completed, history_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã cập nhật tiến độ'
        })
        
    except Exception as e:
        print(f"[UPDATE PROGRESS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/history/<int:history_id>', methods=['DELETE'])
@login_required
def delete_history_item(history_id):
    """Delete item from history"""
    try:
        user = g.current_user
        db = get_db()
        
        # Verify ownership
        history = db.execute(
            'SELECT * FROM listening_history WHERE id = ? AND user_id = ?',
            (history_id, user['user_id'])
        ).fetchone()
        
        if not history:
            return jsonify({'error': 'Không tìm thấy mục lịch sử'}), 404
        
        db.execute('DELETE FROM listening_history WHERE id = ?', (history_id,))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã xóa khỏi lịch sử'
        })
        
    except Exception as e:
        print(f"[DELETE HISTORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/history/clear', methods=['DELETE'])
@login_required
def clear_history():
    """Clear all listening history"""
    try:
        user = g.current_user
        db = get_db()
        
        db.execute('DELETE FROM listening_history WHERE user_id = ?', (user['user_id'],))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã xóa toàn bộ lịch sử'
        })
        
    except Exception as e:
        print(f"[CLEAR HISTORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Favorites Routes
# ==========================================

@history_bp.route('/favorites')
@login_required
def get_favorites():
    """Get user's favorite stories"""
    try:
        user = g.current_user
        db = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        offset = (page - 1) * per_page
        
        favorites = db.execute('''
            SELECT f.id, f.created_at as favorited_at, 
                   s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites uf WHERE uf.story_id = s.story_id) as favorite_count
            FROM user_favorites f
            JOIN stories s ON f.story_id = s.story_id
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE f.user_id = ? AND s.is_active = 1
            ORDER BY f.created_at DESC
            LIMIT ? OFFSET ?
        ''', (user['user_id'], per_page, offset)).fetchall()
        
        # Get total count
        total = db.execute('''
            SELECT COUNT(*) as total 
            FROM user_favorites f
            JOIN stories s ON f.story_id = s.story_id
            WHERE f.user_id = ? AND s.is_active = 1
        ''', (user['user_id'],)).fetchone()['total']
        
        return jsonify({
            'status': 'ok',
            'favorites': [dict(f) for f in favorites],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        print(f"[GET FAVORITES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/favorites', methods=['POST'])
@login_required
def add_favorite():
    """Add story to favorites"""
    try:
        user = g.current_user
        data = request.get_json()
        
        story_id = data.get('story_id')
        
        if not story_id:
            return jsonify({'error': 'Thiếu story_id'}), 400
        
        db = get_db()
        
        # Check if story exists
        story = db.execute('SELECT * FROM stories WHERE story_id = ? AND is_active = 1', (story_id,)).fetchone()
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        # Check if already favorited
        existing = db.execute(
            'SELECT * FROM user_favorites WHERE user_id = ? AND story_id = ?',
            (user['user_id'], story_id)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Truyện đã có trong danh sách yêu thích'}), 400
        
        db.execute('''
            INSERT INTO user_favorites (user_id, story_id)
            VALUES (?, ?)
        ''', (user['user_id'], story_id))
        db.commit()
        
        # Get updated favorite count
        favorite_count = db.execute(
            'SELECT COUNT(*) as count FROM user_favorites WHERE story_id = ?',
            (story_id,)
        ).fetchone()['count']
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã thêm vào yêu thích!',
            'favorite_count': favorite_count
        })
        
    except Exception as e:
        print(f"[ADD FAVORITE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/favorites/<int:story_id>', methods=['DELETE'])
@login_required
def remove_favorite(story_id):
    """Remove story from favorites"""
    try:
        user = g.current_user
        db = get_db()
        
        # Check if favorited
        existing = db.execute(
            'SELECT * FROM user_favorites WHERE user_id = ? AND story_id = ?',
            (user['user_id'], story_id)
        ).fetchone()
        
        if not existing:
            return jsonify({'error': 'Truyện không có trong danh sách yêu thích'}), 404
        
        db.execute(
            'DELETE FROM user_favorites WHERE user_id = ? AND story_id = ?',
            (user['user_id'], story_id)
        )
        db.commit()
        
        # Get updated favorite count
        favorite_count = db.execute(
            'SELECT COUNT(*) as count FROM user_favorites WHERE story_id = ?',
            (story_id,)
        ).fetchone()['count']
        
        return jsonify({
            'status': 'ok',
            'message': 'Đã xóa khỏi yêu thích!',
            'favorite_count': favorite_count
        })
        
    except Exception as e:
        print(f"[REMOVE FAVORITE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@history_bp.route('/favorites/check/<int:story_id>')
@login_required
def check_favorite(story_id):
    """Check if story is in favorites"""
    try:
        user = g.current_user
        db = get_db()
        
        existing = db.execute(
            'SELECT * FROM user_favorites WHERE user_id = ? AND story_id = ?',
            (user['user_id'], story_id)
        ).fetchone()
        
        return jsonify({
            'status': 'ok',
            'is_favorite': existing is not None
        })
        
    except Exception as e:
        print(f"[CHECK FAVORITE ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Statistics Routes
# ==========================================

@history_bp.route('/stats')
@login_required
def get_user_stats():
    """Get user statistics"""
    try:
        user = g.current_user
        db = get_db()
        
        # Total stories listened
        total_listened = db.execute(
            'SELECT COUNT(*) as count FROM listening_history WHERE user_id = ?',
            (user['user_id'],)
        ).fetchone()['count']
        
        # Completed stories
        completed = db.execute(
            'SELECT COUNT(*) as count FROM listening_history WHERE user_id = ? AND completed = 1',
            (user['user_id'],)
        ).fetchone()['count']
        
        # Favorite count
        favorites = db.execute(
            'SELECT COUNT(*) as count FROM user_favorites WHERE user_id = ?',
            (user['user_id'],)
        ).fetchone()['count']
        
        # Most listened category
        top_category = db.execute('''
            SELECT c.name, COUNT(*) as count
            FROM listening_history h
            JOIN stories s ON h.story_id = s.story_id
            JOIN story_categories c ON s.category_id = c.category_id
            WHERE h.user_id = ?
            GROUP BY c.category_id
            ORDER BY count DESC
            LIMIT 1
        ''', (user['user_id'],)).fetchone()
        
        return jsonify({
            'status': 'ok',
            'stats': {
                'total_listened': total_listened,
                'completed': completed,
                'favorites': favorites,
                'top_category': dict(top_category) if top_category else None
            }
        })
        
    except Exception as e:
        print(f"[GET STATS ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500
