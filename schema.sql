-- Bảng người dùng
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng giọng mẫu
CREATE TABLE IF NOT EXISTS voice_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lịch sử tạo audio
CREATE TABLE IF NOT EXISTS generated_audios (
    audio_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    sample_id INTEGER,
    text_input TEXT NOT NULL,
    speed REAL DEFAULT 1.0,
    audio_path TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (sample_id) REFERENCES voice_samples(sample_id)
);

-- Bảng cài đặt người dùng
CREATE TABLE IF NOT EXISTS user_settings (
    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    default_voice INTEGER,
    default_language TEXT,
    default_speed REAL DEFAULT 1.0,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (default_voice) REFERENCES voice_samples(sample_id)
);
