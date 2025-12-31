from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.services.appointment_service import AppointmentService
from app.utils.security import subscription_required, module_access_required

appointments_bp = Blueprint('appointments', __name__)


@appointments_bp.route('/')
@login_required
@subscription_required
@module_access_required('appointments', 'read')
def list_appointments():
    """Lista de citas"""
    # TODO: Implementar
    return render_template('appointments/list.html')


@appointments_bp.route('/calendar')
@login_required
@subscription_required
@module_access_required('appointments', 'read')
def calendar():
    """Vista de calendario"""
    return render_template('appointments/calendar.html')


@appointments_bp.route('/create', methods=['GET', 'POST'])
@login_required
@subscription_required
@module_access_required('appointments', 'write')
def create_appointment():
    """Crear nueva cita"""
    if request.method == 'POST':
        # Obtener datos del formulario
        patient_id = request.form.get('patient_id', type=int)
        dentist_id = request.form.get('dentist_id', type=int)
        date = request.form.get('date')
        time = request.form.get('time')
        duration = request.form.get('duration', 30, type=int)
        notes = request.form.get('notes')
        
        # Combinar fecha y hora
        from datetime import datetime
        date_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        
        # Crear cita
        result = AppointmentService.create_appointment(
            account_id=current_user.account_id,
            patient_id=patient_id,
            dentist_id=dentist_id,
            date_time=date_time,
            duration=duration,
            notes=notes
        )
        
        if result['success']:
            flash('Cita creada exitosamente', 'success')
            return redirect(url_for('appointments.calendar'))
        else:
            flash(result['message'], 'danger')
    
    return render_template('appointments/create.html')