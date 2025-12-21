-- =============================================
-- STORY TELLING APP - DATABASE SCHEMA
-- =============================================

-- =============================================
-- USERS & AUTHENTICATION
-- =============================================

-- Bảng users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT 0,
    is_admin BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    verification_token TEXT,
    verification_expires DATETIME,
    age INTEGER,
    country TEXT DEFAULT 'VN',
    avatar_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    role_id INTEGER REFERENCES roles(role_id)
);

-- Bảng roles (vai trò)
CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    permissions TEXT,  -- JSON permissions
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Token cho reset password
CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =============================================
-- STORY CATEGORIES
-- =============================================

CREATE TABLE IF NOT EXISTS story_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    icon TEXT,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- STORIES
-- =============================================

CREATE TABLE IF NOT EXISTS stories (
    story_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    cover_image TEXT,
    category_id INTEGER,
    country TEXT DEFAULT 'VN',
    min_age INTEGER DEFAULT 0,
    max_age INTEGER DEFAULT 100,
    duration_minutes INTEGER,
    view_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES story_categories(category_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- Tags cho truyện
CREATE TABLE IF NOT EXISTS story_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS story_tag_mapping (
    story_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (story_id, tag_id),
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES story_tags(tag_id) ON DELETE CASCADE
);

-- =============================================
-- VOICE SAMPLES
-- =============================================

CREATE TABLE IF NOT EXISTS voice_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    file_path TEXT NOT NULL,
    ref_text TEXT,
    language TEXT DEFAULT 'vi',
    gender TEXT,
    style TEXT,
    preview_url TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- LISTENING HISTORY
-- =============================================

CREATE TABLE IF NOT EXISTS listening_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    story_id INTEGER NOT NULL,
    voice_id INTEGER,
    audio_path TEXT,
    progress_percent REAL DEFAULT 0,
    completed BOOLEAN DEFAULT 0,
    listen_count INTEGER DEFAULT 1,
    last_listened DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    FOREIGN KEY (voice_id) REFERENCES voice_samples(sample_id)
);

-- =============================================
-- USER PREFERENCES
-- =============================================

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY,
    preferred_voice INTEGER,
    preferred_speed REAL DEFAULT 1.0,
    preferred_country TEXT DEFAULT 'ALL',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (preferred_voice) REFERENCES voice_samples(sample_id)
);

-- =============================================
-- USER FAVORITES
-- =============================================

CREATE TABLE IF NOT EXISTS user_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    story_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, story_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE
);

-- =============================================
-- GENERATED AUDIOS (legacy support)
-- =============================================

CREATE TABLE IF NOT EXISTS generated_audios (
    audio_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    text_input TEXT NOT NULL,
    voice_sample TEXT,
    audio_path TEXT NOT NULL,
    spectrogram_path TEXT,
    duration REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_stories_category ON stories(category_id);
CREATE INDEX IF NOT EXISTS idx_stories_country ON stories(country);
CREATE INDEX IF NOT EXISTS idx_stories_age ON stories(min_age, max_age);
CREATE INDEX IF NOT EXISTS idx_history_user ON listening_history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_story ON listening_history(story_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_story ON user_favorites(story_id);

-- =============================================
-- SAMPLE DATA
-- =============================================

-- Default categories
INSERT OR IGNORE INTO story_categories (name, description, icon, display_order) VALUES
('Cổ tích Việt Nam', 'Truyện cổ tích dân gian Việt Nam', '🇻🇳', 1),
('Cổ tích thế giới', 'Truyện cổ tích nước ngoài', '🌍', 2),
('Thần thoại', 'Truyện thần thoại Hy Lạp, Bắc Âu...', '⚡', 3),
('Ngụ ngôn', 'Truyện ngụ ngôn và bài học cuộc sống', '📚', 4),
('Phiêu lưu', 'Truyện phiêu lưu mạo hiểm', '🗺️', 5),
('Khoa học viễn tưởng', 'Truyện khoa học viễn tưởng', '🚀', 6);

-- Default voice samples
INSERT OR IGNORE INTO voice_samples (name, description, file_path, ref_text, language, gender, style) VALUES
('Giọng đọc tin tức (Nữ)', 'Giọng nữ đọc tin tức rõ ràng, chuyên nghiệp', 'voices/male.mp3', '', 'vi', 'female', 'news'),
('Giọng kể chuyện (Nam)', 'Giọng nam kể chuyện ấm áp, truyền cảm', 'voices/female.mp3', '', 'vi', 'male', 'story');

-- Default roles
INSERT OR IGNORE INTO roles (name, description, permissions, is_active) VALUES
('Quản trị viên', 'Quản trị viên hệ thống - có toàn quyền', '{"manage_users":true,"manage_stories":true,"manage_categories":true,"manage_roles":true}', 1),
('Người dùng', 'Người dùng thông thường', '{}', 1),
('Biên tập viên', 'Quản lý nội dung truyện', '{"manage_stories":true,"manage_categories":true}', 1);

-- Default admin user (password: admin123)
INSERT OR IGNORE INTO users (username, email, password_hash, is_verified, is_admin, role_id) VALUES
('admin', 'admin@storytelling.app', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiGRMHPymqO.', 1, 1, 1);

