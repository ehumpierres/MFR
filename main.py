import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Property, Unit, Booking, NotificationEmail
from forms import LoginForm, BookingForm, NotificationEmailForm
from config import Config
from functools import wraps
from datetime import date
from flask_mail import Mail, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool

app = Flask(__name__)
app.config.from_object(Config)

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'],
                       poolclass=QueuePool,
                       pool_size=5,
                       max_overflow=10,
                       pool_timeout=30,
                       pool_recycle=1800)
db.session = scoped_session(sessionmaker(bind=engine))

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
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

def send_notification_email(subject, body, recipients):
    try:
        msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=recipients)
        msg.body = body
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Failed to send email: {str(e)}")
        pass

def notify_admins(booking):
    subject = f"New Booking Request: {booking.guest_name}"
    body = f"""A new booking request has been submitted:
Guest: {booking.guest_name}
Units: {', '.join([unit.name for unit in booking.units])}
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
    send_notification_email(subject, body, admin_emails)

def notify_guest(booking):
    subject = f"Booking {booking.status.capitalize()}: {booking.units[0].property.name}"
    body = f"""Your booking request for {', '.join([unit.name for unit in booking.units])} from {booking.start_date} to {booking.end_date} has been {booking.status}.
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
    send_notification_email(subject, body, [booking.guest_email])

@app.route('/')
@login_required
def index():
    app.logger.info("Fetching properties for index page")
    properties = Property.query.all()
    app.logger.info(f"Number of properties fetched: {len(properties)}")
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
    upcoming_bookings = Booking.query.join(Booking.units).filter(
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
            booking.units = [Unit.query.get(form.unit_id.data)]
            db.session.add(booking)
            db.session.commit()
            notify_admins(booking)
            flash('Booking request submitted successfully')
            return redirect(url_for('index'))
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.error(f"Database error while submitting booking: {str(e)}")
            flash('An error occurred while submitting your booking. Please try again later.', 'error')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Unexpected error while submitting booking: {str(e)}")
            flash('An unexpected error occurred. Please try again later.', 'error')
    return render_template('booking_form.html', form=form)

@app.route('/admin')
@login_required
@admin_required
def admin():
    pending_bookings = Booking.query.filter_by(status='pending').all()
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
            app.logger.error(f"Database error while adding notification email: {str(e)}")
            flash('An error occurred while adding the notification email. Please try again later.', 'error')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Unexpected error while adding notification email: {str(e)}")
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
        app.logger.error(f"Database error while removing notification email: {str(e)}")
        flash('An error occurred while removing the notification email. Please try again later.', 'error')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error while removing notification email: {str(e)}")
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
        notify_guest(booking)
        return jsonify({
            'id': booking.id,
            'title': f'{booking.guest_name} - {", ".join([unit.name for unit in booking.units])}',
            'color': '#378006',
            'status': 'approved'
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error while approving booking: {str(e)}")
        return jsonify({'error': 'An error occurred while approving the booking. Please try again later.'}), 500
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error while approving booking: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again later.'}), 500

@app.route('/reject/<int:booking_id>')
@login_required
@admin_required
def reject_booking(booking_id):
    try:
        booking = Booking.query.get_or_404(booking_id)
        booking.status = 'rejected'
        db.session.commit()
        notify_guest(booking)
        flash('Booking rejected')
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error while rejecting booking: {str(e)}")
        flash('An error occurred while rejecting the booking. Please try again later.', 'error')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error while rejecting booking: {str(e)}")
        flash('An unexpected error occurred. Please try again later.', 'error')
    return redirect(url_for('admin'))

@app.route('/api/bookings/<int:property_id>')
@login_required
def get_bookings(property_id):
    try:
        bookings = Booking.query.join(Booking.units).filter(Unit.property_id == property_id).all()
        events = [
            {
                'id': booking.id,
                'title': f'{"PENDING - " if booking.status == "pending" else ""}{booking.guest_name} - {", ".join([unit.name for unit in booking.units])}',
                'start': f"{booking.start_date.isoformat()}T{booking.arrival_time.isoformat()}",
                'end': f"{booking.end_date.isoformat()}T{booking.departure_time.isoformat()}",
                'color': '#a8d08d' if booking.status == 'pending' else '#378006',
                'status': booking.status
            }
            for booking in bookings
        ]
        return jsonify(events)
    except SQLAlchemyError as e:
        app.logger.error(f"Database error while fetching bookings: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching bookings. Please try again later.'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error while fetching bookings: {str(e)}")
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

def create_sample_data():
    app.logger.info("Attempting to create sample data")
    try:
        Booking.query.delete()
        Unit.query.delete()
        Property.query.delete()
        db.session.commit()

        cbc = Property(name="CBC", description="Coastal Beach Club")
        cbm = Property(name="CBM", description="Coastal Beach Meadow")
        db.session.add_all([cbc, cbm])
        db.session.commit()

        cbc_units = [
            Unit(name="Log Cabin", property_id=cbc.id),
            Unit(name="Pavilion", property_id=cbc.id),
            Unit(name="Deerfield", property_id=cbc.id),
            Unit(name="Kurth Annex", property_id=cbc.id),
            Unit(name="Kurth House", property_id=cbc.id)
        ]
        cbm_units = [Unit(name=f"CBM Unit {i}", property_id=cbm.id) for i in range(1, 7)]
        db.session.add_all(cbc_units + cbm_units)
        db.session.commit()

        admin_user = User(username='admin')
        admin_user.set_password('admin_passphrase')
        regular_user = User(username='user')
        regular_user.set_password('user_passphrase')
        db.session.add_all([admin_user, regular_user])
        db.session.commit()

        app.logger.info("Sample data created successfully")
    except SQLAlchemyError as e:
        db.session.rollback()
        app.logger.error(f"Database error while creating sample data: {str(e)}")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Unexpected error while creating sample data: {str(e)}")

def test_db_connection():
    try:
        db.session.execute(text('SELECT 1'))
        app.logger.info("Database connection successful")
    except SQLAlchemyError as e:
        app.logger.error(f"Database connection failed: {str(e)}")
        raise

if __name__ == '__main__':
    with app.app_context():
        test_db_connection()
        db.create_all()
        create_sample_data()
    
    app.run(host='0.0.0.0', port=5000)
