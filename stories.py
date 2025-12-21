"""
Story Management Module for Story Telling App
Handles CRUD operations for stories, categories, and recommendations.
"""

import sqlite3
from flask import Blueprint, request, jsonify, g, current_app

from auth import login_required, admin_required, get_current_user

stories_bp = Blueprint('stories', __name__, url_prefix='/api/stories')


def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


def story_to_dict(story, include_content=False):
    """Convert story row to dictionary"""
    data = {
        'story_id': story['story_id'],
        'title': story['title'],
        'summary': story['summary'],
        'cover_image': story['cover_image'],
        'category_id': story['category_id'],
        'country': story['country'],
        'min_age': story['min_age'],
        'max_age': story['max_age'],
        'duration_minutes': story['duration_minutes'],
        'view_count': story['view_count'],
        'created_at': story['created_at']
    }
    if include_content:
        data['content'] = story['content']
    return data


# ==========================================
# Category Routes
# ==========================================

@stories_bp.route('/categories')
def get_categories():
    """Get all story categories"""
    try:
        db = get_db()
        categories = db.execute('''
            SELECT c.*, COUNT(s.story_id) as story_count
            FROM story_categories c
            LEFT JOIN stories s ON c.category_id = s.category_id AND s.is_active = 1
            WHERE c.is_active = 1
            GROUP BY c.category_id
            ORDER BY c.display_order, c.name
        ''').fetchall()
        
        return jsonify({
            'status': 'ok',
            'categories': [dict(c) for c in categories]
        })
    except Exception as e:
        print(f"[GET CATEGORIES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Story Routes
# ==========================================

@stories_bp.route('')
def get_stories():
    """Get list of stories with filters"""
    try:
        db = get_db()
        
        # Get query parameters
        category_id = request.args.get('category_id', type=int)
        country = request.args.get('country')
        age = request.args.get('age', type=int)
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        sort_by = request.args.get('sort', 'newest')  # newest, popular, title
        
        # Build query
        query = '''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE s.is_active = 1
        '''
        params = []
        
        if category_id:
            query += ' AND s.category_id = ?'
            params.append(category_id)
        
        if country and country != 'ALL':
            query += ' AND s.country = ?'
            params.append(country)
        
        if age is not None:
            query += ' AND s.min_age <= ? AND s.max_age >= ?'
            params.extend([age, age])
        
        if search:
            query += ' AND (s.title LIKE ? OR s.summary LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term])
        
        # Sort
        if sort_by == 'popular':
            query += ' ORDER BY favorite_count DESC, s.view_count DESC'
        elif sort_by == 'title':
            query += ' ORDER BY s.title ASC'
        else:  # newest
            query += ' ORDER BY s.created_at DESC'
        
        # Get total count
        count_query = query.replace(
            'SELECT s.*, c.name as category_name,',
            'SELECT COUNT(*) as total FROM (SELECT s.story_id FROM stories s LEFT JOIN story_categories c ON s.category_id = c.category_id WHERE s.is_active = 1'
        )
        
        # Pagination
        offset = (page - 1) * per_page
        query += f' LIMIT {per_page} OFFSET {offset}'
        
        stories = db.execute(query, params).fetchall()
        
        # Get total count for pagination
        total_query = '''
            SELECT COUNT(*) as total FROM stories s WHERE s.is_active = 1
        '''
        total_params = []
        
        if category_id:
            total_query += ' AND s.category_id = ?'
            total_params.append(category_id)
        if country and country != 'ALL':
            total_query += ' AND s.country = ?'
            total_params.append(country)
        if age is not None:
            total_query += ' AND s.min_age <= ? AND s.max_age >= ?'
            total_params.extend([age, age])
        if search:
            total_query += ' AND (s.title LIKE ? OR s.summary LIKE ?)'
            total_params.extend([f'%{search}%', f'%{search}%'])
        
        total = db.execute(total_query, total_params).fetchone()['total']
        
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
        print(f"[GET STORIES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@stories_bp.route('/<int:story_id>')
def get_story(story_id):
    """Get single story by ID"""
    try:
        db = get_db()
        
        story = db.execute('''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE s.story_id = ? AND s.is_active = 1
        ''', (story_id,)).fetchone()
        
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        # Increment view count
        db.execute('UPDATE stories SET view_count = view_count + 1 WHERE story_id = ?', (story_id,))
        db.commit()
        
        # Check if user favorited this story
        is_favorite = False
        user = get_current_user()
        if user:
            fav = db.execute(
                'SELECT 1 FROM user_favorites WHERE user_id = ? AND story_id = ?',
                (user['user_id'], story_id)
            ).fetchone()
            is_favorite = fav is not None
        
        story_data = dict(story)
        story_data['is_favorite'] = is_favorite
        
        return jsonify({
            'status': 'ok',
            'story': story_data
        })
        
    except Exception as e:
        print(f"[GET STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@stories_bp.route('/search')
def search_stories():
    """Search stories by title or content"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({'error': 'Vui lòng nhập ít nhất 2 ký tự'}), 400
        
        db = get_db()
        
        stories = db.execute('''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE s.is_active = 1 AND (s.title LIKE ? OR s.summary LIKE ? OR s.content LIKE ?)
            ORDER BY 
                CASE WHEN s.title LIKE ? THEN 1
                     WHEN s.summary LIKE ? THEN 2
                     ELSE 3 END,
                favorite_count DESC
            LIMIT 20
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
        
        return jsonify({
            'status': 'ok',
            'query': query,
            'stories': [dict(s) for s in stories]
        })
        
    except Exception as e:
        print(f"[SEARCH STORIES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@stories_bp.route('/recommended')
def get_recommended_stories():
    """Get recommended stories for user"""
    try:
        db = get_db()
        user = get_current_user()
        
        # Base query
        query = '''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE s.is_active = 1
        '''
        params = []
        
        if user:
            # Filter by user age if available
            if user.get('age'):
                query += ' AND s.min_age <= ? AND s.max_age >= ?'
                params.extend([user['age'], user['age']])
            
            # Filter by country preference
            if user.get('country') and user['country'] != 'ALL':
                # Prioritize but don't exclude
                pass
            
            # Exclude recently listened stories
            query += '''
                AND s.story_id NOT IN (
                    SELECT story_id FROM listening_history 
                    WHERE user_id = ? 
                    ORDER BY last_listened DESC LIMIT 5
                )
            '''
            params.append(user['user_id'])
        
        # Sort by popularity (favorites count), then random for variety
        query += ' ORDER BY favorite_count DESC, RANDOM() LIMIT 10'
        
        stories = db.execute(query, params).fetchall()
        
        return jsonify({
            'status': 'ok',
            'stories': [dict(s) for s in stories]
        })
        
    except Exception as e:
        print(f"[RECOMMENDED STORIES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@stories_bp.route('/popular')
def get_popular_stories():
    """Get most popular stories (by favorites)"""
    try:
        db = get_db()
        limit = request.args.get('limit', 10, type=int)
        
        stories = db.execute('''
            SELECT s.*, c.name as category_name,
                   (SELECT COUNT(*) FROM user_favorites f WHERE f.story_id = s.story_id) as favorite_count
            FROM stories s
            LEFT JOIN story_categories c ON s.category_id = c.category_id
            WHERE s.is_active = 1
            ORDER BY favorite_count DESC, s.view_count DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        
        return jsonify({
            'status': 'ok',
            'stories': [dict(s) for s in stories]
        })
        
    except Exception as e:
        print(f"[POPULAR STORIES ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Admin Story Routes
# ==========================================

@stories_bp.route('', methods=['POST'])
@admin_required
def create_story():
    """Create a new story (admin only)"""
    try:
        data = request.get_json()
        
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        summary = data.get('summary', '').strip()
        cover_image = data.get('cover_image', '')
        category_id = data.get('category_id')
        country = data.get('country', 'VN')
        min_age = data.get('min_age', 0)
        max_age = data.get('max_age', 100)
        duration_minutes = data.get('duration_minutes')
        
        if not title or not content:
            return jsonify({'error': 'Vui lòng nhập tiêu đề và nội dung'}), 400
        
        db = get_db()
        user = g.current_user
        
        cursor = db.execute('''
            INSERT INTO stories (title, content, summary, cover_image, category_id, country, min_age, max_age, duration_minutes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, summary, cover_image, category_id, country, min_age, max_age, duration_minutes, user['user_id']))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Thêm truyện thành công!',
            'story_id': cursor.lastrowid
        }), 201
        
    except Exception as e:
        print(f"[CREATE STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@stories_bp.route('/<int:story_id>', methods=['PUT'])
@admin_required
def update_story(story_id):
    """Update a story (admin only)"""
    try:
        data = request.get_json()
        db = get_db()
        
        # Check if story exists
        story = db.execute('SELECT * FROM stories WHERE story_id = ?', (story_id,)).fetchone()
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        # Update fields
        title = data.get('title', story['title']).strip()
        content = data.get('content', story['content']).strip()
        summary = data.get('summary', story['summary'])
        cover_image = data.get('cover_image', story['cover_image'])
        category_id = data.get('category_id', story['category_id'])
        country = data.get('country', story['country'])
        min_age = data.get('min_age', story['min_age'])
        max_age = data.get('max_age', story['max_age'])
        duration_minutes = data.get('duration_minutes', story['duration_minutes'])
        is_active = data.get('is_active', story['is_active'])
        
        db.execute('''
            UPDATE stories 
            SET title = ?, content = ?, summary = ?, cover_image = ?, 
                category_id = ?, country = ?, min_age = ?, max_age = ?, 
                duration_minutes = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE story_id = ?
        ''', (title, content, summary, cover_image, category_id, country, min_age, max_age, duration_minutes, is_active, story_id))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Cập nhật truyện thành công!'
        })
        
    except Exception as e:
        print(f"[UPDATE STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


@stories_bp.route('/<int:story_id>', methods=['DELETE'])
@admin_required
def delete_story(story_id):
    """Delete a story (admin only) - soft delete"""
    try:
        db = get_db()
        
        story = db.execute('SELECT * FROM stories WHERE story_id = ?', (story_id,)).fetchone()
        if not story:
            return jsonify({'error': 'Không tìm thấy truyện'}), 404
        
        # Soft delete
        db.execute('UPDATE stories SET is_active = 0 WHERE story_id = ?', (story_id,))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Xóa truyện thành công!'
        })
        
    except Exception as e:
        print(f"[DELETE STORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500


# ==========================================
# Admin Category Routes
# ==========================================

@stories_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    """Create a new category (admin only)"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        description = data.get('description', '')
        icon = data.get('icon', '📚')
        display_order = data.get('display_order', 0)
        
        if not name:
            return jsonify({'error': 'Vui lòng nhập tên danh mục'}), 400
        
        db = get_db()
        
        cursor = db.execute('''
            INSERT INTO story_categories (name, description, icon, display_order)
            VALUES (?, ?, ?, ?)
        ''', (name, description, icon, display_order))
        db.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Thêm danh mục thành công!',
            'category_id': cursor.lastrowid
        }), 201
        
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Tên danh mục đã tồn tại'}), 400
    except Exception as e:
        print(f"[CREATE CATEGORY ERROR] {e}")
        return jsonify({'error': 'Đã xảy ra lỗi'}), 500
