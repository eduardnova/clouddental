"""
Rutas de autenticación: Login, Registro, Recuperación de contraseña
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.urls import url_parse
import secrets
from datetime import datetime, timedelta
from app.extensions import db
from app.models import User, Account
from app.services.trial_service import TrialService
from app.utils.redis_cache import cache_set, cache_delete
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nueva cuenta y usuario"""
    if current_user.is_authenticated:
        return redirect(url_for('users.dashboard'))
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            clinic_name = request.form.get('clinic_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            name = request.form.get('name', '').strip()
            plan = request.form.get('plan', 'basic')
            
            # Validaciones
            if not all([clinic_name, email, password, name]):
                flash('Todos los campos son requeridos', 'danger')
                return render_template('auth/register.html')
            
            if len(password) < 8:
                flash('La contraseña debe tener al menos 8 caracteres', 'danger')
                return render_template('auth/register.html')
            
            # Verificar si el email ya existe
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Este correo ya está registrado', 'danger')
                return render_template('auth/register.html')
            
            # Crear cuenta
            account = Account(
                name=clinic_name,
                plan=plan
            )
            db.session.add(account)
            db.session.flush()  # Para obtener el ID
            
            # Iniciar trial automáticamente
            trial_result = TrialService.start_trial(account.id)
            
            if not trial_result['success']:
                db.session.rollback()
                flash(f'Error al iniciar trial: {trial_result["message"]}', 'danger')
                return render_template('auth/register.html')
            
            # Crear usuario administrador de la cuenta
            user = User(
                account_id=account.id,
                email=email,
                name=name,
                role='account_admin',
                email_confirmed=False,
                confirmation_token=secrets.token_urlsafe(32)
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # TODO: Enviar email de confirmación
            # send_confirmation_email(user)
            
            logger.info(f'Nueva cuenta registrada: {clinic_name} ({email})')
            
            # Login automático
            login_user(user, remember=True)
            
            # Registrar login
            user.record_login(request.remote_addr, success=True)
            
            flash(f'¡Cuenta creada exitosamente! Tu período de prueba de {trial_result["days_remaining"]} días ha comenzado.', 'success')
            return redirect(url_for('users.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error en registro: {e}')
            flash('Error al crear la cuenta. Por favor intenta nuevamente.', 'danger')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de usuarios"""
    if current_user.is_authenticated:
        return redirect(url_for('users.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False) == 'on'
        
        if not email or not password:
            flash('Email y contraseña son requeridos', 'danger')
            return render_template('auth/login.html')
        
        # Buscar usuario
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Credenciales inválidas', 'danger')
            return render_template('auth/login.html')
        
        # Verificar contraseña
        if not user.check_password(password):
            # Registrar intento fallido
            user.record_login(request.remote_addr, success=False)
            flash('Credenciales inválidas', 'danger')
            return render_template('auth/login.html')
        
        # Verificar que la cuenta esté activa
        if not user.account.is_active:
            flash('Tu cuenta ha sido desactivada. Contacta a soporte.', 'danger')
            return render_template('auth/login.html')
        
        # Verificar que pueda acceder (trial o suscripción)
        if not user.is_admin():
            if not user.account.can_access_features():
                flash('Tu período de prueba ha expirado y no tienes una suscripción activa.', 'warning')
                return redirect(url_for('billing.plans'))
        
        # Login exitoso
        login_user(user, remember=remember)
        
        # Registrar login exitoso
        user.record_login(request.remote_addr, success=True)
        
        logger.info(f'Login exitoso: {email}')
        
        # Redirigir a la página solicitada o al dashboard
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            if user.is_admin():
                next_page = url_for('admin.dashboard')
            else:
                next_page = url_for('users.dashboard')
        
        return redirect(next_page)
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Cierra la sesión del usuario"""
    logger.info(f'Logout: {current_user.email}')
    
    # Limpiar cache del usuario
    cache_delete(f'user:{current_user.id}')
    
    logout_user()
    flash('Has cerrado sesión exitosamente', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Solicitud de recuperación de contraseña"""
    if current_user.is_authenticated:
        return redirect(url_for('users.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Por favor ingresa tu correo electrónico', 'danger')
            return render_template('auth/forgot_password.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generar token de reseteo
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # TODO: Enviar email con link de reseteo
            # send_password_reset_email(user)
            
            logger.info(f'Token de reseteo generado para: {email}')
        
        # Siempre mostrar el mismo mensaje (seguridad)
        flash('Si el correo existe, recibirás instrucciones para restablecer tu contraseña.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reseteo de contraseña con token"""
    if current_user.is_authenticated:
        return redirect(url_for('users.dashboard'))
    
    # Buscar usuario con el token
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expiry:
        flash('Token de reseteo inválido o expirado', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    # Verificar que no haya expirado
    if datetime.utcnow() > user.reset_token_expiry:
        flash('Token de reseteo expirado', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password or len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        # Actualizar contraseña
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        logger.info(f'Contraseña restablecida para: {user.email}')
        
        flash('Contraseña restablecida exitosamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/confirm-email/<token>')
def confirm_email(token):
    """Confirma el email del usuario"""
    user = User.query.filter_by(confirmation_token=token).first()
    
    if not user:
        flash('Token de confirmación inválido', 'danger')
        return redirect(url_for('auth.login'))
    
    if user.email_confirmed:
        flash('Tu email ya ha sido confirmado', 'info')
        return redirect(url_for('auth.login'))
    
    # Confirmar email
    user.email_confirmed = True
    user.confirmation_token = None
    db.session.commit()
    
    logger.info(f'Email confirmado: {user.email}')
    
    flash('¡Email confirmado exitosamente! Ahora puedes iniciar sesión.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-confirmation', methods=['POST'])
@login_required
def resend_confirmation():
    """Reenvía el email de confirmación"""
    if current_user.email_confirmed:
        flash('Tu email ya ha sido confirmado', 'info')
        return redirect(url_for('users.dashboard'))
    
    # Generar nuevo token
    current_user.confirmation_token = secrets.token_urlsafe(32)
    db.session.commit()
    
    # TODO: Enviar email de confirmación
    # send_confirmation_email(current_user)
    
    flash('Email de confirmación enviado. Por favor revisa tu bandeja de entrada.', 'success')
    return redirect(url_for('users.dashboard'))


# OAuth Routes (Google, Microsoft) - Placeholders
@auth_bp.route('/oauth/google')
def oauth_google():
    """Autenticación con Google (placeholder)"""
    flash('Autenticación con Google próximamente disponible', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/oauth/microsoft')
def oauth_microsoft():
    """Autenticación con Microsoft (placeholder)"""
    flash('Autenticación con Microsoft próximamente disponible', 'info')
    return redirect(url_for('auth.login'))