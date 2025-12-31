"""
Rutas de facturación: Planes, suscripciones, pagos
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Subscription, SubscriptionPayment
from app.services.stripe_service import StripeService
from app.services.paypal_service import PayPalService
from app.services.trial_service import TrialService
from app.utils.security import account_admin_required
import logging

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/plans')
@login_required
def plans():
    """Página de planes y precios"""
    # Obtener precios de la configuración
    plan_prices = current_app.config['PLAN_PRICES']
    
    # Estado actual
    current_plan = current_user.account.plan
    has_subscription = current_user.account.has_active_subscription()
    trial_status = TrialService.check_trial_status(current_user.account_id)
    
    return render_template(
        'billing/plans.html',
        plans=plan_prices,
        current_plan=current_plan,
        has_subscription=has_subscription,
        trial_status=trial_status
    )


@billing_bp.route('/subscription')
@login_required
@account_admin_required
def subscription():
    """Página de gestión de suscripción actual"""
    # Obtener suscripción activa
    active_subscription = Subscription.query.filter_by(
        account_id=current_user.account_id,
        is_active=True
    ).order_by(Subscription.created_at.desc()).first()
    
    # Obtener historial de pagos si hay suscripción
    payments = []
    if active_subscription:
        payments = SubscriptionPayment.query.filter_by(
            subscription_id=active_subscription.id
        ).order_by(SubscriptionPayment.payment_date.desc()).limit(10).all()
    
    # Estado del trial
    trial_status = TrialService.check_trial_status(current_user.account_id)
    
    return render_template(
        'billing/subscription.html',
        subscription=active_subscription,
        payments=payments,
        trial_status=trial_status
    )


@billing_bp.route('/subscribe/<gateway>/<plan>', methods=['POST'])
@login_required
@account_admin_required
def subscribe(gateway, plan):
    """Crear nueva suscripción"""
    try:
        # Validar gateway
        if gateway not in ['stripe', 'paypal']:
            flash('Gateway de pago inválido', 'danger')
            return redirect(url_for('billing.plans'))
        
        # Validar plan
        if plan not in ['basic', 'pro', 'enterprise']:
            flash('Plan inválido', 'danger')
            return redirect(url_for('billing.plans'))
        
        # Verificar que no tenga suscripción activa
        if current_user.account.has_active_subscription():
            flash('Ya tienes una suscripción activa', 'warning')
            return redirect(url_for('billing.subscription'))
        
        billing_cycle = request.form.get('billing_cycle', 'monthly')
        
        # Crear suscripción según el gateway
        if gateway == 'stripe':
            stripe_service = StripeService()
            
            # Crear customer si no existe
            customer_result = stripe_service.create_customer(
                account_id=current_user.account_id,
                email=current_user.email,
                name=current_user.account.name
            )
            
            if not customer_result['success']:
                flash(f'Error: {customer_result["message"]}', 'danger')
                return redirect(url_for('billing.plans'))
            
            # Crear suscripción
            sub_result = stripe_service.create_subscription(
                account_id=current_user.account_id,
                plan=plan,
                billing_cycle=billing_cycle
            )
            
            if sub_result['success']:
                flash('Suscripción creada exitosamente con Stripe', 'success')
                return redirect(url_for('billing.subscription'))
            else:
                flash(f'Error al crear suscripción: {sub_result["message"]}', 'danger')
                return redirect(url_for('billing.plans'))
        
        elif gateway == 'paypal':
            paypal_service = PayPalService()
            
            # Crear suscripción
            sub_result = paypal_service.create_subscription(
                account_id=current_user.account_id,
                plan=plan,
                billing_cycle=billing_cycle
            )
            
            if sub_result['success']:
                # Redirigir a PayPal para aprobar
                return redirect(sub_result['approval_url'])
            else:
                flash(f'Error al crear suscripción: {sub_result["message"]}', 'danger')
                return redirect(url_for('billing.plans'))
        
    except Exception as e:
        logger.error(f'Error al crear suscripción: {e}')
        flash('Error al procesar la suscripción', 'danger')
        return redirect(url_for('billing.plans'))


@billing_bp.route('/cancel-subscription', methods=['POST'])
@login_required
@account_admin_required
def cancel_subscription():
    """Cancelar suscripción actual"""
    try:
        # Obtener suscripción activa
        subscription = Subscription.query.filter_by(
            account_id=current_user.account_id,
            is_active=True,
            status='active'
        ).first()
        
        if not subscription:
            flash('No tienes una suscripción activa para cancelar', 'warning')
            return redirect(url_for('billing.subscription'))
        
        # Cancelar según el gateway
        if subscription.gateway == 'stripe':
            stripe_service = StripeService()
            result = stripe_service.cancel_subscription(subscription.subscription_id)
        elif subscription.gateway == 'paypal':
            paypal_service = PayPalService()
            result = paypal_service.cancel_subscription(subscription.subscription_id)
        else:
            flash('Gateway desconocido', 'danger')
            return redirect(url_for('billing.subscription'))
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(f'Error al cancelar: {result["message"]}', 'danger')
        
    except Exception as e:
        logger.error(f'Error al cancelar suscripción: {e}')
        flash('Error al procesar la cancelación', 'danger')
    
    return redirect(url_for('billing.subscription'))


# Rutas de callback de PayPal
@billing_bp.route('/paypal/success')
@login_required
def paypal_success():
    """Callback de éxito de PayPal"""
    try:
        subscription_id = request.args.get('subscription_id')
        
        if not subscription_id:
            flash('ID de suscripción no encontrado', 'danger')
            return redirect(url_for('billing.plans'))
        
        # Activar suscripción
        paypal_service = PayPalService()
        result = paypal_service.activate_subscription(subscription_id)
        
        if result['success']:
            flash('¡Suscripción activada exitosamente!', 'success')
            return redirect(url_for('billing.subscription'))
        else:
            flash(f'Error al activar suscripción: {result["message"]}', 'danger')
            return redirect(url_for('billing.plans'))
        
    except Exception as e:
        logger.error(f'Error en callback de PayPal: {e}')
        flash('Error al procesar la suscripción', 'danger')
        return redirect(url_for('billing.plans'))


@billing_bp.route('/paypal/cancel')
@login_required
def paypal_cancel():
    """Callback de cancelación de PayPal"""
    flash('Suscripción cancelada. Si cambias de opinión, puedes suscribirte en cualquier momento.', 'info')
    return redirect(url_for('billing.plans'))


# Webhooks (sin autenticación de usuario)
@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Webhook de Stripe"""
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        stripe_service = StripeService()
        result = stripe_service.handle_webhook(payload, sig_header)
        
        if result['success']:
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'message': result['message']}), 400
        
    except Exception as e:
        logger.error(f'Error en webhook de Stripe: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@billing_bp.route('/webhooks/paypal', methods=['POST'])
def paypal_webhook():
    """Webhook de PayPal"""
    try:
        headers = request.headers
        body = request.get_json()
        
        paypal_service = PayPalService()
        
        # Verificar firma
        if not paypal_service.verify_webhook(headers, body):
            logger.warning('Firma de webhook de PayPal inválida')
            return jsonify({'status': 'error', 'message': 'Invalid signature'}), 400
        
        # Procesar evento
        result = paypal_service.handle_webhook(body)
        
        if result['success']:
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'message': result['message']}), 400
        
    except Exception as e:
        logger.error(f'Error en webhook de PayPal: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# API Endpoints
@billing_bp.route('/api/payment-history')
@login_required
def api_payment_history():
    """API: Historial de pagos"""
    try:
        # Obtener todas las suscripciones de la cuenta
        subscriptions = Subscription.query.filter_by(
            account_id=current_user.account_id
        ).all()
        
        subscription_ids = [s.id for s in subscriptions]
        
        # Obtener pagos
        payments = SubscriptionPayment.query.filter(
            SubscriptionPayment.subscription_id.in_(subscription_ids)
        ).order_by(SubscriptionPayment.payment_date.desc()).limit(50).all()
        
        payment_data = []
        for payment in payments:
            payment_data.append({
                'id': payment.id,
                'amount': float(payment.amount),
                'status': payment.status,
                'date': payment.payment_date.isoformat(),
                'invoice_id': payment.gateway_invoice_id
            })
        
        return jsonify({
            'success': True,
            'payments': payment_data
        })
        
    except Exception as e:
        logger.error(f'Error en API payment history: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }),