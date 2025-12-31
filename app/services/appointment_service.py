from datetime import datetime, timedelta
from app.extensions import db
from app.models import Appointment, Patient, User
import logging

logger = logging.getLogger(__name__)


class AppointmentService:
    """Servicio para gestión de citas"""
    
    @staticmethod
    def create_appointment(account_id, patient_id, dentist_id, date_time, duration=30, notes=None):
        """Crea una nueva cita"""
        try:
            # Validar que el dentista esté disponible
            conflicts = Appointment.query.filter(
                Appointment.dentist_id == dentist_id,
                Appointment.date_time.between(
                    date_time - timedelta(minutes=duration),
                    date_time + timedelta(minutes=duration)
                ),
                Appointment.status.in_(['scheduled', 'completed'])
            ).first()
            
            if conflicts:
                return {
                    'success': False,
                    'message': 'El dentista no está disponible en ese horario'
                }
            
            # Crear cita
            appointment = Appointment(
                account_id=account_id,
                patient_id=patient_id,
                dentist_id=dentist_id,
                date_time=date_time,
                duration=duration,
                notes=notes
            )
            
            db.session.add(appointment)
            db.session.commit()
            
            return {
                'success': True,
                'appointment': appointment,
                'message': 'Cita creada exitosamente'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error al crear cita: {e}')
            return {
                'success': False,
                'message': str(e)
            }