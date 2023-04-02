from flask import Flask
import time
import threading
from queue import Queue
import json
import os
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for
import requests as rq
import webbrowser


def read_json(filename: str) -> dict:
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)

    return data

def thread_webAPP(queue):

    authorization_base_url = 'https://connect.deezer.com/oauth/auth.php'
    token_url = 'https://connect.deezer.com/oauth/access_token.php'

    global config
    global token

    @app.route("/")
    def demo():
        """Step 1: User Authorization.

        Redirect the user/resource owner to the OAuth provider (i.e. Deezer)
        using an URL with a few key OAuth parameters.
        """
        deezer = OAuth2Session(config['app_id'], redirect_uri=config['redirect_uri'])
        authorization_url, state = deezer.authorization_url(authorization_base_url, perms='listening_history,offline_access', app_id=config['app_id'])

        # State is used to prevent CSRF, keep this for later.
        session['oauth_state'] = state
        return redirect(authorization_url)

    # Step 2: User authorization, this happens on the provider.
    @app.route("/callback", methods=["GET"])
    def callback():
        """ Step 3: Retrieving an access token.

        The user has been redirected back from the provider to your registered
        callback URL. With this redirection comes an authorization code included
        in the redirect URL. We will use that to obtain an access token.
        """
        deezer = OAuth2Session(config['app_id'], state=session['oauth_state'])
        tk = deezer.fetch_token(token_url,
                                secret=config['client_secret'],
                                app_id=config['app_id'],
                                authorization_response=request.url)

        # At this point you can fetch protected resources but lets save
        # the token and show how this is done from a persisted token
        # in /profile.
        queue.put(tk)
        finished.set()
        return "Application lancée, vous pouvez fermer cette page."

    # This allows us to use a plain HTTP callback
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = "1"
    app.secret_key = os.urandom(24)
    app.run()


def get_last_song_history(url_to_get) :
    all_history = []
    is_next = True

    try:
        while is_next:
            result = rq.get(url_to_get).json()

            data = result['data']
            all_history += data

            is_next = 'next' in result
            if is_next:
                url_to_get = result['next']
    except Exception as e:
        print('While loading history exception has occurred! {}'.format(e))
    return all_history[0]


### ========== MAIN ==========

webbrowser.open('http://127.0.0.1:5000/')

# Variable partagées entre les threads
finished = threading.Event()
queue = Queue()

# Reading config file
config = read_json('config.json')

# Checking config file and starting an application
if (not ('app_id' in config and 'client_secret' in config and 'redirect_uri' in config and 'user_id' in config)):
    raise ValueError('Wrong config! Config file must contain fields "app_id", "client_secret", "redirect_uri", "user_id"')

# application flask
app = Flask(__name__)

# lancer le thread avec le serveur web
t_webApp = threading.Thread(name='Web App', target=thread_webAPP, args=(queue,), daemon=True)
t_webApp.start()

# attendre que la permission soit accordée
while not finished.is_set():
    continue

token = queue.get()
url_to_get = 'https://api.deezer.com/user/{}/history&access_token={}'.format(config['user_id'], token['access_token'])
last_song_id_old = 0

# Vérifier si la musique a changé toutes les 0.5s (limité par deezer à 50 requêtes / 5s)
while True :
    time.sleep(0.5)
    last_song = get_last_song_history(url_to_get)
    if last_song_id_old != last_song['id'] :
        print("CHANGEMENT : " + last_song['title'] + "\n", flush=True)
        last_song_id_old = last_song['id']