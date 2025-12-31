"""
Servicio de integración con Stripe
Maneja suscripciones, pagos y webhooks
"""
import stripe
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models import Account, Subscription, SubscriptionPayment
from app.utils.redis_cache import invalidate_account_cache
import logging

logger = logging.getLogger(__name__)


class StripeService:
    """Servicio para gestionar pagos con Stripe"""
    
    def __init__(self):
        """Inicializa Stripe con la clave secreta"""
        self.stripe = stripe
        self.stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    
    def create_customer(self, account_id, email, name):
        """
        Crea un customer en Stripe
        
        Args:
            account_id: ID de la cuenta
            email: Email del cliente
            name: Nombre del cliente
            
        Returns:
            dict con success, customer_id y message
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': 'Cuenta no encontrada'
                }
            
            # Verificar si ya tiene customer
            if account.stripe_customer_id:
                return {
                    'success': True,
                    'customer_id': account.stripe_customer_id,
                    'message': 'Customer ya existe'
                }
            
            # Crear customer en Stripe
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata={
                    'account_id': account_id
                }
            )
            
            # Guardar customer ID
            account.stripe_customer_id = customer.id
            db.session.commit()
            
            logger.info(f"Customer Stripe creado: {customer.id} para cuenta {account_id}")
            
            return {
                'success': True,
                'customer_id': customer.id,
                'message': 'Customer creado exitosamente'
            }
            
        except stripe.error.StripeError as e:
            db.session.rollback()
            logger.error(f"Error de Stripe: {e}")
            return {
                'success': False,
                'message': f'Error de Stripe: {str(e)}'
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al crear customer: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def create_subscription(self, account_id, plan, billing_cycle='monthly'):
        """
        Crea una suscripción en Stripe
        
        Args:
            account_id: ID de la cuenta
            plan: Plan (basic, pro, enterprise)
            billing_cycle: monthly o yearly
            
        Returns:
            dict con success, subscription_id y message
        """
        try:
            account = Account.query.get(account_id)
            
            if not account:
                return {
                    'success': False,
                    'message': 'Cuenta no encontrada'
                }
            
            # Verificar que tenga customer ID
            if not account.stripe_customer_id:
                return {
                    'success': False,
                    'message': 'Primero debe crear un customer en Stripe'
                }
            
            # Obtener price ID del plan
            plan_config = current_app.config['PLAN_PRICES'].get(plan, {})
            price_id = plan_config.get('stripe_price_id')
            
            if not price_id:
                return {
                    'success': False,
                    'message': f'Price ID no configurado para plan {plan}'
                }
            
            # Crear suscripción en Stripe
            stripe_subscription = self.stripe.Subscription.create(
                customer=account.stripe_customer_id,
                items=[{'price': price_id}],
                metadata={
                    'account_id': account_id,
                    'plan': plan,
                    'billing_cycle': billing_cycle
                }
            )
            
            # Guardar en base de datos
            subscription = Subscription(
                account_id=account_id,
                gateway='stripe',
                subscription_id=stripe_subscription.id,
                plan=plan,
                billing_cycle=billing_cycle,
                status=stripe_subscription.status,
                start_date=datetime.fromtimestamp(stripe_subscription.created),
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                metadata={
                    'stripe_status': stripe_subscription.status,
                    'customer_id': account.stripe_customer_id
                }
            )
            
            db.session.add(subscription)
            
            # Actualizar plan de la cuenta
            account.plan = plan
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(account_id)
            
            logger.info(f"Suscripción Stripe creada: {stripe_subscription.id} para cuenta {account_id}")
            
            return {
                'success': True,
                'subscription_id': stripe_subscription.id,
                'message': 'Suscripción creada exitosamente',
                'subscription': subscription
            }
            
        except stripe.error.StripeError as e:
            db.session.rollback()
            logger.error(f"Error de Stripe: {e}")
            return {
                'success': False,
                'message': f'Error de Stripe: {str(e)}'
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al crear suscripción: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def cancel_subscription(self, subscription_id):
        """
        Cancela una suscripción en Stripe
        
        Args:
            subscription_id: ID de la suscripción en Stripe
            
        Returns:
            dict con success y message
        """
        try:
            # Buscar suscripción en BD
            subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='stripe'
            ).first()
            
            if not subscription:
                return {
                    'success': False,
                    'message': 'Suscripción no encontrada'
                }
            
            # Cancelar en Stripe (al final del período)
            stripe_subscription = self.stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            
            # Actualizar en BD
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(subscription.account_id)
            
            logger.info(f"Suscripción Stripe cancelada: {subscription_id}")
            
            return {
                'success': True,
                'message': 'Suscripción cancelada. Se mantendrá activa hasta el final del período de facturación.',
                'cancels_at': datetime.fromtimestamp(stripe_subscription.current_period_end).isoformat()
            }
            
        except stripe.error.StripeError as e:
            db.session.rollback()
            logger.error(f"Error de Stripe: {e}")
            return {
                'success': False,
                'message': f'Error de Stripe: {str(e)}'
            }
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al cancelar suscripción: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def handle_webhook(self, payload, sig_header):
        """
        Procesa webhooks de Stripe
        
        Args:
            payload: Cuerpo del webhook
            sig_header: Firma del webhook
            
        Returns:
            dict con success y message
        """
        try:
            webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
            
            # Verificar firma
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            
            event_type = event['type']
            logger.info(f"Webhook Stripe recibido: {event_type}")
            
            # Procesar según tipo de evento
            if event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event['data']['object'])
            
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(event['data']['object'])
            
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event['data']['object'])
            
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event['data']['object'])
            
            else:
                logger.info(f"Evento Stripe no procesado: {event_type}")
                return {
                    'success': True,
                    'message': f'Evento {event_type} recibido pero no procesado'
                }
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Error de firma de webhook: {e}")
            return {
                'success': False,
                'message': 'Firma de webhook inválida'
            }
        except Exception as e:
            logger.error(f"Error al procesar webhook: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_payment_succeeded(self, invoice):
        """Procesa pago exitoso"""
        try:
            subscription_id = invoice.get('subscription')
            
            if not subscription_id:
                return {'success': True, 'message': 'No es pago de suscripción'}
            
            # Buscar suscripción
            subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='stripe'
            ).first()
            
            if not subscription:
                logger.warning(f"Suscripción no encontrada: {subscription_id}")
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            # Registrar pago
            payment = SubscriptionPayment(
                subscription_id=subscription.id,
                gateway_invoice_id=invoice['id'],
                amount=invoice['amount_paid'] / 100,  # Convertir de centavos
                status='paid',
                payment_date=datetime.fromtimestamp(invoice['created'])
            )
            
            db.session.add(payment)
            
            # Actualizar estado de suscripción
            subscription.status = 'active'
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(subscription.account_id)
            
            logger.info(f"Pago registrado: ${payment.amount} para suscripción {subscription_id}")
            
            return {
                'success': True,
                'message': 'Pago procesado exitosamente'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al procesar pago exitoso: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_payment_failed(self, invoice):
        """Procesa pago fallido"""
        try:
            subscription_id = invoice.get('subscription')
            
            if not subscription_id:
                return {'success': True, 'message': 'No es pago de suscripción'}
            
            subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='stripe'
            ).first()
            
            if not subscription:
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            # Registrar pago fallido
            payment = SubscriptionPayment(
                subscription_id=subscription.id,
                gateway_invoice_id=invoice['id'],
                amount=invoice['amount_due'] / 100,
                status='failed',
                payment_date=datetime.fromtimestamp(invoice['created']),
                failure_reason=invoice.get('last_finalization_error', {}).get('message', 'Pago rechazado')
            )
            
            db.session.add(payment)
            
            # Actualizar estado de suscripción
            subscription.status = 'past_due'
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(subscription.account_id)
            
            logger.warning(f"Pago fallido para suscripción {subscription_id}")
            
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
    
    def _handle_subscription_updated(self, subscription_data):
        """Procesa actualización de suscripción"""
        try:
            subscription_id = subscription_data['id']
            
            subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='stripe'
            ).first()
            
            if not subscription:
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            # Actualizar datos
            subscription.status = subscription_data['status']
            subscription.current_period_start = datetime.fromtimestamp(subscription_data['current_period_start'])
            subscription.current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
            
            if subscription_data.get('canceled_at'):
                subscription.canceled_at = datetime.fromtimestamp(subscription_data['canceled_at'])
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(subscription.account_id)
            
            logger.info(f"Suscripción actualizada: {subscription_id}")
            
            return {
                'success': True,
                'message': 'Suscripción actualizada'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al actualizar suscripción: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _handle_subscription_deleted(self, subscription_data):
        """Procesa eliminación de suscripción"""
        try:
            subscription_id = subscription_data['id']
            
            subscription = Subscription.query.filter_by(
                subscription_id=subscription_id,
                gateway='stripe'
            ).first()
            
            if not subscription:
                return {'success': False, 'message': 'Suscripción no encontrada'}
            
            # Marcar como cancelada
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            subscription.is_active = False
            
            db.session.commit()
            
            # Invalidar cache
            invalidate_account_cache(subscription.account_id)
            
            logger.info(f"Suscripción eliminada: {subscription_id}")
            
            return {
                'success': True,
                'message': 'Suscripción eliminada'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al eliminar suscripción: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }