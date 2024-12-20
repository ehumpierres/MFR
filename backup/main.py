import os
from flask import Flask, render_template, flash, redirect, url_for, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_mail import Mail 
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, create_engine, or_
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
        if not current_user.is_authenticated:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def generate_ical(booking):
    cal = Calendar()
    cal.add('prodid', '-//Mitchell Property Booking System//mxm.dk//')
    cal.add('version', '2.0')

    event = Event()
    event.add('summary', f"Booking: {booking.guest_name} - {booking.unit.property.name} - {booking.unit.name}")
    event.add('dtstart', datetime.combine(booking.start_date, booking.arrival_time))
    event.add('dtend', datetime.combine(booking.end_date, booking.departure_time))
    event.add('description', f"Guest: {booking.guest_name}\nNumber of Guests: {booking.num_guests}")
    event.add('organizer', booking.guest_name)
    event.add('location', f"{booking.unit.property.name} - {booking.unit.name}")

    cal.add_component(event)
    return cal.to_ical()

def notify_admins(booking):
    try:
        subject = f"New Booking Request: {booking.guest_name}"
        body = f"""A new booking request has been submitted:
Guest: {booking.guest_name}
Unit: {booking.unit.name}
Dates: {booking.start_date} to {booking.end_date}
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
Organization Status: {booking.organization_status}"""
        admin_emails = [email.email for email in NotificationEmail.query.all()]
        logger.debug(f"Number of admin emails fetched: {len(admin_emails)}")
        
        if not admin_emails:
            logger.warning("No admin emails found. Skipping admin notification.")
            return False

        ical_attachment = generate_ical(booking)
        if not ical_attachment:
            logger.error("Failed to generate iCal attachment")
            return False

        result = send_email(subject, body, admin_emails, ical_attachment)
        logger.debug(f"Result of sending admin notification: {result}")
        return result
    except Exception as e:
        logger.error(f'Error notifying admins for booking {booking.id}: {str(e)}')
        return False

def notify_guest(booking):
    try:
        subject = f"Booking {booking.status.capitalize()}: {booking.unit.property.name}"
        body = f"""{booking.guest_name} your booking request for {booking.unit.name} from {booking.start_date} to {booking.end_date} has been {booking.status}.
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
Organization Status: {booking.organization_status}"""
        
        ical_attachment = generate_ical(booking) if booking.status == 'approved' else None

        recipients = [booking.guest_email]

        if booking.status == 'approved':
            admin_emails = [email.email for email in NotificationEmail.query.all()]
            if admin_emails:
                recipients.extend(admin_emails)

        return send_email(subject, body, recipients, ical_attachment)
    except Exception as e:
        logger.error(f'Error notifying guest for booking {booking.id}: {str(e)}')
        return False

@app.route('/')
@login_required
def index():
    logger.info("Fetching properties for index page")
    properties = Property.query.all()
    logger.info(f"Number of properties fetched: {len(properties)}")
    return render_template('properties.html', properties=properties)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        admin_user = User.query.filter_by(username='admin').first()
        regular_user = User.query.filter_by(username='user').first()

        logger.debug(f"Admin passphrase from config: {app.config['ADMIN_PASSPHRASE']}")
        logger.debug(f"User passphrase from config: {app.config['USER_PASSPHRASE']}")
        logger.debug(f"Submitted passphrase: {form.passphrase.data}")
        logger.debug(f"Admin user found: {admin_user is not None}")
        logger.debug(f"Regular user found: {regular_user is not None}")

        if admin_user and form.passphrase.data == app.config['ADMIN_PASSPHRASE']:
            logger.debug("Admin login successful")
            login_user(admin_user)
            return redirect(url_for('index'))
        elif regular_user and form.passphrase.data == app.config['USER_PASSPHRASE']:
            logger.debug("Regular user login successful")
            login_user(regular_user)
            return redirect(url_for('index'))

        logger.debug("Invalid passphrase")
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
    upcoming_bookings = Booking.query.join(Unit).filter(
        Unit.property_id == property_id,
        or_(Booking.status == 'approved', Booking.status == 'pending'),
        Booking.start_date >= date.today()
    ).order_by(Booking.start_date).all()
    return render_template('property_details.html', property=property, upcoming_bookings=upcoming_bookings)

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    form = BookingForm()
    form.unit_id.choices = [(unit.id, f"{unit.property.name} - {unit.name}") for unit in Unit.query.join(Property).all()]
    if form.validate_on_submit():
        try:
            booking = Booking(
                unit_id=form.unit_id.data,
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

@app.route('/admin')
@login_required
@admin_required
def admin():
    pending_bookings = Booking.query.filter_by(status='pending').join(Unit).join(Property).all()
    approved_bookings = Booking.query.filter_by(status='approved').join(Unit).join(Property).all()
    email_form = NotificationEmailForm()
    notification_emails = NotificationEmail.query.all()
    return render_template('admin.html', pending_bookings=pending_bookings, approved_bookings=approved_bookings, email_form=email_form, notification_emails=notification_emails)

@app.route('/admin/add_notification_email', methods=['POST'])
@login_required
@admin_required
def add_notification_email():
    form = NotificationEmailForm()
    if form.validate_on_submit():
        try:
            email = NotificationEmail(email=form.email.data)
            db.session.add(email)
            db.session.commit()
            flash('Notification email added successfully')
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error while adding notification email: {str(e)}")
            flash('An error occurred while adding the notification email. Please try again later.', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error while adding notification email: {str(e)}")
            flash('An unexpected error occurred. Please try again later.', 'error')
    return redirect(url_for('admin'))

@app.route('/admin/remove_notification_email/<int:email_id>')
@login_required
@admin_required
def remove_notification_email(email_id):
    try:
        email = NotificationEmail.query.get_or_404(email_id)
        db.session.delete(email)
        db.session.commit()
        flash('Notification email removed successfully')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error while removing notification email: {str(e)}")
        flash('An error occurred while removing the notification email. Please try again later.', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error while removing notification email: {str(e)}")
        flash('An unexpected error occurred. Please try again later.', 'error')
    return redirect(url_for('admin'))

@app.route('/approve/<int:booking_id>', methods=['POST'])
@login_required
@admin_required
def approve_booking(booking_id):
    try:
        booking = Booking.query.get_or_404(booking_id)
        booking.status = 'approved'
        db.session.commit()
        
        logger.debug(f"Attempting to notify guest for booking {booking_id}")
        guest_notified = notify_guest(booking)
        logger.debug(f"Guest notification result: {guest_notified}")
        
        if not guest_notified:
            logger.warning(f"Failed to send some notifications for booking {booking_id}")
            flash('Booking approved, but there was an issue sending notifications.', 'warning')
        else:
            flash('Booking approved and notifications sent successfully.', 'success')
        
        return jsonify({
            'id': booking.id,
            'title': f'{booking.guest_name} - {booking.unit.name}',
            'color': '#378006',
            'status': 'approved'
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error while approving booking: {str(e)}")
        return jsonify({'error': 'An error occurred while approving the booking. Please try again later.'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error while approving booking: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500

@app.route('/reject/<int:booking_id>')
@login_required
@admin_required
def reject_booking(booking_id):
    try:
        booking = Booking.query.get_or_404(booking_id)
        booking.status = 'rejected'
        db.session.commit()
        
        if notify_guest(booking):
            flash('Booking rejected and guest notified.', 'success')
        else:
            flash('Booking rejected, but there was an issue notifying the guest.', 'warning')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error while rejecting booking: {str(e)}")
        flash('An error occurred while rejecting the booking. Please try again later.', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error while rejecting booking: {str(e)}")
        flash('An unexpected error occurred. Please try again later.', 'error')
    return redirect(url_for('admin'))

@app.route('/api/bookings/<int:property_id>')
@login_required
def get_bookings(property_id):
    try:
        bookings = Booking.query.join(Unit).filter(
            Unit.property_id == property_id,
            Booking.status != 'rejected'
        ).all()
        events = [
            {
                'id': booking.id,
                'title': f'{"PENDING - " if booking.status == "pending" else ""}{booking.guest_name} - {booking.unit.name}',
                'start': f"{booking.start_date.isoformat()}T{booking.arrival_time.isoformat()}",
                'end': f"{booking.end_date.isoformat()}T{booking.departure_time.isoformat()}",
                'color': '#a8d08d' if booking.status == 'pending' else '#378006',
                'status': booking.status,
                'guestName': booking.guest_name,
                'guestEmail': booking.guest_email,
                'numGuests': booking.num_guests,
                'arrivalTime': booking.arrival_time.strftime('%H:%M'),
                'departureTime': booking.departure_time.strftime('%H:%M'),
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

@app.route('/admin/database', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_database():
    if request.method == 'POST':
        operation = request.form.get('operation')
        if operation == 'add_property':
            name = request.form.get('property_name')
            description = request.form.get('property_description')
            new_property = Property(name=name, description=description)
            db.session.add(new_property)
            db.session.commit()
            flash('Property added successfully', 'success')
        elif operation == 'add_unit':
            property_id = request.form.get('property_id')
            unit_name = request.form.get('unit_name')
            new_unit = Unit(name=unit_name, property_id=property_id)
            db.session.add(new_unit)
            db.session.commit()
            flash('Unit added successfully', 'success')
        elif operation == 'delete_property':
            property_id = request.form.get('property_id')
            property_to_delete = Property.query.get(property_id)
            if property_to_delete:
                db.session.delete(property_to_delete)
                db.session.commit()
                flash('Property deleted successfully', 'success')
            else:
                flash('Property not found', 'error')
        elif operation == 'delete_unit':
            unit_id = request.form.get('unit_id')
            unit_to_delete = Unit.query.get(unit_id)
            if unit_to_delete:
                db.session.delete(unit_to_delete)
                db.session.commit()
                flash('Unit deleted successfully', 'success')
            else:
                flash('Unit not found', 'error')
    
    properties = Property.query.all()
    units = Unit.query.all()
    return render_template('admin_database.html', properties=properties, units=units)

@app.route('/test_email')
@login_required
@admin_required
def test_email():
    try:
        test_unit = Unit.query.first()
        if not test_unit:
            return "No units available for testing", 400

        test_booking = Booking(
            unit_id=test_unit.id,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=10),
            arrival_time=datetime.now().time(),
            departure_time=(datetime.now() + timedelta(hours=3)).time(),
            guest_name="Test Guest",
            guest_email=app.config['MAIL_USERNAME'],
            num_guests=2,
            catering_option="Bring own food",
            special_requests="Test request",
            mobility_impaired=False,
            event_manager_contact="Test Manager",
            offsite_emergency_contact="Test Emergency",
            mitchell_sponsor="Test Sponsor",
            exclusive_use="Open to sharing",
            organization_status="Personal use",
            status='approved'
        )
        db.session.add(test_booking)
        db.session.commit()

        if notify_guest(test_booking):
            return "Test email with calendar invite sent successfully. Please check your inbox."
        else:
            return "Failed to send test email", 500

    except Exception as e:
        logger.error(f"Failed to send test email: {str(e)}")
        return f"Failed to send test email: {str(e)}", 500

@app.route('/admin/download_csv')
@login_required
@admin_required
def download_csv():
    try:
        bookings = Booking.query.all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'Property', 'Unit', 'Guest Name', 'Start Date', 'End Date', 'Arrival Time', 'Departure Time', 'Guest Email', 'Number of Guests', 'Status', 'Catering Option', 'Special Requests', 'Mobility Impaired', 'Event Manager Contact', 'Offsite Emergency Contact', 'Mitchell Sponsor', 'Exclusive Use', 'Organization Status'])
        
        for booking in bookings:
            writer.writerow([
                booking.id,
                booking.unit.property.name,
                booking.unit.name,
                booking.guest_name,
                booking.start_date,
                booking.end_date,
                booking.arrival_time,
                booking.departure_time,
                booking.guest_email,
                booking.num_guests,
                booking.status,
                booking.catering_option,
                booking.special_requests,
                'Yes' if booking.mobility_impaired else 'No',
                booking.event_manager_contact,
                booking.offsite_emergency_contact,
                booking.mitchell_sponsor,
                booking.exclusive_use,
                booking.organization_status
            ])
        
        output.seek(0)
        return send_file(BytesIO(output.getvalue().encode()),
                         mimetype='text/csv',
                         as_attachment=True,
                         download_name='bookings.csv')
    except Exception as e:
        logger.error(f"Error generating CSV: {str(e)}")
        flash('An error occurred while generating the CSV file.', 'error')
        return redirect(url_for('admin'))

@app.route('/delete_booking/<int:booking_id>', methods=['POST'])
@login_required
@admin_required
def delete_booking(booking_id):
    try:
        booking = Booking.query.get_or_404(booking_id)
        db.session.delete(booking)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Booking deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting booking: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while deleting the booking'}), 500

def create_sample_data():
    if User.query.first() is not None:
        logger.info("Sample data already exists. Skipping creation.")
        return
    
    logger.info("Creating sample data...")
    try:
        # Clear existing data
        Booking.query.delete()
        Unit.query.delete()
        Property.query.delete()
        User.query.delete()
        db.session.commit()
        
        # db.session.query(Unit).delete()
        # db.session.query(Property).delete()
        # db.session.query(User).delete()
        # db.session.commit() 

        cbc = Property(name="CBC", description="Log Cabin, Pavilion, Deerfield, Kurth Annex, Kurth House")
        cbm = Property(name="CBM", description="Firemeadow, Sunday House")
        db.session.add_all([cbc, cbm])
        db.session.commit()

        cbc_units = [
            Unit(name="Log Cabin", property_id=cbc.id),
            Unit(name="Pavilion", property_id=cbc.id),
            Unit(name="Deerfield", property_id=cbc.id),
            Unit(name="Kurth Annex", property_id=cbc.id),
            Unit(name="Kurth House", property_id=cbc.id)
        ]
        cbm_units = [
            Unit(name="Firemeadow - ALL", property_id=cbm.id),
            Unit(name="Firemeadow - Main Lodge", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 0", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 1", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 2", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 3", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 4", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 5", property_id=cbm.id),
            Unit(name="Firemeadow - Cabin 6", property_id=cbm.id),
            Unit(name="Firemeadow - Meadowlark", property_id=cbm.id),
            Unit(name="Firemeadow - Mariposa", property_id=cbm.id),
            Unit(name="Firemeadow - Magnolia", property_id=cbm.id),
            Unit(name="Firemeadow - Pinehurst", property_id=cbm.id),
            Unit(name="Firemeadow - Montgomery", property_id=cbm.id),
            Unit(name="Sunday House", property_id=cbm.id)
            
        ]
        db.session.add_all(cbc_units + cbm_units)
        db.session.commit()

        admin_user = User(username='admin')
        admin_user.set_password(app.config['ADMIN_PASSPHRASE'])
        regular_user = User(username='user')
        regular_user.set_password(app.config['USER_PASSPHRASE'])
        db.session.add_all([admin_user, regular_user])
        db.session.commit()

        logger.info("Sample data created successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating sample data: {str(e)}")

def init_db():
    with app.app_context():
        db.create_all()
        create_sample_data()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

logger.info("Flask application has stopped")