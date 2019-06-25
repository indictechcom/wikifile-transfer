from flask import Flask, render_template
from flask_mwoauth import MWOAuth
import requests_oauthlib
import requests
import os
import yaml

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

# Register blueprint to app
MWOAUTH = MWOAuth(base_url=BASE_URL, consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET)
app.register_blueprint(MWOAUTH.bp)


# /index route for return_to
@app.route('/index', methods=['GET'])
@app.route("/")
def index():

    data = {
        'username': MWOAUTH.get_current_user(True)
    }
    return render_template('index.html', data=data)


if __name__ == "__main__":
    app.run()
