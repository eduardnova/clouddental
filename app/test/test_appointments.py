import unittest
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import Account, User, Patient, Appointment
from app.services.appointment_service import AppointmentService


class AppointmentTestCase(unittest.TestCase):
    
    def setUp(self):
        """Setup de pruebas"""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Crear datos de prueba
        self.account = Account(name='Test Clinic', plan='basic')
        db.session.add(self.account)
        db.session.flush()
        
        self.dentist = User(
            account_id=self.account.id,
            email='dentist@test.com',
            name='Dr. Test',
            role='dentist'
        )
        db.session.add(self.dentist)
        
        self.patient = Patient(
            account_id=self.account.id,
            first_name='John',
            last_name='Doe'
        )
        db.session.add(self.patient)
        db.session.commit()
    
    def tearDown(self):
        """Limpieza"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_create_appointment(self):
        """Test de creación de cita"""
        result = AppointmentService.create_appointment(
            account_id=self.account.id,
            patient_id=self.patient.id,
            dentist_id=self.dentist.id,
            date_time=datetime.now() + timedelta(days=1),
            duration=30
        )
        
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['appointment'])


if __name__ == '__main__':
    unittest.main()