"""
Servicio para gestión del período de trial (10 días)
"""
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models import Account
from app.utils.redis_cache import cache_set, cache_delete, invalidate_account_cache
import logging

logger = logging.getLogger(__name__)


class TrialService:
    """Servicio para gestionar trials de cuentas"""
    
    @staticmethod
    def start_trial(account_id, days=None):
        """
        Inicia el período de trial para una cuenta
        
        Args:
            account_id: ID de la cuenta
            days: Días de trial (usa TRIAL_DAYS del config si no se especifica)
            
        Returns:
            dict con success, message y trial_end si exitoso
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': 'Cuenta no encontrada'
                }
            
            # Verificar si ya usó el trial
            if account.trial_used:
                return {
                    'success': False,
                    'message': 'Esta cuenta ya ha utilizado su período de prueba'
                }
            
            # Obtener días de trial
            if days is None:
                days = current_app.config.get('TRIAL_DAYS', 10)
            
            # Iniciar trial
            account.trial_start = datetime.utcnow()
            account.trial_end = account.trial_start + timedelta(days=days)
            account.trial_used = True
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(account_id)
            
            logger.info(f"Trial iniciado para cuenta {account_id}. Expira: {account.trial_end}")
            
            return {
                'success': True,
                'message': f'Período de prueba de {days} días iniciado',
                'trial_end': account.trial_end.isoformat(),
                'days_remaining': days
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al iniciar trial: {e}")
            return {
                'success': False,
                'message': f'Error al iniciar trial: {str(e)}'
            }
    
    @staticmethod
    def check_trial_status(account_id):
        """
        Verifica el estado del trial de una cuenta
        
        Returns:
            dict con información del trial
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'exists': False,
                    'message': 'Cuenta no encontrada'
                }
            
            # Si no ha usado trial
            if not account.trial_used:
                return {
                    'exists': False,
                    'available': True,
                    'message': 'Trial disponible pero no iniciado'
                }
            
            # Si ya usó trial
            is_active = account.is_trial_active()
            days_remaining = 0
            
            if is_active and account.trial_end:
                delta = account.trial_end - datetime.utcnow()
                days_remaining = max(0, delta.days)
            
            return {
                'exists': True,
                'active': is_active,
                'start': account.trial_start.isoformat() if account.trial_start else None,
                'end': account.trial_end.isoformat() if account.trial_end else None,
                'days_remaining': days_remaining,
                'expired': not is_active and account.trial_used
            }
            
        except Exception as e:
            logger.error(f"Error al verificar trial: {e}")
            return {
                'exists': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_days_remaining(account_id):
        """
        Obtiene los días restantes de trial
        
        Returns:
            int: Días restantes (0 si expirado o no existe)
        """
        try:
            account = Account.query.get(account_id)
            
            if not account or not account.is_trial_active():
                return 0
            
            if account.trial_end:
                delta = account.trial_end - datetime.utcnow()
                return max(0, delta.days)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error al obtener días restantes: {e}")
            return 0
    
    @staticmethod
    def extend_trial(account_id, additional_days):
        """
        Extiende el período de trial (solo para admins)
        
        Args:
            account_id: ID de la cuenta
            additional_days: Días adicionales
            
        Returns:
            dict con success y message
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': 'Cuenta no encontrada'
                }
            
            if not account.trial_end:
                return {
                    'success': False,
                    'message': 'No hay trial activo para extender'
                }
            
            # Extender trial
            account.trial_end += timedelta(days=additional_days)
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(account_id)
            
            logger.info(f"Trial extendido para cuenta {account_id} por {additional_days} días")
            
            return {
                'success': True,
                'message': f'Trial extendido por {additional_days} días',
                'new_end': account.trial_end.isoformat()
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al extender trial: {e}")
            return {
                'success': False,
                'message': f'Error al extender trial: {str(e)}'
            }
    
    @staticmethod
    def get_expiring_trials(days_before_expiry=3):
        """
        Obtiene cuentas con trials próximos a expirar
        Útil para enviar notificaciones
        
        Args:
            days_before_expiry: Días antes de expirar para considerar
            
        Returns:
            list: Lista de cuentas con trials próximos a expirar
        """
        try:
            threshold_date = datetime.utcnow() + timedelta(days=days_before_expiry)
            
            expiring_accounts = Account.query.filter(
                Account.trial_used == True,
                Account.trial_end <= threshold_date,
                Account.trial_end > datetime.utcnow(),
                Account.is_active == True
            ).all()
            
            return [
                {
                    'account_id': acc.id,
                    'account_name': acc.name,
                    'trial_end': acc.trial_end.isoformat(),
                    'days_remaining': (acc.trial_end - datetime.utcnow()).days
                }
                for acc in expiring_accounts
            ]
            
        except Exception as e:
            logger.error(f"Error al obtener trials próximos a expirar: {e}")
            return []
    
    @staticmethod
    def convert_trial_to_subscription(account_id):
        """
        Marca que el trial se convirtió en suscripción pagada
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            dict con success y message
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': 'Cuenta no encontrada'
                }
            
            # No hacer nada especial, la suscripción ya está creada
            # Solo invalidar cache para que se refleje el cambio
            invalidate_account_cache(account_id)
            
            logger.info(f"Trial convertido a suscripción para cuenta {account_id}")
            
            return {
                'success': True,
                'message': 'Trial convertido exitosamente a suscripción'
            }
            
        except Exception as e:
            logger.error(f"Error al convertir trial: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }


# Función helper para usar en middleware
def can_access_platform(account_id):
    """
    Verifica si una cuenta puede acceder a la plataforma
    (trial activo O suscripción activa)
    
    Returns:
        tuple: (bool, str) - (puede_acceder, razón_si_no)
    """
    try:
        account = Account.query.get(account_id)
        
        if not account:
            return False, "Cuenta no encontrada"
        
        if not account.is_active:
            return False, "Cuenta desactivada"
        
        # Verificar trial
        if account.is_trial_active():
            return True, "Trial activo"
        
        # Verificar suscripción
        if account.has_active_subscription():
            return True, "Suscripción activa"
        
        # No tiene acceso
        return False, "Trial expirado y sin suscripción activa"
        
    except Exception as e:
        logger.error(f"Error al verificar acceso: {e}")
        return False, f"Error: {str(e)}"