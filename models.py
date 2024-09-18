from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.username == 'admin'

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    units = db.relationship('Unit', backref='property', lazy=True)

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)

booking_units = db.Table('booking_units',
    db.Column('booking_id', db.Integer, db.ForeignKey('booking.id'), primary_key=True),
    db.Column('unit_id', db.Integer, db.ForeignKey('unit.id'), primary_key=True)
)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    units = db.relationship('Unit', secondary=booking_units, lazy='subquery', backref=db.backref('bookings', lazy=True))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    arrival_time = db.Column(db.Time, nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    guest_name = db.Column(db.String(100), nullable=False)
    guest_email = db.Column(db.String(100), nullable=False)
    num_guests = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    catering_option = db.Column(db.String(20), nullable=False)
    special_requests = db.Column(db.Text)
    mobility_impaired = db.Column(db.Boolean, nullable=False)
    event_manager_contact = db.Column(db.String(200), nullable=False)
    offsite_emergency_contact = db.Column(db.String(200), nullable=False)
    mitchell_sponsor = db.Column(db.String(100), nullable=False)
    exclusive_use = db.Column(db.String(20), nullable=False)
    organization_status = db.Column(db.String(50), nullable=False)

class NotificationEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
