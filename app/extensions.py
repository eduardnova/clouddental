"""
Inicialización de extensiones Flask
Todas las extensiones se crean aquí y se inicializan en __init__.py
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_migrate import Migrate

# Inicializar extensiones (sin app todavía)
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
mail = Mail()
migrate = Migrate()

# Configuración del Login Manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'
login_manager.session_protection = 'strong'


@login_manager.user_loader
def load_user(user_id):
    """
    Callback para cargar usuario desde la sesión
    Se usa cache de Redis si está disponible
    """
    from app.models import User
    from app.utils.redis_cache import cache_get, cache_set
    
    # Intentar obtener del cache
    cache_key = f'user:{user_id}'
    cached_user = cache_get(cache_key)
    
    if cached_user:
        return cached_user
    
    # Si no está en cache, cargar de BD
    user = User.query.get(int(user_id))
    
    if user:
        cache_set(cache_key, user, ttl=300)  # Cache por 5 minutos
    
    return user