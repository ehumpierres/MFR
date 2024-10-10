import os
from flask import Flask, render_template, flash, redirect, url_for, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_mail import Mail 
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool
from datetime import datetime, date, time, timedelta
from forms import LoginForm, BookingForm, NotificationEmailForm
from models import db, User, Property, Unit, Booking, NotificationEmail
from config import Config
import logging
from io import StringIO, BytesIO
import csv
from email_utils import send_email, create_ical_invite
import secrets
from functools import wraps
from icalendar import Calendar, Event

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

# ... (keep all existing routes and functions)

@app.route('/change_booking_status/<int:booking_id>', methods=['POST'])
@login_required
@admin_required
def change_booking_status(booking_id):
    try:
        data = request.json
        new_status = data.get('status')

        if new_status not in ['pending', 'approved', 'rejected']:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400

        booking = Booking.query.get_or_404(booking_id)
        old_status = booking.status
        booking.status = new_status
        db.session.commit()

        if old_status != new_status:
            if new_status in ['approved', 'rejected']:
                notify_guest(booking)

        return jsonify({'success': True, 'message': 'Booking status updated successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error while changing booking status: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while updating the booking status'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error while changing booking status: {str(e)}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred'}), 500

def notify_guest(booking):
    subject = f"Booking {booking.status.capitalize()}: {booking.unit.property.name}"
    body = f"""Dear {booking.guest_name},

Your booking request for {booking.unit.name} from {booking.start_date} to {booking.end_date} has been {booking.status}.

Booking Details:
Arrival Time: {booking.arrival_time}
Departure Time: {booking.departure_time}
Number of Guests: {booking.num_guests}
Catering Option: {booking.catering_option}
Special Requests: {booking.special_requests}
Mobility Impaired: {'Yes' if booking.mobility_impaired else 'No'}
Event Manager Contact: {booking.event_manager_contact}
Offsite Emergency Contact: {booking.offsite_emergency_contact}
Mitchell Sponsor: {booking.mitchell_sponsor}
Exclusive Use: {booking.exclusive_use}
Organization Status: {booking.organization_status}

If you have any questions, please contact us.

Thank you for using our booking system.
"""
    
    recipients = [booking.guest_email]
    
    if booking.status == 'approved':
        ical_attachment = create_ical_invite(booking)
        admin_emails = [email.email for email in NotificationEmail.query.all()]
        if admin_emails:
            recipients.extend(admin_emails)
    else:
        ical_attachment = None

    send_email(subject, body, recipients, ical_attachment)

# ... (keep all existing code at the end of the file)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

logger.info("Flask application has stopped")
