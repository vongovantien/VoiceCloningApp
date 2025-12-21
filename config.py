import os
from datetime import timedelta


class Config:
    """Base configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
    
    # Mail Configuration (Gmail SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'your-email@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'your-app-password'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'Story Telling App <your-email@gmail.com>'
    
    # App Settings
    APP_NAME = 'Story Telling App'
    APP_URL = os.environ.get('APP_URL') or 'http://localhost:5000'
    
    # Upload Settings
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Audio Settings
    OUTPUT_DIR = 'static/output'
    VOICE_DIR = 'static/voices'
    
    # Pagination
    STORIES_PER_PAGE = 12
    HISTORY_PER_PAGE = 20
    USERS_PER_PAGE = 20
    
    # Verification
    VERIFICATION_TOKEN_EXPIRES = timedelta(hours=24)
    PASSWORD_RESET_EXPIRES = timedelta(hours=1)


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Override with production values
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DATABASE = ':memory:'


# Config dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV') or 'development'
    return config.get(env, config['default'])
