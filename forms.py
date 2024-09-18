from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DateField, SelectField, IntegerField, TextAreaField, RadioField
from wtforms.validators import DataRequired, Email, NumberRange

class LoginForm(FlaskForm):
    passphrase = PasswordField('Passphrase', validators=[DataRequired()])
    submit = SubmitField('Login')

class BookingForm(FlaskForm):
    unit_id = SelectField('Unit', coerce=int, validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    guest_name = StringField('Guest Name', validators=[DataRequired()])
    guest_email = StringField('Guest Email', validators=[DataRequired(), Email()])
    num_guests = IntegerField('Number of Guests', validators=[DataRequired(), NumberRange(min=1, message="Must be at least 1")])
    catering_option = SelectField('Will you be directly booking your own caterer or bringing your own food?', 
                                  choices=[('Catering', 'Catering'), ('Bring own food', 'Bring own food')],
                                  validators=[DataRequired()])
    special_requests = TextAreaField('Special Requests')
    mobility_impaired = RadioField('Is anyone in your party mobility impaired?', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    event_manager_contact = StringField('Event manager/on-site emergency contact. Name, phone number, and email address:', validators=[DataRequired()])
    offsite_emergency_contact = StringField('Off-site emergency contact. Name, phone number, and email address:', validators=[DataRequired()])
    mitchell_sponsor = StringField('Mitchell family sponsor name or CGMF Program name', validators=[DataRequired()])
    exclusive_use = RadioField('Will you need exclusive use of requested facilities?', choices=[('Open to sharing', 'Open to sharing'), ('Exclusive use', 'Exclusive use')], validators=[DataRequired()])
    organization_status = RadioField('Organization status:', choices=[('501(c)(3)', '501(c)(3)'), ('CGMF Foundation event', 'CGMF Foundation event'), ('Personal use', 'Personal use')], validators=[DataRequired()])
    submit = SubmitField('Submit Booking Request')

class NotificationEmailForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Add Email')
