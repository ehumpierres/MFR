import os
from flask_mail import Message
from flask import current_app
from icalendar import Calendar, Event
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import time
from typing import List, Optional

def send_email_with_retry(subject: str, body: str, recipients: List[str], 
                         ical_attachment: Optional[bytes] = None, max_retries: int = 3) -> bool:
    """
    Send an email with retry logic and better error handling
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Create MIME message
            msg = MIMEMultipart()
            msg['Subject'] = subject
            msg['From'] = current_app.config['MAIL_USERNAME']
            msg['To'] = ', '.join(recipients)

            # Add body
            msg.attach(MIMEText(body, 'plain'))

            # Add calendar attachment if provided
            if ical_attachment:
                cal_attachment = MIMEApplication(
                    ical_attachment,
                    _subtype='ics'
                )
                cal_attachment.add_header(
                    'Content-Disposition',
                    'attachment; filename="event.ics"'
                )
                msg.attach(cal_attachment)

            # Setup SMTP connection with TLS for Outlook
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], 
                            current_app.config['MAIL_PORT']) as server:
                server.starttls()  # Enable TLS
                server.login(
                    current_app.config['MAIL_USERNAME'],
                    current_app.config['MAIL_PASSWORD']
                )
                server.send_message(msg)

            current_app.logger.info(f"Email sent successfully to {recipients}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            current_app.logger.error(f"SMTP Authentication failed: {str(e)}")
            return False  # Don't retry for auth errors

        except (smtplib.SMTPException, ConnectionError) as e:
            retry_count += 1
            if retry_count == max_retries:
                current_app.logger.error(f"Failed to send email after {max_retries} attempts: {str(e)}")
                return False
            
            # Exponential backoff: 2, 4, 8 seconds between retries
            wait_time = 2 ** retry_count
            current_app.logger.warning(
                f"Email sending attempt {retry_count} failed. Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)

        except Exception as e:
            current_app.logger.error(f"Unexpected error sending email: {str(e)}")
            return False

def create_ical_invite(booking) -> bytes:
    """
    Create an iCalendar invitation for a booking
    """
    try:
        cal = Calendar()
        cal.add('prodid', '-//Mitchell Property Booking System//mxm.dk//')
        cal.add('version', '2.0')
        cal.add('method', 'REQUEST')  # This makes it an invitation

        event = Event()
        event.add('summary', f"Booking: {booking.guest_name} - {booking.unit.property.name} - {booking.unit.name}")
        event.add('dtstart', datetime.combine(booking.start_date, booking.arrival_time))
        event.add('dtend', datetime.combine(booking.end_date, booking.departure_time))
        event.add('description', f"""
Guest: {booking.guest_name}
Number of Guests: {booking.num_guests}
Property: {booking.unit.property.name}
Unit: {booking.unit.name}
Special Requests: {booking.special_requests}
        """.strip())
        
        # Add unique identifier
        event.add('uid', f'booking-{booking.id}@mitchell-properties.com')
        
        # Add status
        event.add('status', 'CONFIRMED')
        
        # Add organizer
        event.add('organizer', f'mailto:{current_app.config["MAIL_USERNAME"]}')
        
        # Add location
        event.add('location', f"{booking.unit.property.name} - {booking.unit.name}")

        cal.add_component(event)
        return cal.to_ical()

    except Exception as e:
        current_app.logger.error(f"Error creating iCal invite: {str(e)}")
        return None
