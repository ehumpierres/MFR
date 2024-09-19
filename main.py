import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Property, Unit, Booking, NotificationEmail
from forms import LoginForm, BookingForm, NotificationEmailForm
from config import Config
from functools import wraps
from datetime import date, datetime, timedelta
from flask_mail import Mail, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool
from flask_migrate import Migrate
from icalendar import Calendar, Event
from io import BytesIO
import logging

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(level=logging.DEBUG)
logger = app.logger

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                       poolclass=QueuePool,
                       pool_size=5,
                       max_overflow=10,
                       pool_timeout=30,
                       pool_recycle=1800)
db.session = scoped_session(sessionmaker(bind=engine))

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

app.config['MAIL_SERVER'] = 'smtp-mail.outlook.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
mail = Mail(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
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

def send_notification_email(subject, body, recipients, ical_attachment=None):
    try:
        msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=recipients)
        msg.body = body
        if ical_attachment:
            msg.attach("booking.ics", "text/calendar", ical_attachment)
        mail.send(msg)
        logger.info(f"Email sent successfully to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        logger.error(f"Email details - Subject: {subject}, Recipients: {recipients}")
        logger.error(f"SMTP Server: {app.config['MAIL_SERVER']}, Port: {app.config['MAIL_PORT']}")
        return False

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

        result = send_notification_email(subject, body, admin_emails, ical_attachment)
        logger.debug(f"Result of sending admin notification: {result}")
        return result
    except Exception as e:
        logger.error(f'Error notifying admins for booking {booking.id}: {str(e)}')
        return False

def notify_guest(booking):
    try:
        subject = f"Booking {booking.status.capitalize()}: {booking.unit.property.name}"
        body = f"""Your booking request for {booking.unit.name} from {booking.start_date} to {booking.end_date} has been {booking.status}.
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

        return send_notification_email(subject, body, recipients, ical_attachment)
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
        
        if admin_user and check_password_hash(admin_user.password_hash, form.passphrase.data):
            login_user(admin_user)
            return redirect(url_for('index'))
        elif regular_user and check_password_hash(regular_user.password_hash, form.passphrase.data):
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
    upcoming_bookings = Booking.query.join(Unit).filter(
        Unit.property_id == property_id,
        Booking.status == 'approved',
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
    email_form = NotificationEmailForm()
    notification_emails = NotificationEmail.query.all()
    return render_template('admin.html', bookings=pending_bookings, email_form=email_form, notification_emails=notification_emails)

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
        
        logger.debug(f"Attempting to notify admins for booking {booking_id}")
        admins_notified = notify_admins(booking)
        logger.debug(f"Admin notification result: {admins_notified}")
        
        if not guest_notified or not admins_notified:
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
        bookings = Booking.query.join(Unit).filter(Unit.property_id == property_id).all()
        events = [
            {
                'id': booking.id,
                'title': f'{"PENDING - " if booking.status == "pending" else ""}{booking.guest_name} - {booking.unit.name}',
                'start': f"{booking.start_date.isoformat()}T{booking.arrival_time.isoformat()}",
                'end': f"{booking.end_date.isoformat()}T{booking.departure_time.isoformat()}",
                'color': '#a8d08d' if booking.status == 'pending' else '#378006',
                'status': booking.status
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

def create_sample_data():
    logger.info("Checking if sample data needs to be created")
    try:
        property_count = Property.query.count()
        logger.info(f"Number of existing properties: {property_count}")
        
        if property_count == 0:
            logger.info("Database is empty. Creating sample data...")
            
            Booking.query.delete()
            Unit.query.delete()
            Property.query.delete()
            User.query.delete()
            NotificationEmail.query.delete()
            db.session.commit()
            logger.info("Existing data cleared")

            cbc = Property(name="CBC", description="Log Cabin, Pavilion, Deerfield, Kurth Annex, Kurth House")
            cbm = Property(name="CBM", description="Firemeadow, Sunday House")
            db.session.add_all([cbc, cbm])
            db.session.commit()
            logger.info(f"Created properties: CBC (id: {cbc.id}), CBM (id: {cbm.id})")

            cbc_units = [
                Unit(name="Log Cabin", property_id=cbc.id),
                Unit(name="Pavilion", property_id=cbc.id),
                Unit(name="Deerfield", property_id=cbc.id),
                Unit(name="Kurth Annex", property_id=cbc.id),
                Unit(name="Kurth House", property_id=cbc.id)
            ]
            cbm_units = [
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
            logger.info(f"Created {len(cbc_units)} units for CBC and {len(cbm_units)} units for CBM")

            admin_user = User(username='admin')
            admin_user.set_password('admin_passphrase')
            regular_user = User(username='user')
            regular_user.set_password('user_passphrase')
            db.session.add_all([admin_user, regular_user])
            db.session.commit()
            logger.info("Created admin and regular user accounts")

            logger.info("Sample data created successfully")
        else:
            logger.info("Database is not empty. Skipping sample data creation.")
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error while creating sample data: {str(e)}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error while creating sample data: {str(e)}")

def test_db_connection():
    try:
        db.session.execute(text('SELECT 1'))
        logger.info("Database connection successful")
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

if __name__ == '__main__':
    with app.app_context():
        try:
            test_db_connection()
            db.create_all()
            create_sample_data()
            logger.info("Application setup completed successfully")
        except Exception as e:
            logger.error(f"Error during application setup: {str(e)}")
    
    app.run(host='0.0.0.0', port=5000)