"""
Configuración de la aplicación Flask SaaS
Incluye configuraciones para desarrollo, testing y producción
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base para todos los entornos"""
    
    # Configuración básica de Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'mysql+pymysql://root:password@localhost/clouddental_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    # Redis Configuration (Optional)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_ENABLED = os.getenv('REDIS_ENABLED', 'True').lower() == 'true'
    CACHE_TTL = 300  # 5 minutos por defecto
    
    # Security
    BCRYPT_LOG_ROUNDS = 12
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Trial Configuration
    TRIAL_DAYS = 10
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@clouddental.com')
    
    # PayPal Configuration
    PAYPAL_MODE = os.getenv('PAYPAL_MODE', 'sandbox')  # sandbox o live
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
    PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')
    PAYPAL_WEBHOOK_ID = os.getenv('PAYPAL_WEBHOOK_ID')
    
    # Stripe Configuration
    STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    # Plan Pricing (en USD)
    PLAN_PRICES = {
        'basic': {
            'monthly': 29.99,
            'yearly': 299.99,
            'stripe_price_id': os.getenv('STRIPE_BASIC_PRICE_ID'),
            'paypal_plan_id': os.getenv('PAYPAL_BASIC_PLAN_ID')
        },
        'pro': {
            'monthly': 79.99,
            'yearly': 799.99,
            'stripe_price_id': os.getenv('STRIPE_PRO_PRICE_ID'),
            'paypal_plan_id': os.getenv('PAYPAL_PRO_PLAN_ID')
        },
        'enterprise': {
            'monthly': 199.99,
            'yearly': 1999.99,
            'stripe_price_id': os.getenv('STRIPE_ENTERPRISE_PRICE_ID'),
            'paypal_plan_id': os.getenv('PAYPAL_ENTERPRISE_PLAN_ID')
        }
    }
    
    # Application Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False
    
    # Sobrescribir configuraciones críticas de seguridad
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY debe estar definida en producción")
    
    # Forzar HTTPS
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


# Mapeo de configuraciones
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Obtiene la configuración basada en el entorno"""
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)