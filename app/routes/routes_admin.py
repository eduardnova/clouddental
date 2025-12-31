"""
Rutas de administración de plataforma (solo platform_admin)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from app.extensions import db
from app.models import Account, User, Subscription, SubscriptionPayment, SupportTicket, AuditLog
from app.utils.security import admin_required
from app.services.trial_service import TrialService
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Dashboard principal de administración"""
    try:
        # Estadísticas generales
        total_accounts = Account.query.filter_by(is_active=True).count()
        total_users = User.query.filter_by(is_active=True).count()
        
        # Suscripciones activas
        active_subscriptions = Subscription.query.filter_by(
            status='active',
            is_active=True
        ).count()
        
        # Cuentas en trial
        trial_accounts = Account.query.filter(
            Account.trial_used == True,
            Account.trial_end > datetime.utcnow(),
            Account.is_active == True
        ).count()
        
        # Ingresos del mes actual
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue = db.session.query(func.sum(SubscriptionPayment.amount)).filter(
            SubscriptionPayment.status == 'paid',
            SubscriptionPayment.payment_date >= current_month_start
        ).scalar() or 0
        
        # Distribución por planes
        plan_distribution = db.session.query(
            Account.plan,
            func.count(Account.id).label('count')
        ).filter(Account.is_active == True).group_by(Account.plan).all()
        
        # Tickets de soporte abiertos
        open_tickets = SupportTicket.query.filter_by(status='open').count()
        
        # Cuentas recientes (últimos 7 días)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_accounts = Account.query.filter(
            Account.created_at >= week_ago
        ).order_by(desc(Account.created_at)).limit(10).all()
        
        return render_template(
            'admin/dashboard.html',
            total_accounts=total_accounts,
            total_users=total_users,
            active_subscriptions=active_subscriptions,
            trial_accounts=trial_accounts,
            monthly_revenue=float(monthly_revenue),
            plan_distribution=dict(plan_distribution),
            open_tickets=open_tickets,
            recent_accounts=recent_accounts
        )
        
    except Exception as e:
        logger.error(f'Error en dashboard admin: {e}')
        flash('Error al cargar el dashboard', 'danger')
        return render_template('admin/dashboard.html')


@admin_bp.route('/accounts')
@login_required
@admin_required
def accounts():
    """Lista de todas las cuentas"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtros
        plan = request.args.get('plan')
        status = request.args.get('status')
        search = request.args.get('search', '').strip()
        
        # Query base
        query = Account.query
        
        # Aplicar filtros
        if plan and plan != 'all':
            query = query.filter_by(plan=plan)
        
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        if search:
            query = query.filter(Account.name.ilike(f'%{search}%'))
        
        # Ordenar y paginar
        accounts_pagination = query.order_by(desc(Account.created_at)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'admin/accounts/list.html',
            accounts=accounts_pagination.items,
            pagination=accounts_pagination
        )
        
    except Exception as e:
        logger.error(f'Error al cargar cuentas: {e}')
        flash('Error al cargar las cuentas', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/accounts/<int:account_id>')
@login_required
@admin_required
def view_account(account_id):
    """Ver detalles de una cuenta"""
    try:
        account = Account.query.get_or_404(account_id)
        
        # Usuarios de la cuenta
        users = User.query.filter_by(account_id=account_id).all()
        
        # Suscripciones
        subscriptions = Subscription.query.filter_by(account_id=account_id).order_by(
            desc(Subscription.created_at)
        ).all()
        
        # Pagos
        if subscriptions:
            subscription_ids = [s.id for s in subscriptions]
            payments = SubscriptionPayment.query.filter(
                SubscriptionPayment.subscription_id.in_(subscription_ids)
            ).order_by(desc(SubscriptionPayment.payment_date)).limit(10).all()
        else:
            payments = []
        
        # Estado del trial
        trial_status = TrialService.check_trial_status(account_id)
        
        return render_template(
            'admin/accounts/view.html',
            account=account,
            users=users,
            subscriptions=subscriptions,
            payments=payments,
            trial_status=trial_status
        )
        
    except Exception as e:
        logger.error(f'Error al cargar cuenta: {e}')
        flash('Error al cargar la cuenta', 'danger')
        return redirect(url_for('admin.accounts'))


@admin_bp.route('/accounts/<int:account_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_account_status(account_id):
    """Activar/desactivar cuenta"""
    try:
        account = Account.query.get_or_404(account_id)
        
        if account.is_active:
            account.soft_delete()
            flash(f'Cuenta {account.name} desactivada', 'success')
        else:
            account.restore()
            flash(f'Cuenta {account.name} activada', 'success')
        
        logger.info(f'Estado de cuenta cambiado: {account_id} -> {account.is_active}')
        
    except Exception as e:
        logger.error(f'Error al cambiar estado de cuenta: {e}')
        flash('Error al cambiar el estado', 'danger')
    
    return redirect(url_for('admin.view_account', account_id=account_id))


@admin_bp.route('/accounts/<int:account_id>/extend-trial', methods=['POST'])
@login_required
@admin_required
def extend_trial(account_id):
    """Extender trial de una cuenta"""
    try:
        days = request.form.get('days', 7, type=int)
        
        result = TrialService.extend_trial(account_id, days)
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'danger')
        
    except Exception as e:
        logger.error(f'Error al extender trial: {e}')
        flash('Error al extender el trial', 'danger')
    
    return redirect(url_for('admin.view_account', account_id=account_id))


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """Lista de todos los usuarios"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtros
        role = request.args.get('role')
        search = request.args.get('search', '').strip()
        
        # Query base
        query = User.query.filter_by(is_active=True)
        
        # Aplicar filtros
        if role and role != 'all':
            query = query.filter_by(role=role)
        
        if search:
            query = query.filter(
                db.or_(
                    User.name.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
        
        # Ordenar y paginar
        users_pagination = query.order_by(desc(User.created_at)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'admin/users/list.html',
            users=users_pagination.items,
            pagination=users_pagination
        )
        
    except Exception as e:
        logger.error(f'Error al cargar usuarios: {e}')
        flash('Error al cargar los usuarios', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/subscriptions')
@login_required
@admin_required
def subscriptions():
    """Lista de todas las suscripciones"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtros
        status = request.args.get('status')
        gateway = request.args.get('gateway')
        
        # Query base
        query = Subscription.query
        
        # Aplicar filtros
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        if gateway and gateway != 'all':
            query = query.filter_by(gateway=gateway)
        
        # Ordenar y paginar
        subs_pagination = query.order_by(desc(Subscription.created_at)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'admin/subscriptions/list.html',
            subscriptions=subs_pagination.items,
            pagination=subs_pagination
        )
        
    except Exception as e:
        logger.error(f'Error al cargar suscripciones: {e}')
        flash('Error al cargar las suscripciones', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/support')
@login_required
@admin_required
def support_tickets():
    """Lista de tickets de soporte"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Filtro de estado
        status = request.args.get('status', 'open')
        
        # Query
        query = SupportTicket.query
        
        if status != 'all':
            query = query.filter_by(status=status)
        
        tickets_pagination = query.order_by(desc(SupportTicket.created_at)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'admin/support/list.html',
            tickets=tickets_pagination.items,
            pagination=tickets_pagination
        )
        
    except Exception as e:
        logger.error(f'Error al cargar tickets: {e}')
        flash('Error al cargar los tickets', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/support/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def view_ticket(ticket_id):
    """Ver y gestionar ticket de soporte"""
    ticket = SupportTicket.query.get_or_404(ticket_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        try:
            if action == 'close':
                ticket.status = 'closed'
                flash('Ticket cerrado', 'success')
            elif action == 'in_progress':
                ticket.status = 'in_progress'
                ticket.assigned_to = current_user.id
                flash('Ticket asignado', 'success')
            
            db.session.commit()
            logger.info(f'Ticket {ticket_id} actualizado: {action}')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al actualizar ticket: {e}')
            flash('Error al actualizar el ticket', 'danger')
    
    return render_template('admin/support/view.html', ticket=ticket)


@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    """Logs de auditoría"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        # Filtros
        table_name = request.args.get('table')
        action = request.args.get('action')
        
        # Query
        query = AuditLog.query
        
        if table_name and table_name != 'all':
            query = query.filter_by(table_name=table_name)
        
        if action and action != 'all':
            query = query.filter_by(action=action)
        
        logs_pagination = query.order_by(desc(AuditLog.timestamp)).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return render_template(
            'admin/audit_logs.html',
            logs=logs_pagination.items,
            pagination=logs_pagination
        )
        
    except Exception as e:
        logger.error(f'Error al cargar audit logs: {e}')
        flash('Error al cargar los logs', 'danger')
        return redirect(url_for('admin.dashboard'))


# API Endpoints
@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API: Estadísticas para charts"""
    try:
        # Revenue por mes (últimos 12 meses)
        twelve_months_ago = datetime.utcnow() - timedelta(days=365)
        
        monthly_revenue = db.session.query(
            func.date_format(SubscriptionPayment.payment_date, '%Y-%m').label('month'),
            func.sum(SubscriptionPayment.amount).label('revenue')
        ).filter(
            SubscriptionPayment.status == 'paid',
            SubscriptionPayment.payment_date >= twelve_months_ago
        ).group_by('month').all()
        
        # Nuevas cuentas por mes
        monthly_accounts = db.session.query(
            func.date_format(Account.created_at, '%Y-%m').label('month'),
            func.count(Account.id).label('count')
        ).filter(
            Account.created_at >= twelve_months_ago
        ).group_by('month').all()
        
        return jsonify({
            'success': True,
            'revenue': [{'month': r[0], 'amount': float(r[1])} for r in monthly_revenue],
            'accounts': [{'month': a[0], 'count': a[1]} for a in monthly_accounts]
        })
        
    except Exception as e:
        logger.error(f'Error en API stats: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500