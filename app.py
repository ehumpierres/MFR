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

# ... (rest of the code remains the same)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

logger.info("Flask application has stopped")
