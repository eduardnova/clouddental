"""
Modelos de Base de Datos para CloudDental SaaS
Incluye soft delete, timestamps y relaciones completas
"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy import Index, text
from app.extensions import db, bcrypt


class TimestampMixin:
    """Mixin para timestamps automáticos"""
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class SoftDeleteMixin:
    """Mixin para soft delete"""
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    def soft_delete(self):
        """Marca el registro como eliminado"""
        self.deleted_at = datetime.utcnow()
        self.is_active = False
        db.session.commit()
    
    def restore(self):
        """Restaura un registro eliminado"""
        self.deleted_at = None
        self.is_active = True
        db.session.commit()


class Account(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Cuenta de la clínica dental (multi-tenant)
    Cada cuenta puede tener múltiples usuarios
    """
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    plan = db.Column(
        db.Enum('basic', 'pro', 'enterprise', name='plan_types'),
        nullable=False,
        default='basic'
    )
    
    # IDs de gateways de pago
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    paypal_payer_id = db.Column(db.String(255), nullable=True)
    
    # Estado de trial
    trial_start = db.Column(db.DateTime, nullable=True)
    trial_end = db.Column(db.DateTime, nullable=True)
    trial_used = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relaciones
    users = db.relationship('User', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', backref='account', lazy='dynamic')
    
    def __repr__(self):
        return f'<Account {self.name}>'
    
    def is_trial_active(self):
        """Verifica si el trial está activo"""
        if not self.trial_start or not self.trial_end:
            return False
        return datetime.utcnow() < self.trial_end
    
    def start_trial(self, days=10):
        """Inicia el período de trial"""
        if not self.trial_used:
            self.trial_start = datetime.utcnow()
            self.trial_end = self.trial_start + timedelta(days=days)
            self.trial_used = True
            db.session.commit()
            return True
        return False
    
    def has_active_subscription(self):
        """Verifica si tiene una suscripción activa"""
        active_sub = self.subscriptions.filter_by(
            status='active',
            is_active=True
        ).first()
        return active_sub is not None
    
    def can_access_features(self):
        """Verifica si puede acceder a las funcionalidades"""
        return self.is_trial_active() or self.has_active_subscription()


class User(UserMixin, db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Usuario del sistema (multi-rol)
    Puede ser: platform_admin, account_admin, receptionist, dentist, employee
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    
    # Credenciales
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=True)  # Nullable para OAuth
    
    # OAuth IDs
    google_id = db.Column(db.String(255), nullable=True, unique=True)
    microsoft_id = db.Column(db.String(255), nullable=True, unique=True)
    
    # Información del usuario
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum('platform_admin', 'account_admin', 'receptionist', 'dentist', 'employee', name='user_roles'),
        nullable=False,
        default='receptionist'
    )
    
    # Seguridad
    two_factor_secret = db.Column(db.String(255), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    email_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmation_token = db.Column(db.String(255), nullable=True)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    
    # Control de sesión
    last_login = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Relaciones
    login_attempts = db.relationship('LoginAttempt', backref='user', lazy='dynamic')
    permissions = db.relationship('Permission', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def set_password(self, password):
        """Hash de la contraseña"""
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Verifica la contraseña"""
        if not self.password:
            return False
        return bcrypt.check_password_hash(self.password, password)
    
    def is_admin(self):
        """Verifica si es administrador de plataforma"""
        return self.role == 'platform_admin'
    
    def is_account_admin(self):
        """Verifica si es administrador de cuenta"""
        return self.role == 'account_admin'
    
    def can_access_module(self, module_name):
        """Verifica si puede acceder a un módulo específico"""
        permission = self.permissions.filter_by(module=module_name).first()
        if permission:
            return permission.access_level in ['read', 'write']
        return False
    
    def record_login(self, ip_address, success=True):
        """Registra un intento de login"""
        attempt = LoginAttempt(
            user_id=self.id,
            ip_address=ip_address,
            success=success
        )
        db.session.add(attempt)
        
        if success:
            self.last_login = datetime.utcnow()
            self.login_count += 1
        
        db.session.commit()


class Permission(db.Model, TimestampMixin):
    """
    Permisos por módulo para cada usuario
    """
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    module = db.Column(db.String(100), nullable=False)
    access_level = db.Column(
        db.Enum('read', 'write', 'none', name='access_levels'),
        nullable=False,
        default='none'
    )
    
    __table_args__ = (
        Index('idx_user_module', 'user_id', 'module', unique=True),
    )
    
    def __repr__(self):
        return f'<Permission {self.module}:{self.access_level}>'


class Subscription(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Suscripción activa de una cuenta
    Puede ser de Stripe o PayPal
    """
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    
    # Gateway de pago
    gateway = db.Column(
        db.Enum('stripe', 'paypal', name='payment_gateways'),
        nullable=False
    )
    subscription_id = db.Column(db.String(255), nullable=False)  # ID del gateway
    
    # Detalles del plan
    plan = db.Column(
        db.Enum('basic', 'pro', 'enterprise', name='subscription_plans'),
        nullable=False
    )
    billing_cycle = db.Column(
        db.Enum('monthly', 'yearly', name='billing_cycles'),
        nullable=False,
        default='monthly'
    )
    
    # Estado
    status = db.Column(
        db.Enum('active', 'trialing', 'past_due', 'canceled', 'unpaid', 'paused', 'suspended', name='subscription_status'),
        nullable=False,
        default='active'
    )
    
    # Fechas
    start_date = db.Column(db.Date, nullable=False)
    current_period_start = db.Column(db.Date, nullable=True)
    current_period_end = db.Column(db.Date, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)
    
    # Metadata adicional (JSON)
    metadata = db.Column(db.JSON, nullable=True)
    
    # Relaciones
    payments = db.relationship('SubscriptionPayment', backref='subscription', lazy='dynamic')
    
    __table_args__ = (
        Index('idx_account_status', 'account_id', 'status'),
        Index('idx_gateway_sub_id', 'gateway', 'subscription_id'),
    )
    
    def __repr__(self):
        return f'<Subscription {self.plan} - {self.status}>'
    
    def cancel(self):
        """Cancela la suscripción"""
        self.status = 'canceled'
        self.canceled_at = datetime.utcnow()
        db.session.commit()
    
    def is_active(self):
        """Verifica si la suscripción está activa"""
        return self.status == 'active' and self.is_active


class SubscriptionPayment(db.Model, TimestampMixin):
    """
    Pagos de suscripción (facturas)
    """
    __tablename__ = 'subscription_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False)
    
    # ID de la factura en el gateway
    gateway_invoice_id = db.Column(db.String(255), nullable=True)
    
    # Monto y estado
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(
        db.Enum('paid', 'failed', 'pending', 'void', name='payment_status'),
        nullable=False,
        default='pending'
    )
    
    # Fechas
    payment_date = db.Column(db.Date, nullable=False)
    
    # Razón de fallo si aplica
    failure_reason = db.Column(db.Text, nullable=True)
    
    __table_args__ = (
        Index('idx_sub_payment_date', 'subscription_id', 'payment_date'),
    )
    
    def __repr__(self):
        return f'<Payment ${self.amount} - {self.status}>'


class LoginAttempt(db.Model):
    """
    Registro de intentos de login (seguridad)
    """
    __tablename__ = 'login_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    success = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<LoginAttempt {self.success} at {self.timestamp}>'


class AuditLog(db.Model):
    """
    Registro de auditoría de todas las operaciones
    """
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    action = db.Column(
        db.Enum('insert', 'update', 'delete', name='audit_actions'),
        nullable=False
    )
    
    # Datos antes y después
    old_data = db.Column(db.JSON, nullable=True)
    new_data = db.Column(db.JSON, nullable=True)
    
    # Usuario que realizó la acción
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_table_record', 'table_name', 'record_id'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<AuditLog {self.table_name}.{self.action}>'


class SupportTicket(db.Model, TimestampMixin):
    """
    Tickets de soporte para usuarios
    """
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum('open', 'in_progress', 'closed', name='ticket_status'),
        nullable=False,
        default='open'
    )
    
    # Asignación (para admins de plataforma)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    __table_args__ = (
        Index('idx_account_status', 'account_id', 'status'),
    )
    
    def __repr__(self):
        return f'<Ticket {self.title} - {self.status}>'
    
    
class Appointment(db.Model, TimestampMixin, SoftDeleteMixin):
    """Citas programadas"""
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    dentist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    date_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, default=30)  # minutos
    status = db.Column(
        db.Enum('scheduled', 'completed', 'cancelled', 'no_show', name='appointment_status'),
        default='scheduled'
    )
    
    notes = db.Column(db.Text)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    __table_args__ = (
        Index('idx_account_date', 'account_id', 'date_time'),
        Index('idx_dentist_date', 'dentist_id', 'date_time'),
    )


class Patient(db.Model, TimestampMixin, SoftDeleteMixin):
    """Pacientes de la clínica"""
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Información personal
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.Enum('male', 'female', 'other', name='gender'))
    
    # Contacto
    phone = db.Column(db.String(50))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    
    # Médico
    allergies = db.Column(db.Text)
    medical_conditions = db.Column(db.Text)
    insurance_info = db.Column(db.JSON)
    
    # Relaciones
    appointments = db.relationship('Appointment', backref='patient', lazy='dynamic')