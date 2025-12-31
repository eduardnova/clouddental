"""
Servicio de integración con PayPal
Maneja suscripciones y webhooks
"""
import paypalrestsdk
import requests
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models import Account, Subscription, SubscriptionPayment
from app.utils.redis_cache import invalidate_account_cache
import logging

logger = logging.getLogger(__name__)


class PayPalService:
    """Servicio para gestionar pagos con PayPal"""
    
    def __init__(self):
        """Inicializa PayPal SDK"""
        self.api = paypalrestsdk
        self.api.configure({
            "mode": current_app.config.get('PAYPAL_MODE', 'sandbox'),
            "client_id": current_app.config.get('PAYPAL_CLIENT_ID'),
            "client_secret": current_app.config.get('PAYPAL_CLIENT_SECRET')
        })
    
    def create_subscription(self, account_id, plan, billing_cycle='monthly'):
        """
        Crea una suscripción en PayPal
        
        Args:
            account_id: ID de la cuenta
            plan: Plan (basic, pro, enterprise)
            billing_cycle: monthly o yearly
            
        Returns:
            dict con success, approval_url, subscription_id y message
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': 'Cuenta no encontrada'
                }
            
            # Obtener plan ID de PayPal
            plan_config = current_app.config['PLAN_PRICES'].get(plan, {})
            paypal_plan_id = plan_config.get('paypal_plan_id')
            
            if not paypal_plan_id:
                return {
                    'success': False,
                    'message': f'Plan ID no configurado para plan {plan}'
                }
            
            # Crear suscripción en PayPal
            subscription_data = {
                "plan_id": paypal_plan_id,
                "application_context": {
                    "brand_name": "CloudDental",
                    "locale": "es-ES",
                    "user_action": "SUBSCRIBE_NOW",
                    "return_url": f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/billing/paypal/success",
                    "cancel_url": f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/billing/paypal/cancel"
                },
                "custom_id": str(account_id)
            }
            
            subscription = self.api.Subscription(subscription_data)
            
            if subscription.create():
                # Obtener approval URL
                approval_url = None
                for link in subscription.links:
                    if link.rel == "approve":
                        approval_url = link.href
                        break
                
                if not approval_url:
                    return {
                        'success': False,
                        'message': 'No se pudo obtener URL de aprobación'
                    }
                
                # Guardar en BD con estado pending
                db_subscription = Subscription(
                    account_id=account_id,
                    gateway='paypal',
                    subscription_id=subscription.id,
                    plan=plan,
                    billing_cycle=billing_cycle,
                    status='pending',  # Se actualizará cuando el usuario apruebe
                    start_date=datetime.utcnow(),
                    metadata={
                        'paypal_status': subscription.status,
                        'approval_url': approval_url
                    }
                )
                
                db.session.add(db_subscription)
                db.session.commit()
                
                logger.info(f"Suscripción PayPal creada: {subscription.id} para cuenta {account_id}")
                
                return {
                    'success': True,
                    'subscription_id': subscription.id,
                    'approval_url': approval_url,
                    'message': 'Suscripción creada. Redirigir al usuario para aprobar.'
                }
            else:
                logger.error(f"Error al crear suscripción PayPal: {subscription.error}")
                return {
                    'success': False,
                    'message': f'Error de PayPal: {subscription.error}'
                }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al crear suscripción PayPal: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def activate_subscription(self, subscription_id):
        """
        Activa una suscripción después de que el usuario la apruebe
        
        Args:
            subscription_id: ID de la suscripción en PayPal
            
        Returns:
            dict con success y message
        """
        try:
            # Buscar en BD
            db_subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='paypal'
            ).first()
            
            if not db_subscription:
                return {
                    'success': False,
                    'message': 'Suscripción no encontrada'
                }
            
            # Obtener detalles de PayPal
            subscription = self.api.Subscription.find(subscription_id)
            
            if not subscription:
                return {
                    'success': False,
                    'message': 'No se pudo obtener información de PayPal'
                }
            
            # Actualizar en BD
            db_subscription.status = subscription.status.lower()
            db_subscription.current_period_start = datetime.utcnow()
            
            # Guardar payer ID si está disponible
            if hasattr(subscription, 'subscriber') and hasattr(subscription.subscriber, 'payer_id'):
                account = Account.query.get(db_subscription.account_id)
                if account:
                    account.paypal_payer_id = subscription.subscriber.payer_id
            
            # Actualizar plan de la cuenta
            account = Account.query.get(db_subscription.account_id)
            if account:
                account.plan = db_subscription.plan
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(db_subscription.account_id)
            
            logger.info(f"Suscripción PayPal activada: {subscription_id}")
            
            return {
                'success': True,
                'message': 'Suscripción activada exitosamente'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al activar suscripción: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def cancel_subscription(self, subscription_id, reason='User requested cancellation'):
        """
        Cancela una suscripción en PayPal
        
        Args:
            subscription_id: ID de la suscripción
            reason: Razón de cancelación
            
        Returns:
            dict con success y message
        """
        try:
            # Buscar en BD
            db_subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='paypal'
            ).first()
            
            if not db_subscription:
                return {
                    'success': False,
                    'message': 'Suscripción no encontrada'
                }
            
            # Cancelar en PayPal
            subscription = self.api.Subscription.find(subscription_id)
            
            if subscription.cancel({"reason": reason}):
                # Actualizar en BD
                db_subscription.status = 'canceled'
                db_subscription.canceled_at = datetime.utcnow()
                
                db.session.commit()
                
                # Invalidar cache
                invalidate_account_cache(db_subscription.account_id)
                
                logger.info(f"Suscripción PayPal cancelada: {subscription_id}")
                
                return {
                    'success': True,
                    'message': 'Suscripción cancelada exitosamente'
                }
            else:
                return {
                    'success': False,
                    'message': f'Error de PayPal: {subscription.error}'
                }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al cancelar suscripción: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def verify_webhook(self, headers, body):
        """
        Verifica la firma de un webhook de PayPal
        
        Args:
            headers: Headers del request
            body: Cuerpo del request
            
        Returns:
            bool: True si la firma es válida
        """
        try:
            webhook_id = current_app.config.get('PAYPAL_WEBHOOK_ID')
            
            if not webhook_id:
                logger.warning("PAYPAL_WEBHOOK_ID no configurado")
                return False
            
            # Preparar datos para verificación
            transmission_id = headers.get('PAYPAL-TRANSMISSION-ID')
            transmission_time = headers.get('PAYPAL-TRANSMISSION-TIME')
            cert_url = headers.get('PAYPAL-CERT-URL')
            auth_algo = headers.get('PAYPAL-AUTH-ALGO')
            transmission_sig = headers.get('PAYPAL-TRANSMISSION-SIG')
            
            # Construir request de verificación
            verification_data = {
                "transmission_id": transmission_id,
                "transmission_time": transmission_time,
                "cert_url": cert_url,
                "auth_algo": auth_algo,
                "transmission_sig": transmission_sig,
                "webhook_id": webhook_id,
                "webhook_event": body
            }
            
            # Llamar a API de verificación de PayPal
            mode = current_app.config.get('PAYPAL_MODE', 'sandbox')
            base_url = "https://api.paypal.com" if mode == "live" else "https://api.sandbox.paypal.com"
            
            response = requests.post(
                f"{base_url}/v1/notifications/verify-webhook-signature",
                json=verification_data,
                auth=(
                    current_app.config.get('PAYPAL_CLIENT_ID'),
                    current_app.config.get('PAYPAL_CLIENT_SECRET')
                )
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('verification_status') == 'SUCCESS'
            
            return False
            
        except Exception as e:
            logger.error(f"Error al verificar webhook: {e}")
            return False
    
    def handle_webhook(self, event_data):
        """
        Procesa webhooks de PayPal
        
        Args:
            event_data: Datos del evento
            
        Returns:
            dict con success y message
        """
        try:
            event_type = event_data.get('event_type')
            resource = event_data.get('resource', {})
            
            logger.info(f"Webhook PayPal recibido: {event_type}")
            
            # Procesar según tipo de evento
            if event_type == 'BILLING.SUBSCRIPTION.ACTIVATED':
                return self._handle_subscription_activated(resource)
            
            elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
                return self._handle_subscription_cancelled(resource)
            
            elif event_type == 'PAYMENT.SALE.COMPLETED':
                return self._handle_payment_completed(resource)
            
            elif event_type == 'PAYMENT.SALE.FAILED':
                return self._handle_payment_failed(resource)
            
            else:
                logger.info(f"Evento PayPal no procesado: {event_type}")
                return {
                    'success': True,
                    'message': f'Evento {event_type} recibido pero no procesado'
                }
            
        except Exception as e:
            logger.error(f"Error al procesar webhook: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_subscription_activated(self, resource):
        """Procesa activación de suscripción"""
        try:
            subscription_id = resource.get('id')
            
            return self.activate_subscription(subscription_id)
            
        except Exception as e:
            logger.error(f"Error al procesar activación: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_subscription_cancelled(self, resource):
        """Procesa cancelación de suscripción"""
        try:
            subscription_id = resource.get('id')
            
            db_subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='paypal'
            ).first()
            
            if not db_subscription:
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            db_subscription.status = 'canceled'
            db_subscription.canceled_at = datetime.utcnow()
            
            db.session.commit()
            
            invalidate_account_cache(db_subscription.account_id)
            
            logger.info(f"Suscripción cancelada vía webhook: {subscription_id}")
            
            return {
                'success': True,
                'message': 'Suscripción cancelada'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al procesar cancelación: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_payment_completed(self, resource):
        """Procesa pago completado"""
        try:
            billing_agreement_id = resource.get('billing_agreement_id')
            
            if not billing_agreement_id:
                return {'success': True, 'message': 'No es pago de suscripción'}
            
            db_subscription = Subscription.query.filter_by(
                subscription_id=billing_agreement_id,
                gateway='paypal'
            ).first()
            
            if not db_subscription:
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            # Registrar pago
            payment = SubscriptionPayment(
                subscription_id=db_subscription.id,
                gateway_invoice_id=resource.get('id'),
                amount=float(resource.get('amount', {}).get('total', 0)),
                status='paid',
                payment_date=datetime.utcnow()
            )
            
            db.session.add(payment)
            
            # Asegurar que la suscripción esté activa
            db_subscription.status = 'active'
            
            db.session.commit()
            
            invalidate_account_cache(db_subscription.account_id)
            
            logger.info(f"Pago registrado: ${payment.amount} para suscripción {billing_agreement_id}")
            
            return {
                'success': True,
                'message': 'Pago procesado exitosamente'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al procesar pago: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_payment_failed(self, resource):
        """Procesa pago fallido"""
        try:
            billing_agreement_id = resource.get('billing_agreement_id')
            
            if not billing_agreement_id:
                return {'success': True, 'message': 'No es pago de suscripción'}
            
            db_subscription = Subscription.query.filter_by(
                subscription_id=billing_agreement_id,
                gateway='paypal'
            ).first()
            
            if not db_subscription:
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            # Registrar pago fallido
            payment = SubscriptionPayment(
                subscription_id=db_subscription.id,
                gateway_invoice_id=resource.get('id'),
                amount=float(resource.get('amount', {}).get('total', 0)),
                status='failed',
                payment_date=datetime.utcnow(),
                failure_reason='Payment failed'
            )
            
            db.session.add(payment)
            
            # Actualizar estado de suscripción
            db_subscription.status = 'past_due'
            
            db.session.commit()
            
            invalidate_account_cache(db_subscription.account_id)
            
            logger.warning(f"Pago fallido para suscripción {billing_agreement_id}")
            
            return {
                'success': True,
                'message': 'Pago fallido registrado'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al procesar pago fallido: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }