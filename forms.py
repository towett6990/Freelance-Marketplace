"""
Form definitions for Freelance Marketplace
All FlaskForm classes
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, PasswordField, SubmitField,
    TextAreaField, DecimalField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Regexp


class RegistrationForm(FlaskForm):
    username = StringField("Display name", validators=[Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters"),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]',
               message="Password must contain: uppercase, lowercase, number, and special character (@$!%*?&)")
    ])
    confirm_password = PasswordField("Confirm", validators=[DataRequired(), EqualTo("password")])
    role = SelectField("Role", choices=[("buyer","Buyer"),("seller","Seller")], validators=[DataRequired()])
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Login")


class ServiceForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=150)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10)])
    price = DecimalField("Price", validators=[DataRequired(), NumberRange(min=0)], places=2)
    submit = SubmitField("Post Service")


class ProfileForm(FlaskForm):
    username = StringField("Display name", validators=[Length(max=120)])
    bio = TextAreaField("Bio", validators=[Length(max=1000)])
    submit = SubmitField("Save")
