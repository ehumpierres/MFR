import os
from flask import Flask, render_template, flash, redirect, url_for, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_mail import Mail 
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, date, time, timedelta
from forms import LoginForm, BookingForm, NotificationEmailForm
from models import db, User, Property, Unit, Booking, NotificationEmail
from config import Config
import logging
from io import StringIO, BytesIO
import csv
from email_utils import send_email, create_ical_invite
from functools import wraps
from wtforms.validators import ValidationError

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.username != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    properties = Property.query.all()
    return render_template('properties.html', properties=properties)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        admin_user = User.query.filter_by(username='admin').first()
        regular_user = User.query.filter_by(username='user').first()

        if admin_user and form.passphrase.data == app.config['ADMIN_PASSPHRASE']:
            login_user(admin_user)
            return redirect(url_for('index'))
        elif regular_user and form.passphrase.data == app.config['USER_PASSPHRASE']:
            login_user(regular_user)
            return redirect(url_for('index'))

        flash('Invalid passphrase')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/property/<int:property_id>')
@login_required
def property_details(property_id):
    property = Property.query.get_or_404(property_id)
    upcoming_bookings = Booking.query.join(Booking.units).join(Unit).filter(
        Unit.property_id == property_id,
        Booking.status == 'approved',
        Booking.start_date >= date.today()
    ).order_by(Booking.start_date).all()
    return render_template('property_details.html', property=property, upcoming_bookings=upcoming_bookings)

@app.route('/get_units/<int:property_id>')
@login_required
def get_units(property_id):
    units = Unit.query.filter_by(property_id=property_id).all()
    return jsonify([{'id': unit.id, 'name': unit.name} for unit in units])

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    form = BookingForm()
    form.property_id.choices = [(p.id, p.name) for p in Property.query.all()]
    
    if form.validate_on_submit():
        if not form.units.data:
            flash('Please select at least one unit.', 'error')
            return render_template('booking_form.html', form=form)
        
        try:
            booking = Booking(
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                arrival_time=form.arrival_time.data,
                departure_time=form.departure_time.data,
                guest_name=form.guest_name.data,
                guest_email=form.guest_email.data,
                num_guests=form.num_guests.data,
                catering_option=form.catering_option.data,
                special_requests=form.special_requests.data,
                mobility_impaired=form.mobility_impaired.data == 'Yes',
                event_manager_contact=form.event_manager_contact.data,
                offsite_emergency_contact=form.offsite_emergency_contact.data,
                mitchell_sponsor=form.mitchell_sponsor.data,
                exclusive_use=form.exclusive_use.data,
                organization_status=form.organization_status.data,
                status='pending'
            )
            
            selected_units = Unit.query.filter(Unit.id.in_(form.units.data)).all()
            booking.units.extend(selected_units)
            
            db.session.add(booking)
            db.session.commit()
            notify_admins(booking)
            flash('Booking request submitted successfully')
            return redirect(url_for('index'))
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error while submitting booking: {str(e)}")
            flash('An error occurred while submitting your booking. Please try again later.', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error while submitting booking: {str(e)}")
            flash('An unexpected error occurred. Please try again later.', 'error')
    return render_template('booking_form.html', form=form)

@app.route('/api/bookings/<int:property_id>')
@login_required
def get_bookings(property_id):
    try:
        bookings = Booking.query.join(Booking.units).join(Unit).filter(
            Unit.property_id == property_id,
            Booking.status != 'rejected'
        ).all()
        events = [
            {
                'id': booking.id,
                'title': f'{"PENDING - " if booking.status == "pending" else ""}{booking.guest_name} - {", ".join([unit.name for unit in booking.units])}',
                'start': f"{booking.start_date.isoformat()}T{booking.arrival_time.isoformat()}",
                'end': f"{booking.end_date.isoformat()}T{booking.departure_time.isoformat()}",
                'color': '#a8d08d' if booking.status == 'pending' else '#378006',
                'status': booking.status,
                'guestName': booking.guest_name,
                'guestEmail': booking.guest_email,
                'numGuests': booking.num_guests,
                'arrivalTime': booking.arrival_time.strftime('%H:%M'),
                'departureTime': booking.departure_time.strftime('%H:%M'),
                'units': ', '.join([unit.name for unit in booking.units]),
                'cateringOption': booking.catering_option,
                'specialRequests': booking.special_requests,
                'mobilityImpaired': 'Yes' if booking.mobility_impaired else 'No',
                'eventManagerContact': booking.event_manager_contact,
                'offsiteEmergencyContact': booking.offsite_emergency_contact,
                'mitchellSponsor': booking.mitchell_sponsor,
                'exclusiveUse': booking.exclusive_use,
                'organizationStatus': booking.organization_status
            }
            for booking in bookings
        ]
        return jsonify(events)
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching bookings: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching bookings. Please try again later.'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching bookings: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500

@app.route('/admin')
@login_required
@admin_required
def admin():
    bookings = Booking.query.filter_by(status='pending').all()
    email_form = NotificationEmailForm()
    notification_emails = NotificationEmail.query.all()
    return render_template('admin.html', bookings=bookings, email_form=email_form, notification_emails=notification_emails)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
