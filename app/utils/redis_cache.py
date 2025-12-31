"""
Sistema de caché con Redis y fallback a memoria local
Detecta automáticamente si Redis está disponible
"""
import json
import pickle
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Variable global para controlar si Redis está disponible
_redis_available = False
_redis_client = None
_memory_cache = {}  # Fallback: diccionario en memoria


def init_redis(app):
    """
    Inicializa Redis si está disponible y configurado
    Returns: True si Redis está disponible, False si usa fallback
    """
    global _redis_available, _redis_client
    
    if not app.config.get('REDIS_ENABLED', False):
        logger.info("Redis deshabilitado en configuración. Usando cache en memoria.")
        return False
    
    try:
        import redis
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Test de conexión
        _redis_client.ping()
        _redis_available = True
        logger.info(f"✓ Redis conectado exitosamente: {redis_url}")
        return True
        
    except ImportError:
        logger.warning("⚠ Módulo redis no instalado. Usando cache en memoria.")
        _redis_available = False
        return False
        
    except Exception as e:
        logger.warning(f"⚠ No se pudo conectar a Redis: {e}. Usando cache en memoria.")
        _redis_available = False
        return False


def is_redis_available():
    """Verifica si Redis está disponible"""
    return _redis_available


def cache_set(key, value, ttl=300):
    """
    Guarda un valor en cache
    Args:
        key: Clave del cache
        value: Valor a guardar (cualquier tipo serializable)
        ttl: Time to live en segundos (default: 5 minutos)
    """
    try:
        if _redis_available and _redis_client:
            # Usar Redis
            serialized = json.dumps(value, default=str)
            _redis_client.setex(key, ttl, serialized)
            logger.debug(f"Cache SET (Redis): {key}")
        else:
            # Usar memoria local
            expiry = datetime.utcnow() + timedelta(seconds=ttl)
            _memory_cache[key] = {
                'value': value,
                'expiry': expiry
            }
            logger.debug(f"Cache SET (Memory): {key}")
        return True
        
    except Exception as e:
        logger.error(f"Error al guardar en cache: {e}")
        return False


def cache_get(key):
    """
    Obtiene un valor del cache
    Returns: Valor si existe y no ha expirado, None en caso contrario
    """
    try:
        if _redis_available and _redis_client:
            # Usar Redis
            data = _redis_client.get(key)
            if data:
                logger.debug(f"Cache HIT (Redis): {key}")
                return json.loads(data)
            logger.debug(f"Cache MISS (Redis): {key}")
            return None
        else:
            # Usar memoria local
            if key in _memory_cache:
                cached = _memory_cache[key]
                if datetime.utcnow() < cached['expiry']:
                    logger.debug(f"Cache HIT (Memory): {key}")
                    return cached['value']
                else:
                    # Expirado, eliminar
                    del _memory_cache[key]
                    logger.debug(f"Cache EXPIRED (Memory): {key}")
            logger.debug(f"Cache MISS (Memory): {key}")
            return None
            
    except Exception as e:
        logger.error(f"Error al leer cache: {e}")
        return None


def cache_delete(key):
    """Elimina una clave del cache"""
    try:
        if _redis_available and _redis_client:
            _redis_client.delete(key)
            logger.debug(f"Cache DELETE (Redis): {key}")
        else:
            if key in _memory_cache:
                del _memory_cache[key]
                logger.debug(f"Cache DELETE (Memory): {key}")
        return True
        
    except Exception as e:
        logger.error(f"Error al eliminar del cache: {e}")
        return False


def cache_clear():
    """Limpia todo el cache"""
    try:
        if _redis_available and _redis_client:
            _redis_client.flushdb()
            logger.info("Cache limpiado (Redis)")
        else:
            _memory_cache.clear()
            logger.info("Cache limpiado (Memory)")
        return True
        
    except Exception as e:
        logger.error(f"Error al limpiar cache: {e}")
        return False


def cache_pattern_delete(pattern):
    """
    Elimina todas las claves que coincidan con un patrón
    Args:
        pattern: Patrón de búsqueda (ej: 'user:*')
    """
    try:
        if _redis_available and _redis_client:
            keys = _redis_client.keys(pattern)
            if keys:
                _redis_client.delete(*keys)
                logger.debug(f"Cache DELETE pattern (Redis): {pattern} ({len(keys)} keys)")
        else:
            # En memoria, filtrar por prefijo
            prefix = pattern.replace('*', '')
            keys_to_delete = [k for k in _memory_cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del _memory_cache[key]
            logger.debug(f"Cache DELETE pattern (Memory): {pattern} ({len(keys_to_delete)} keys)")
        return True
        
    except Exception as e:
        logger.error(f"Error al eliminar patrón del cache: {e}")
        return False


def cached(ttl=300, key_prefix=''):
    """
    Decorador para cachear resultados de funciones
    
    Usage:
        @cached(ttl=600, key_prefix='user_data')
        def get_user_data(user_id):
            # ... expensive operation
            return data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de cache
            cache_key = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            
            # Intentar obtener del cache
            result = cache_get(cache_key)
            if result is not None:
                return result
            
            # Si no está en cache, ejecutar función
            result = func(*args, **kwargs)
            
            # Guardar en cache
            cache_set(cache_key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator


def invalidate_user_cache(user_id):
    """Invalida todo el cache relacionado con un usuario"""
    patterns = [
        f'user:{user_id}',
        f'user_permissions:{user_id}',
        f'user_subscription:{user_id}'
    ]
    for pattern in patterns:
        cache_delete(pattern)


def invalidate_account_cache(account_id):
    """Invalida todo el cache relacionado con una cuenta"""
    cache_pattern_delete(f'account:{account_id}:*')


# Función helper para cache de subscripción
def get_subscription_status_cached(account_id):
    """
    Obtiene el estado de suscripción con cache
    """
    cache_key = f'subscription_status:{account_id}'
    
    status = cache_get(cache_key)
    if status is not None:
        return status
    
    # Cargar desde BD
    from app.models import Account
    account = Account.query.get(account_id)
    
    if not account:
        return None
    
    status = {
        'can_access': account.can_access_features(),
        'is_trial': account.is_trial_active(),
        'has_subscription': account.has_active_subscription(),
        'plan': account.plan
    }
    
    # Cachear por 2 minutos
    cache_set(cache_key, status, ttl=120)
    
    return status