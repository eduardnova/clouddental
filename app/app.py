"""
Archivo principal para ejecutar la aplicación Flask
"""
import os
from app import create_app
from app.extensions import db

# Crear aplicación
app = create_app()


@app.shell_context_processor
def make_shell_context():
    """
    Crea un contexto de shell con objetos útiles
    Uso: flask shell
    """
    from app.models import (
        User, Account, Subscription, SubscriptionPayment,
        Permission, LoginAttempt, AuditLog, SupportTicket
    )
    
    return {
        'db': db,
        'User': User,
        'Account': Account,
        'Subscription': Subscription,
        'SubscriptionPayment': SubscriptionPayment,
        'Permission': Permission,
        'LoginAttempt': LoginAttempt,
        'AuditLog': AuditLog,
        'SupportTicket': SupportTicket
    }


if __name__ == '__main__':
    # Configuración para desarrollo
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    
    app.run(
        host=host,
        port=port,
        debug=debug
    )