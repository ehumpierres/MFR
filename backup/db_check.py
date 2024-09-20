from flask import Flask
from sqlalchemy import inspect
from datetime import date, time
from models import db, User, Property, Unit, Booking, NotificationEmail
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def get_table_info(table):
    return {
        "name": table.name,
        "columns": [column.name for column in table.columns],
        "foreign_keys": [fk.target_fullname for fk in table.foreign_keys],
        "indexes": [index.name for index in table.indexes]
    }

with app.app_context():
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    
    print("Database Tables:")
    for table_name in table_names:
        print(f"\nTable: {table_name}")
        columns = inspector.get_columns(table_name)
        print("Columns:")
        for column in columns:
            print(f"  - {column['name']} ({column['type']})")
        
        foreign_keys = inspector.get_foreign_keys(table_name)
        if foreign_keys:
            print("Foreign Keys:")
            for fk in foreign_keys:
                print(f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")

    print("\nModel Definitions:")
    models = [User, Property, Unit, Booking, NotificationEmail]
    for model in models:
        table_info = get_table_info(model.__table__)
        print(f"\nModel: {model.__name__}")
        print(f"Table: {table_info['name']}")
        print("Columns:", ', '.join(table_info['columns']))
        if table_info['foreign_keys']:
            print("Foreign Keys:", ', '.join(table_info['foreign_keys']))
        if table_info['indexes']:
            print("Indexes:", ', '.join(table_info['indexes']))

    print("\nChecking 'booking_units' association table:")
    if 'booking_units' in table_names:
        booking_units_columns = inspector.get_columns('booking_units')
        print("Columns:")
        for column in booking_units_columns:
            print(f"  - {column['name']} ({column['type']})")
        
        booking_units_fks = inspector.get_foreign_keys('booking_units')
        if booking_units_fks:
            print("Foreign Keys:")
            for fk in booking_units_fks:
                print(f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
    else:
        print("'booking_units' table not found in the database.")

    print("\nTesting booking insertion:")
    try:
        test_booking = Booking(
            start_date=date(2024, 10, 1),
            end_date=date(2024, 10, 5),
            arrival_time=time(14, 0),
            departure_time=time(11, 0),
            guest_name="Test User",
            guest_email="test@example.com",
            num_guests=2,
            status="pending",
            catering_option="Bring own food",
            special_requests="None",
            mobility_impaired=False,
            event_manager_contact="Test Manager",
            offsite_emergency_contact="Test Emergency",
            mitchell_sponsor="Test Sponsor",
            exclusive_use="Open to sharing",
            organization_status="Personal use"
        )
        test_unit = Unit.query.first()
        if test_unit:
            test_booking.units.append(test_unit)
            db.session.add(test_booking)
            db.session.commit()
            print("Test booking inserted successfully.")
            db.session.delete(test_booking)
            db.session.commit()
            print("Test booking deleted.")
        else:
            print("No units found in the database. Cannot test booking insertion.")
    except Exception as e:
        print(f"Error inserting test booking: {str(e)}")
        db.session.rollback()
