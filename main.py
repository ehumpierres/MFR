from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Property, Unit, Booking, NotificationEmail
from forms import LoginForm, BookingForm, NotificationEmailForm
from config import Config
from functools import wraps
from datetime import date
import os
from flask_mail import Mail, Message

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Update email configuration
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
        # Continue with the application flow even if email sending fails
        pass

def notify_admins(booking):
    subject = f"New Booking Request: {booking.guest_name}"
    body = f"A new booking request has been submitted:\nGuest: {booking.guest_name}\nUnit: {booking.unit.name}\nDates: {booking.start_date} to {booking.end_date}"
    admin_emails = [email.email for email in NotificationEmail.query.all()]
    send_notification_email(subject, body, admin_emails)

def notify_guest(booking):
    subject = f"Booking {booking.status.capitalize()}: {booking.unit.property.name} - {booking.unit.name}"
    body = f"Your booking request for {booking.unit.property.name} - {booking.unit.name} from {booking.start_date} to {booking.end_date} has been {booking.status}."
    send_notification_email(subject, body, [booking.guest_email])

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
                guest_name=form.guest_name.data,
                guest_email=form.guest_email.data,
                status='pending'
            )
            db.session.add(booking)
            db.session.commit()
            notify_admins(booking)
            flash('Booking request submitted successfully')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error submitting booking: {str(e)}")
            flash('An error occurred while submitting your booking. Please try again.', 'error')
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
        email = NotificationEmail(email=form.email.data)
        db.session.add(email)
        db.session.commit()
        flash('Notification email added successfully')
    return redirect(url_for('admin'))

@app.route('/admin/remove_notification_email/<int:email_id>')
@login_required
@admin_required
def remove_notification_email(email_id):
    email = NotificationEmail.query.get_or_404(email_id)
    db.session.delete(email)
    db.session.commit()
    flash('Notification email removed successfully')
    return redirect(url_for('admin'))

@app.route('/approve/<int:booking_id>', methods=['POST'])
@login_required
@admin_required
def approve_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'approved'
    db.session.commit()
    notify_guest(booking)
    return jsonify({
        'id': booking.id,
        'title': f'{booking.guest_name} - {booking.unit.name}',
        'color': '#378006',
        'status': 'approved'
    })

@app.route('/reject/<int:booking_id>')
@login_required
@admin_required
def reject_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'rejected'
    db.session.commit()
    notify_guest(booking)
    flash('Booking rejected')
    return redirect(url_for('admin'))

@app.route('/api/bookings/<int:property_id>')
@login_required
def get_bookings(property_id):
    bookings = Booking.query.join(Unit).filter(Unit.property_id == property_id).all()
    events = [
        {
            'id': booking.id,
            'title': f'{"PENDING - " if booking.status == "pending" else ""}{booking.guest_name} - {booking.unit.name}',
            'start': booking.start_date.isoformat(),
            'end': booking.end_date.isoformat(),
            'color': '#a8d08d' if booking.status == 'pending' else '#378006',
            'status': booking.status
        }
        for booking in bookings
    ]
    return jsonify(events)

def create_sample_data():
    # Create sample properties
    beach_house = Property(name="Beach House", description="A beautiful house by the beach")
    mountain_cabin = Property(name="Mountain Cabin", description="A cozy cabin in the mountains")
    db.session.add_all([beach_house, mountain_cabin])
    db.session.commit()

    # Create sample units for Beach House (7 units)
    beach_house_units = [
        Unit(name="Main House", property_id=beach_house.id),
        Unit(name="Guest House", property_id=beach_house.id),
        Unit(name="Beach Bungalow 1", property_id=beach_house.id),
        Unit(name="Beach Bungalow 2", property_id=beach_house.id),
        Unit(name="Beach Bungalow 3", property_id=beach_house.id),
        Unit(name="Poolside Suite", property_id=beach_house.id),
        Unit(name="Oceanview Loft", property_id=beach_house.id)
    ]

    # Create sample units for Mountain Cabin (6 units)
    mountain_cabin_units = [
        Unit(name="Main Cabin", property_id=mountain_cabin.id),
        Unit(name="Treehouse Suite", property_id=mountain_cabin.id),
        Unit(name="Hillside Cottage", property_id=mountain_cabin.id),
        Unit(name="Lakeside Cabin", property_id=mountain_cabin.id),
        Unit(name="Forest Retreat", property_id=mountain_cabin.id),
        Unit(name="Mountain View Lodge", property_id=mountain_cabin.id)
    ]

    db.session.add_all(beach_house_units + mountain_cabin_units)
    db.session.commit()

    # Create admin and regular user
    admin_user = User(username='admin')
    admin_user.set_password('admin_passphrase')
    regular_user = User(username='user')
    regular_user.set_password('user_passphrase')
    db.session.add_all([admin_user, regular_user])
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()  # Drop all existing tables
        db.create_all()  # Create new tables
        create_sample_data()  # Add sample data
    app.run(host='0.0.0.0', port=5000)
