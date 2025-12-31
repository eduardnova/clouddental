"""
Rutas del dashboard de usuarios (recepcionistas, dentistas, admins de cuenta)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.extensions import db
from app.models import User, Account, Permission
from app.utils.security import subscription_required, account_admin_required, get_allowed_modules
from app.services.trial_service import TrialService
from app.utils.redis_cache import cache_get, cache_set
import logging

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__)


@users_bp.route('/')
@login_required
@subscription_required
def dashboard():
    """Dashboard principal del usuario"""
    try:
        # Obtener información del trial
        trial_status = TrialService.check_trial_status(current_user.account_id)
        
        # Obtener módulos disponibles
        allowed_modules = get_allowed_modules(current_user)
        
        # Estadísticas básicas (cachear)
        cache_key = f'dashboard_stats:{current_user.account_id}'
        stats = cache_get(cache_key)
        
        if not stats:
            # TODO: Calcular estadísticas reales de la BD
            stats = {
                'appointments_today': 0,
                'patients_total': 0,
                'pending_payments': 0,
                'monthly_revenue': 0
            }
            cache_set(cache_key, stats, ttl=300)  # 5 minutos
        
        # Avisos importantes
        warnings = []
        
        # Aviso de trial próximo a expirar
        if trial_status.get('active') and trial_status.get('days_remaining', 0) <= 3:
            warnings.append({
                'type': 'warning',
                'message': f'Tu período de prueba expira en {trial_status["days_remaining"]} días. Suscríbete para continuar usando CloudDental.'
            })
        
        # Aviso si el trial expiró
        if trial_status.get('expired') and not current_user.account.has_active_subscription():
            warnings.append({
                'type': 'danger',
                'message': 'Tu período de prueba ha expirado. Por favor selecciona un plan para continuar.'
            })
        
        return render_template(
            'dashboard/index.html',
            trial_status=trial_status,
            modules=allowed_modules,
            stats=stats,
            warnings=warnings
        )
        
    except Exception as e:
        logger.error(f'Error en dashboard: {e}')
        flash('Error al cargar el dashboard', 'danger')
        return render_template('dashboard/index.html')


@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Perfil del usuario"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            
            # Validar nombre
            if not name:
                flash('El nombre es requerido', 'danger')
                return render_template('dashboard/profile.html')
            
            # Actualizar nombre
            current_user.name = name
            
            # Cambiar contraseña si se proporcionó
            if new_password:
                if not current_password:
                    flash('Debes ingresar tu contraseña actual', 'danger')
                    return render_template('dashboard/profile.html')
                
                if not current_user.check_password(current_password):
                    flash('Contraseña actual incorrecta', 'danger')
                    return render_template('dashboard/profile.html')
                
                if len(new_password) < 8:
                    flash('La nueva contraseña debe tener al menos 8 caracteres', 'danger')
                    return render_template('dashboard/profile.html')
                
                current_user.set_password(new_password)
                flash('Contraseña actualizada exitosamente', 'success')
            
            db.session.commit()
            
            logger.info(f'Perfil actualizado: usuario {current_user.id}')
            flash('Perfil actualizado exitosamente', 'success')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al actualizar perfil: {e}')
            flash('Error al actualizar el perfil', 'danger')
    
    return render_template('dashboard/profile.html')


@users_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@account_admin_required
def settings():
    """Configuración de la cuenta (solo admins)"""
    if request.method == 'POST':
        try:
            clinic_name = request.form.get('clinic_name', '').strip()
            
            if not clinic_name:
                flash('El nombre de la clínica es requerido', 'danger')
                return render_template('dashboard/settings.html')
            
            # Actualizar nombre de la cuenta
            current_user.account.name = clinic_name
            db.session.commit()
            
            logger.info(f'Configuración actualizada: cuenta {current_user.account_id}')
            flash('Configuración actualizada exitosamente', 'success')
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al actualizar configuración: {e}')
            flash('Error al actualizar la configuración', 'danger')
    
    return render_template('dashboard/settings.html')


@users_bp.route('/users')
@login_required
@account_admin_required
def manage_users():
    """Gestión de usuarios de la cuenta (solo admins)"""
    try:
        # Obtener usuarios de la cuenta
        users = User.query.filter_by(
            account_id=current_user.account_id,
            is_active=True
        ).all()
        
        return render_template('dashboard/users/list.html', users=users)
        
    except Exception as e:
        logger.error(f'Error al cargar usuarios: {e}')
        flash('Error al cargar los usuarios', 'danger')
        return redirect(url_for('users.dashboard'))


@users_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@account_admin_required
def add_user():
    """Agregar nuevo usuario a la cuenta"""
    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip().lower()
            name = request.form.get('name', '').strip()
            role = request.form.get('role', 'receptionist')
            password = request.form.get('password', '')
            
            # Validaciones
            if not all([email, name, password]):
                flash('Todos los campos son requeridos', 'danger')
                return render_template('dashboard/users/add.html')
            
            if len(password) < 8:
                flash('La contraseña debe tener al menos 8 caracteres', 'danger')
                return render_template('dashboard/users/add.html')
            
            # Verificar que el email no exista
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Este correo ya está registrado', 'danger')
                return render_template('dashboard/users/add.html')
            
            # Crear usuario
            user = User(
                account_id=current_user.account_id,
                email=email,
                name=name,
                role=role,
                email_confirmed=True  # Auto-confirmado para usuarios internos
            )
            user.set_password(password)
            
            db.session.add(user)
            
            # Asignar permisos por defecto según el rol
            if role == 'dentist':
                # Dentistas: acceso a citas, pacientes, procedimientos
                modules = ['appointments', 'patients', 'procedures']
            elif role == 'receptionist':
                # Recepcionistas: acceso a citas, pacientes, pagos
                modules = ['appointments', 'patients', 'payments', 'quotations']
            else:
                modules = []
            
            for module in modules:
                permission = Permission(
                    user_id=user.id,
                    module=module,
                    access_level='write'
                )
                db.session.add(permission)
            
            db.session.commit()
            
            logger.info(f'Usuario creado: {email} para cuenta {current_user.account_id}')
            flash(f'Usuario {name} creado exitosamente', 'success')
            return redirect(url_for('users.manage_users'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al crear usuario: {e}')
            flash('Error al crear el usuario', 'danger')
    
    return render_template('dashboard/users/add.html')


@users_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@account_admin_required
def edit_user(user_id):
    """Editar usuario de la cuenta"""
    user = User.query.filter_by(
        id=user_id,
        account_id=current_user.account_id
    ).first_or_404()
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            role = request.form.get('role', user.role)
            
            if not name:
                flash('El nombre es requerido', 'danger')
                return render_template('dashboard/users/edit.html', user=user)
            
            user.name = name
            user.role = role
            
            db.session.commit()
            
            logger.info(f'Usuario actualizado: {user_id}')
            flash('Usuario actualizado exitosamente', 'success')
            return redirect(url_for('users.manage_users'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al actualizar usuario: {e}')
            flash('Error al actualizar el usuario', 'danger')
    
    return render_template('dashboard/users/edit.html', user=user)


@users_bp.route('/users/<int:user_id>/permissions', methods=['GET', 'POST'])
@login_required
@account_admin_required
def user_permissions(user_id):
    """Gestionar permisos de un usuario"""
    user = User.query.filter_by(
        id=user_id,
        account_id=current_user.account_id
    ).first_or_404()
    
    # No se pueden cambiar permisos de admins
    if user.is_account_admin():
        flash('No se pueden cambiar permisos de administradores', 'warning')
        return redirect(url_for('users.manage_users'))
    
    if request.method == 'POST':
        try:
            # Obtener permisos del formulario
            modules = [
                'appointments', 'patients', 'payments', 'quotations',
                'procedures', 'inventory', 'payroll', 'reports'
            ]
            
            for module in modules:
                access_level = request.form.get(f'permission_{module}', 'none')
                
                # Buscar o crear permiso
                permission = Permission.query.filter_by(
                    user_id=user.id,
                    module=module
                ).first()
                
                if permission:
                    permission.access_level = access_level
                else:
                    permission = Permission(
                        user_id=user.id,
                        module=module,
                        access_level=access_level
                    )
                    db.session.add(permission)
            
            db.session.commit()
            
            logger.info(f'Permisos actualizados para usuario {user_id}')
            flash('Permisos actualizados exitosamente', 'success')
            return redirect(url_for('users.manage_users'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al actualizar permisos: {e}')
            flash('Error al actualizar los permisos', 'danger')
    
    # Obtener permisos actuales
    permissions = {}
    for permission in user.permissions:
        permissions[permission.module] = permission.access_level
    
    return render_template('dashboard/users/permissions.html', user=user, permissions=permissions)


@users_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@account_admin_required
def delete_user(user_id):
    """Desactivar usuario (soft delete)"""
    if user_id == current_user.id:
        flash('No puedes eliminar tu propio usuario', 'danger')
        return redirect(url_for('users.manage_users'))
    
    try:
        user = User.query.filter_by(
            id=user_id,
            account_id=current_user.account_id
        ).first_or_404()
        
        # Soft delete
        user.soft_delete()
        
        logger.info(f'Usuario desactivado: {user_id}')
        flash('Usuario desactivado exitosamente', 'success')
        
    except Exception as e:
        logger.error(f'Error al desactivar usuario: {e}')
        flash('Error al desactivar el usuario', 'danger')
    
    return redirect(url_for('users.manage_users'))


# API Endpoints para AJAX
@users_bp.route('/api/trial-status')
@login_required
def api_trial_status():
    """API: Estado del trial"""
    try:
        trial_status = TrialService.check_trial_status(current_user.account_id)
        return jsonify({
            'success': True,
            'trial_status': trial_status
        })
    except Exception as e:
        logger.error(f'Error en API trial status: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@users_bp.route('/api/stats')
@login_required
@subscription_required
def api_stats():
    """API: Estadísticas del dashboard"""
    try:
        # TODO: Implementar estadísticas reales
        stats = {
            'appointments_today': 0,
            'patients_total': 0,
            'pending_payments': 0,
            'monthly_revenue': 0
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f'Error en API stats: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500