"""
Upload handling module for images (story covers, avatars)
"""
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.utils import secure_filename
import sqlite3

upload_bp = Blueprint('upload', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(current_app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

# Import login_required from auth module
from auth import login_required, get_current_user

def save_uploaded_file(file, folder):
    """
    Save uploaded file to specified folder.
    Returns the relative URL path.
    """
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        return None
    
    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    
    # Ensure upload folder exists
    upload_folder = os.path.join(current_app.static_folder, 'uploads', folder)
    os.makedirs(upload_folder, exist_ok=True)
    
    # Save file
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    
    # Return URL path
    return f"/static/uploads/{folder}/{unique_filename}"


@upload_bp.route('/api/upload/story-cover', methods=['POST'])
@login_required
def upload_story_cover():
    """Upload story cover image"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large. Max 5MB'}), 400
    
    url = save_uploaded_file(file, 'stories')
    if url:
        return jsonify({
            'status': 'ok',
            'url': url,
            'message': 'Upload successful'
        })
    else:
        return jsonify({'error': 'Invalid file type'}), 400


@upload_bp.route('/api/upload/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload user avatar"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large. Max 5MB'}), 400
    
    url = save_uploaded_file(file, 'avatars')
    if url:
        # Get current user
        current_user = get_current_user()
        if current_user:
            # Update user's avatar in database
            db = get_db()
            cursor = db.cursor()
            try:
                cursor.execute('''
                    UPDATE users SET avatar = ? WHERE user_id = ?
                ''', (url, current_user['user_id']))
                db.commit()
            except Exception as e:
                # Column might not exist yet
                print(f"Avatar update error: {e}")
        
        return jsonify({
            'status': 'ok',
            'url': url,
            'message': 'Avatar updated'
        })
    else:
        return jsonify({'error': 'Invalid file type'}), 400


@upload_bp.route('/api/upload/image', methods=['POST'])
@login_required
def upload_general_image():
    """General image upload (for editor, etc.)"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    folder = request.form.get('folder', 'general')
    
    # Validate folder name (security)
    allowed_folders = ['stories', 'avatars', 'general']
    if folder not in allowed_folders:
        folder = 'general'
    
    url = save_uploaded_file(file, folder)
    if url:
        return jsonify({
            'status': 'ok',
            'url': url
        })
    else:
        return jsonify({'error': 'Invalid file type'}), 400
