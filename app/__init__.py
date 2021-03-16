# Import flask and template operators
from flask import Flask,request
import telegram
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage

import time
import io
import pandas as pd
import numpy as np
import os

# INIT NLP
# Fuzzy,spacy
import spacy
from spaczz.matcher import FuzzyMatcher
from spacy.matcher import PhraseMatcher
from transliterate import translit, get_available_language_codes
from pyngrok import ngrok

# nlp = spacy.load("ru_core_news_lg") # Large one = 2.5Gb
nlp = spacy.load("ru_core_news_sm") # Small one for testing

from app.processing.speech_to_text import google_stt
from app.processing.menu_matching import remove_stopwords,menu_preprocessing,text_preprocessing,find_matches,print_result
# Define the WSGI application object
app = Flask(__name__)
app.config.from_pyfile('config.py')
#ngrok
def init_webhooks(base_url):
    # Update inbound traffic via APIs to use the public-facing ngrok URL
    pass

if app.config.get("ENV") == "development" and app.config["USE_NGROK"]:
    port = 5033
    # Open a ngrok tunnel to the dev server
    public_url = ngrok.connect(port).public_url
    print(" * ngrok tunnel \"{}\" -> \"http://0.0.0.0:{}\"".format(public_url, port))
    # Update any base URLs or webhooks to use the public ngrok URL
    app.config["BASE_URL"] = public_url.replace('http','https')+'/'
    init_webhooks(public_url)


TOKEN = app.config.get('TOKEN')
URL = app.config.get('BASE_URL')
                    
bot = telegram.Bot(token=TOKEN)

s = bot.setWebhook('{URL}{HOOK}'.format(URL=URL, HOOK=TOKEN))
if s:
    print("webhook setup ok")
else:
    print("webhook setup failed")
 

@app.route('/test_comms')
def test():
    return 'test ok!'

@app.route('/{}'.format(TOKEN), methods=['POST'])
def application():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    print('\n',update,'\n')
    if update.message.voice is not None:
        chat_id = update.message.chat.id
        msg_id = update.message.message_id
        bot.sendMessage(chat_id=chat_id, text='Processing... Please wait '+"\U0001f600",reply_to_message_id=msg_id)
        first_name=update.message.chat.first_name
        last_name=update.message.chat.last_name
        username=update.message.chat.username
        ts=update.message.date    
        file_id=update.message.voice.file_id
        file = bot.getFile(file_id)
        print ("file_id: " + str(file_id))
        oggpath='./app/audio/{u}_{f}_{l}_{d}.ogg'.format(d=ts,f=first_name,
                                                                     l=last_name,
                                                                     u=username)
        # Save file
        file.download(oggpath)
        # Get stt result
        x,comm = google_stt(oggpath)
        bot.sendMessage(chat_id=chat_id, text=comm,reply_to_message_id=msg_id)

        #Text preproc

        x=remove_stopwords(x)
        dishlist,matcher = menu_preprocessing(nlp=nlp)
        x,dishlist = text_preprocessing(x=x,dishlist=dishlist)
        doc,fdf,comm = find_matches(x=x,dishlist=dishlist,nlp=nlp,matcher=matcher)
        bot.sendMessage(chat_id=chat_id, text=comm,reply_to_message_id=msg_id)
        comm=print_result(x=x,doc=doc,dishlist=dishlist,fdf=fdf)
        bot.sendMessage(chat_id=chat_id, text=comm,reply_to_message_id=msg_id)

        with open('./app/transcripts/{u}_{f}_{l}_{d}.txt'.format(d=ts,f=first_name,
                                                                     l=last_name,
                                                                     u=username), "w") as text_file:
            text_file.write(comm)
        return 'job done'
    else:
        return 'ok'
