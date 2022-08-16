#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, session, abort, \
    redirect, url_for
from flask_mwoauth import MWOAuth
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms_components import SelectField
import requests_oauthlib
import requests
import os
import yaml
import re
import datetime
import urllib.parse

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load configuration from YAML file
__dir__ = os.path.dirname(__file__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

# Get variables
BASE_URL = app.config['OAUTH_MWURI']
API_ENDPOINT = BASE_URL + '/api.php'
CONSUMER_KEY = app.config['CONSUMER_KEY']
CONSUMER_SECRET = app.config['CONSUMER_SECRET']

# Create Database and Migration Object
db = SQLAlchemy( app )
migrate = Migrate(app, db)


# ORM to store the User Data
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255))
    pref_project = db.Column(db.String(15))
    pref_language = db.Column(db.String(4))
    user_language = db.Column(db.String(4), default='en') # will use in future

    def __repr__(self):
        return '<User %r>' % self.username


class SelectFields(FlaskForm):
    projects = [ ('wikipedia','Wikipedia'), ('wikisource','Wikisource'),
                 ('wikibooks', 'Wikibooks'), ('wikinews','Wikinews'),
                 ('wikiquote', 'Wikiquote'),('wiktionary', 'Wiktionary'),
                 ('wikiversity', 'Wikiversity')
    ]
    lang = [ ('as','Assamese'),('awa','Awadhi'),('bn','Bangla'), ('bh','Bhojpuri'),
             ('bpy','Bishnupriya Manipuri'), ('gu','Gujarati'),
             ('en','English'), ('hi','Hindi'),('kn','Kannada'), ('ks','Kashmiri'),
             ('gom','Konkani'),('mai','Maithili'),('ml','Malayalam'),('mr','Marathi'),('mei','Meitei'),
             ('ne','Nepali'),('new','Newari'),('or','Oriya'),('pi','Pali'),
             ('pa','Punjabi'),('sa','Sanskrit'),('sat','Santali'),('sd','Sindhi'),
             ('ta','Tamil'),('te','Telugu'),('tcy','Tulu'),('ur','Urdu')
    ]

    trproject = SelectField(
        'Select Project',
        choices = projects,
        render_kw = { "class":"form-control" }
    )
    trlang = SelectField(
        'Select Language',
        choices = lang,
        render_kw = { "class":"form-control" }
    )

# Register blueprint to app
MW_OAUTH = MWOAuth(base_url=BASE_URL, consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET)
app.register_blueprint(MW_OAUTH.bp)


# /index route for return_to
@app.route('/index', methods=['GET'])
@app.route("/")
def index():
    if (logged() is not None) and ( db_user() is not None):
        user = db_user()
        fields = SelectFields(trlang=user.pref_language, trproject=user.pref_project)
    else:
        fields = SelectFields()

    return render_template('index.html', field=fields)


@app.route('/upload', methods = ['POST'])
def upload():
    if request.method == 'POST':

        # Getting Source Details
        src_url = urllib.parse.unquote( request.form['srcUrl'] )
        match = re.findall("(\w+)\.(\w+)\.org/wiki/", src_url)

        src_project = match[0][1]
        src_lang = match[0][0]
        src_filename = src_url.split('/')[-1]
        src_fileext = src_filename.split('.')[-1]

        # Downloading the source file and getting saved file name
        downloaded_filename = download_image(src_project, src_lang, src_filename)

        # Getting Target Details
        tr_project = request.form['trproject']
        tr_lang = request.form['trlang']
        tr_filename = request.form['tr-filename']
        tr_endpoint = "https://" + tr_lang + "." + tr_project + ".org/w/api.php"

        # Authenticate Session
        ses = authenticated_session()

        # Variable to set error state
        error = None

        # Check whether we have enough data or not
        if None not in (downloaded_filename, tr_filename, src_fileext, ses):
            # API Parameter to get CSRF Token
            csrf_param = {
                "action": "query",
                "meta": "tokens",
                "format": "json"
            }

            response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
            csrf_token = response.json()["query"]["tokens"]["csrftoken"]

            # API Parameter to upload the file
            upload_param = {
                "action": "upload",
                "filename": tr_filename + "." + src_fileext,
                "format": "json",
                "token": csrf_token,
                "ignorewarnings": 1
            }

            # Read the file for POST request
            file = {
                'file': open('temp_images/' + downloaded_filename, 'rb')
            }

            response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses).json()

            # Try block to get Link and URL
            try:
                wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
                file_link = response["upload"]["imageinfo"]["url"]
            except KeyError:
                error = True
                return render_template('upload.html', error=error)

            return render_template('upload.html', wikifileURL=wikifile_url, fileLink=file_link, error=error)

        # If we didn't have enough data, just throw an error
        error = True
        return render_template('upload.html', error=error)
    else:
        abort(400)


def download_image(src_project, src_lang, src_filename):
    src_endpoint = "https://"+ src_lang + "." + src_project + ".org/w/api.php"

    param = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": src_filename,
        "iiprop": "url",
        "iilocalonly": 1
    }

    page = requests.get(url=src_endpoint, params=param).json()['query']['pages']

    try:
        image_url = list (page.values()) [0]["imageinfo"][0]["url"]
    except KeyError:
        raise ValueError('Can\'t find the image URL :(')

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_')
    get_filename = get_filename.replace(' ', '_')

    # Download the Image File
    r = requests.get(image_url, allow_redirects=True)
    filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
    open("temp_images/" + filename, 'wb').write(r.content)

    return filename


@app.route('/preference', methods = ['GET', 'POST'])
def preference():

    if request.method == 'GET':
        user = db_user()
        if db_user() is not None:
            fields = SelectFields(trlang=user.pref_language, trproject=user.pref_project)
        else:
            fields = SelectFields()

        return render_template('preference.html', field=fields)

    elif request.method == 'POST':
        # Get the data
        pre_project = request.form['trproject']
        pre_lang = request.form['trlang']

        # Add into database
        cur_username = MW_OAUTH.get_current_user(True)
        user = User.query.filter_by(username=cur_username).first()
        if user is None:
            user = User(username=cur_username,pref_language=pre_lang, pref_project=pre_project)
            db.session.add(user)
        else:
            user.pref_language = pre_lang
            user.pref_project = pre_project

        db.session.commit()

        return redirect(url_for('index'))

    else:
        abort(400)


def authenticated_session():
    if 'mwoauth_access_token' in session:
        auth = requests_oauthlib.OAuth1(
            client_key=CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=session['mwoauth_access_token']['key'],
            resource_owner_secret=session['mwoauth_access_token']['secret']
        )
        return auth

    return None


def db_user():
    if logged():
        user = User.query.filter_by(username=MW_OAUTH.get_current_user(True)).first()
        return user
    else:
        return None


def logged():
    if MW_OAUTH.get_current_user(True) is not None:
        return MW_OAUTH.get_current_user(True)
    else:
        return None

@app.context_processor
def inject_base_variables():
    return {
        "logged": logged(),
        "username": MW_OAUTH.get_current_user(True)
    }

if __name__ == "__main__":
    app.run()
