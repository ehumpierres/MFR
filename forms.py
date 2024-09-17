from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DateField, SelectField
from wtforms.validators import DataRequired, Email

class LoginForm(FlaskForm):
    passphrase = PasswordField('Passphrase', validators=[DataRequired()])
    submit = SubmitField('Login')

class BookingForm(FlaskForm):
    unit_id = SelectField('Unit', coerce=int, validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    guest_name = StringField('Guest Name', validators=[DataRequired()])
    guest_email = StringField('Guest Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Submit Booking Request')

class NotificationEmailForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Add Email')
