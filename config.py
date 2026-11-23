import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-key-change-me")
    DATABASE = os.path.join(BASE_DIR, "pharmacy.db")
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    TESTING = False
    CSRF_ENABLED = os.environ.get("CSRF_ENABLED", "1") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE") == "1"
    MAX_CONTENT_LENGTH = 1024 * 1024


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    CSRF_ENABLED = False
