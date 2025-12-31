"""
Inicialización de la aplicación Flask
Factory pattern para crear instancias de la app
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from flask import Flask
from flask_cors import CORS
from app.config import get_config
from app.extensions import db, login_manager, bcrypt, mail, migrate
from app.utils.redis_cache import init_redis


def create_app(config_name=None):
    """
    Factory para crear la aplicación Flask
    
    Args:
        config_name: Nombre de la configuración (development, production, testing)
        
    Returns:
        Flask app instance
    """
    # Crear instancia de Flask
    app = Flask(__name__)
    
    # Cargar configuración
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Configurar CORS
    CORS(app, resources={
        r"/*": {
            "origins": os.getenv('ALLOWED_ORIGINS', '*').split(',')
        }
    })
    
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    
    # Inicializar Redis (con fallback automático)
    with app.app_context():
        redis_available = init_redis(app)
        if redis_available:
            app.logger.info("✓ Cache Redis inicializado")
        else:
            app.logger.info("⚠ Usando cache en memoria (Redis no disponible)")
    
    # Crear carpeta de uploads si no existe
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        app.logger.info(f"Carpeta de uploads creada: {upload_folder}")
    
    # Configurar logging
    setup_logging(app)
    
    # Registrar Blueprints
    register_blueprints(app)
    
    # Registrar manejadores de errores
    register_error_handlers(app)
    
    # Registrar comandos CLI
    register_cli_commands(app)
    
    # Context processors
    register_context_processors(app)
    
    app.logger.info(f"Aplicación iniciada en modo: {config_name}")
    
    return app


def setup_logging(app):
    """Configura el sistema de logging"""
    if not app.debug and not app.testing:
        # Crear directorio de logs si no existe
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Handler para archivo
        file_handler = RotatingFileHandler(
            app.config.get('LOG_FILE', 'logs/app.log'),
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        ))
        
        file_handler.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
        app.logger.info('CloudDental startup')


def register_blueprints(app):
    """Registra todos los blueprints"""
    from app.routes.routes_auth import auth_bp
    from app.routes.routes_users import users_bp
    from app.routes.routes_billing import billing_bp
    from app.routes.routes_admin import admin_bp
    from app.routes.routes_appointments import appointments_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(users_bp, url_prefix='/dashboard')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(appointments_bp, url_prefix='/appointments')
    
    # Ruta principal
    @app.route('/')
    def index():
        from flask import render_template, redirect, url_for
        from flask_login import current_user
        
        if current_user.is_authenticated:
            if current_user.is_admin():
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('users.dashboard'))
        
        return render_template('landing.html')


def register_error_handlers(app):
    """Registra manejadores de errores"""
    from flask import render_template, jsonify, request
    
    @app.errorhandler(400)
    def bad_request(error):
        if request.is_json:
            return jsonify({'error': 'Bad request'}), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        if request.is_json:
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        if request.is_json:
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Server Error: {error}')
        if request.is_json:
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500


def register_cli_commands(app):
    """Registra comandos CLI personalizados"""
    import click
    from app.models import User, Account
    
    @app.cli.command('create-admin')
    @click.argument('email')
    @click.argument('password')
    @click.argument('name')
    def create_admin(email, password, name):
        """Crea un usuario administrador de plataforma"""
        # Crear cuenta especial para admins de plataforma
        account = Account(
            name='Platform Admin Account',
            plan='enterprise'
        )
        db.session.add(account)
        db.session.flush()
        
        # Crear usuario admin
        user = User(
            account_id=account.id,
            email=email,
            name=name,
            role='platform_admin',
            email_confirmed=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f'✓ Administrador creado: {email}')
    
    @app.cli.command('init-db')
    def init_db():
        """Inicializa la base de datos"""
        db.create_all()
        click.echo('✓ Base de datos inicializada')
    
    @app.cli.command('seed-data')
    def seed_data():
        """Carga datos de prueba"""
        from datetime import datetime, timedelta
        
        # Crear cuenta de prueba
        account = Account(
            name='Clínica Dental Demo',
            plan='basic'
        )
        db.session.add(account)
        db.session.flush()
        
        # Iniciar trial
        account.start_trial(days=10)
        
        # Crear usuarios de prueba
        admin_user = User(
            account_id=account.id,
            email='admin@demo.com',
            name='Administrador Demo',
            role='account_admin',
            email_confirmed=True
        )
        admin_user.set_password('demo123')
        
        dentist_user = User(
            account_id=account.id,
            email='dentist@demo.com',
            name='Dr. Juan Pérez',
            role='dentist',
            email_confirmed=True
        )
        dentist_user.set_password('demo123')
        
        receptionist_user = User(
            account_id=account.id,
            email='reception@demo.com',
            name='María García',
            role='receptionist',
            email_confirmed=True
        )
        receptionist_user.set_password('demo123')
        
        db.session.add_all([admin_user, dentist_user, receptionist_user])
        db.session.commit()
        
        click.echo('✓ Datos de prueba cargados')
        click.echo(f'  Cuenta: {account.name}')
        click.echo(f'  Trial hasta: {account.trial_end}')
        click.echo('  Usuarios:')
        click.echo('    - admin@demo.com / demo123')
        click.echo('    - dentist@demo.com / demo123')
        click.echo('    - reception@demo.com / demo123')


def register_context_processors(app):
    """Registra context processors para templates"""
    from flask_login import current_user
    from datetime import datetime
    
    @app.context_processor
    def inject_globals():
        """Inyecta variables globales en todos los templates"""
        return {
            'app_name': 'CloudDental',
            'current_year': datetime.utcnow().year,
            'current_user': current_user
        }
    
    @app.context_processor
    def inject_subscription_status():
        """Inyecta estado de suscripción si el usuario está autenticado"""
        if current_user.is_authenticated:
            from app.services.trial_service import TrialService
            
            trial_status = TrialService.check_trial_status(current_user.account_id)
            
            return {
                'trial_status': trial_status,
                'account': current_user.account
            }
        
        return {}