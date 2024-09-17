from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Property, Unit, Booking
from forms import LoginForm, BookingForm
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    properties = Property.query.all()
    return render_template('properties.html', properties=properties)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username='admin').first()
        if user and check_password_hash(user.password_hash, form.passphrase.data):
            login_user(user)
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
    return render_template('property_details.html', property=property)

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    form = BookingForm()
    form.unit_id.choices = [(unit.id, f"{unit.property.name} - {unit.name}") for unit in Unit.query.join(Property).all()]
    if form.validate_on_submit():
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
        flash('Booking request submitted successfully')
        return redirect(url_for('index'))
    return render_template('booking_form.html', form=form)

@app.route('/admin')
@login_required
def admin():
    if current_user.username != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    pending_bookings = Booking.query.filter_by(status='pending').all()
    return render_template('admin.html', bookings=pending_bookings)

@app.route('/approve/<int:booking_id>')
@login_required
def approve_booking(booking_id):
    if current_user.username != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'approved'
    db.session.commit()
    flash('Booking approved')
    return redirect(url_for('admin'))

@app.route('/reject/<int:booking_id>')
@login_required
def reject_booking(booking_id):
    if current_user.username != 'admin':
        flash('Access denied')
        return redirect(url_for('index'))
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'rejected'
    db.session.commit()
    flash('Booking rejected')
    return redirect(url_for('admin'))

@app.route('/api/bookings/<int:property_id>')
@login_required
def get_bookings(property_id):
    bookings = Booking.query.join(Unit).filter(Unit.property_id == property_id, Booking.status == 'approved').all()
    events = [
        {
            'title': f'{booking.guest_name} - {booking.unit.name}',
            'start': booking.start_date.isoformat(),
            'end': booking.end_date.isoformat()
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

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()  # Drop all existing tables
        db.create_all()  # Create new tables
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', password_hash=generate_password_hash('admin_passphrase'))
            db.session.add(admin_user)
            db.session.commit()
        create_sample_data()  # Add sample data
    app.run(host='0.0.0.0', port=5000)
