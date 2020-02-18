from flask_login import (current_user, login_required, login_user, logout_user)
import requests
from config import Config
from flask import request, redirect, Blueprint
import json

admin_login = Blueprint('admin_login', __name__)

from main import login_manager

users_email = ""

# TODO HttpError handling
# getting the provider configuration document
def get_google_provider_cfg():
	return requests.get(Config.LOGIN['GOOGLE_DISCOVERY_URL']).json()



@login_manager.user_loader
def user_loader(id):
	from models import Admin
	global users_email
	user = Admin.query.get(users_email)
	return user


@login_manager.user_loader
def load_user(id):
	global users_email
	from models import Admin
	from main import DB, app
	app.logger.info('LOAD USER, SHOW EMAIL: ' + str(id))
	user = DB.session.query(Admin).get(users_email)
	return user


def flask_user_authentication(users_email):
	from models import Admin
	from main import DB, app
	if users_email == Config.LOGIN['ADMIN_EMAIL_1'] or users_email == Config.LOGIN['ADMIN_EMAIL_2']:
		admin = DB.session.query(Admin).get(users_email)
		admin.authenticated = "true"
		admin.active = "true"
		DB.session.add(admin)
		DB.session.commit()
		login_user(admin, remember=True)
		return True
	else:
		app.logger.info('FLASK USER AUTHENTICATION FAILED')
		return False


@admin_login.route('/api/admin')
def admin_home():
	from main import app
	if current_user.is_authenticated:
		app.logger.info('current user: ' + str(current_user))
		return "<p>Du bist eingeloggt!</p>"
	else:
		return '<a class="button" href="/api/admin/login">Google Login</a>'


@admin_login.route('/api/admin/login')
def google_login():
	from main import app
	# auth-endpoint contains URL to instantiate the OAuth2 flow with Google from this client app
	google_provider_cfg = get_google_provider_cfg()
	authorization_endpoint = google_provider_cfg["authorization_endpoint"]
	# Use library to construct request for Google login + provide scopes that let retrieve user's profile from Google
	request_uri = Config.LOGIN['CLIENT'].prepare_request_uri(
		authorization_endpoint,
		redirect_uri=request.base_url.replace('http://', 'https://') + "/callback",
		scope=["openid", "email", "profile"])
	return redirect(request_uri)


@admin_login.route("/api/admin/login/callback")
def callback():
	global users_email
	from main import app
	# Get authorization code Google sent back to you
	code = request.args.get("code")
	google_provider_cfg = get_google_provider_cfg()
	token_endpoint = google_provider_cfg["token_endpoint"]
	token_url, headers, body = Config.LOGIN['CLIENT'].prepare_token_request(
		token_endpoint,
		authorization_response=request.url.replace('http://', 'https://'),
		redirect_url=request.base_url.replace('http://', 'https://'),
		code=code)
	app.logger.info('GOT TOKEN_URL from /callback ' + token_url)
	token_response = requests.post(
		token_url,
		headers=headers,
		data=body,
		auth=(Config.SECRETS['GOOGLE_CLIENT_ID'], Config.SECRETS['GOOGLE_CLIENT_SECRET']))

	Config.LOGIN['CLIENT'].parse_request_body_response(json.dumps(token_response.json()))
	# find and hit the URL from Google that gives you the user's profile information,
	userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
	uri, headers, body = Config.LOGIN['CLIENT'].add_token(userinfo_endpoint)
	userinfo_response = requests.get(uri, headers=headers, data=body)

	# verification
	# if userinfo_response.json().get("email_verified"):
	unique_id = userinfo_response.json()["sub"]
	users_email = userinfo_response.json()["email"]
	users_name = userinfo_response.json()["given_name"]
	app.logger.info('GOT USER DATA from /callback: ' + unique_id + ' ' + users_email + ' ' + users_name)

	if flask_user_authentication(users_email):
		return redirect('https://demo.datexis.com/admin')
	else:
		return "Sorry. You're Email is not valid.", 400


@admin_login.route("/test")
@login_required
def get_user_data():
	from main import app
	return '<a class="button" href="/api/admin/logout">Logout</a>'


@admin_login.route("/logout")
@login_required
def logout():
	from main import DB, app
	app.logger.info('logout')
	admin = current_user
	admin.authenticated = False
	DB.session.add(admin)
	DB.session.commit()
	logout_user()
	return redirect('https://demo.datexis.com/api/admin')
