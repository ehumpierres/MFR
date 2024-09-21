import os
from flask_mail import Message
from flask import current_app
from icalendar import Calendar, Event
from datetime import datetime

def send_email(subject, body, recipients, ical_attachment=None):
    try:
        msg = Message(subject, recipients=recipients)
        msg.body = body
        
        if ical_attachment:
            msg.attach("event.ics", "text/calendar", ical_attachment)
        
        current_app.extensions['mail'].send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False

def create_ical_invite(booking):
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
