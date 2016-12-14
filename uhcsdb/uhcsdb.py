# all the imports
import os
import re
import sys
import glob
import time
import uuid
import atexit
import subprocess
import pandas as pd
import seaborn as sns
from datetime import datetime
from contextlib import closing
from numpy import array, random
from os.path import abspath, dirname, join

from bokeh.client import pull_session
from bokeh.embed import autoload_server

from flask import (Flask, request, session, g, redirect, url_for,
                   abort, render_template, render_template_string, flash, current_app)

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, contains_eager

app = Flask(__name__)

sys.path.append( os.path.join( os.path.dirname(__file__), os.path.pardir ) )

# Flask app configuration
DATADIR = '/Users/brian/Research/projects/uhcs'
SQLALCHEMY_DATABASE_URI = 'microstructures.sqlite'
MICROGRAPH_PATH = 'static/micrographs'
UPLOAD_FOLDER = join('uhcsdb', MICROGRAPH_PATH)
EXTRACT_PATH = join('static', 'pdf_stage')
PDF_STAGE = join('uhcsdb', EXTRACT_PATH)
ALLOWED_EXTENSIONS = set(['pdf', 'png', 'jpg', 'jpeg', 'gif', 'tif'])

app.config.update(dict(
    DATADIR=DATADIR,
    DATABASE=SQLALCHEMY_DATABASE_URI,
    MICROGRAPH_PATH = MICROGRAPH_PATH,
    DEBUG=False,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))

app.config.from_envvar('UHCSDB_SETTINGS', silent=True)

_cwd = dirname(abspath(__file__))

print(app.config)

from . import features
from .visualization import scatterplot
from .models import Base, User, Collection, Sample, Micrograph

# from uhcsdb import features
# from uhcsdb.visualization import scatterplot
# from uhcsdb.models import Base, User, Collection, Sample, Micrograph


# features.build_search_tree(app.config['DATADIR'])

def connect_db(dbpath):
    print(dbpath)
    engine = create_engine('sqlite:///' + dbpath)
    Base.metadata.bind = engine
    dbSession = sessionmaker(bind=engine)
    db = dbSession()
    return db

def get_db():
    if not hasattr(g, '_database'):
        g._database = connect_db(app.config['DATABASE'])
    return g._database

@app.route('/all/')
def all_entries():
    db = get_db()
    all_entries = db.query(Micrograph).all()
    entries = [entry.info() for entry in all_entries]
    return render_template('all_entries.html', entries=entries)

@app.route('/favorites/')
def favorites():
    db = get_db()
    favs = [73, 357, 137, 156, 223, 290, 354, 359, 363, 372, 379, 394, 404, 422, 450, 452, 472, 696, 785, 830]
    entries = db.query(Micrograph).filter(Micrograph.id.in_(favs))
    entries = [entry.info() for entry in entries]
    return render_template('all_entries.html', entries=entries)

def paginate(results, page, PER_PAGE):
    start = (page-1)*PER_PAGE
    if start < 0 or start > len(results):
        return []
    end = min(start + PER_PAGE, len(results))

    page_data = {'prev_num': page - 1, 'next_num': page + 1,
                 'has_prev': True, 'has_next': True}
    if page_data['prev_num'] <= 0:
        page_data['has_prev'] = False
    if end >= len(results):
        page_data['has_next'] = False
  
    return results[start:end], page_data

PER_PAGE = 24
@app.route('/')
@app.route('/index')
@app.route('/entries/') #, defaults={'page': 1})
@app.route('/entries/<int:page>')
def entries(page=1):
    db = get_db()
    # all_entries = Micrograph.query.paginate(page, PER_PAGE, False)
    # all_entries = db.query(Micrograph).paginate(page, PER_PAGE, False)
    res = db.query(Micrograph).all()
    page_entries, page_data = paginate(res, page, PER_PAGE)
    page_entries = [entry.info() for entry in page_entries]
    count = len(page_entries)

    return render_template('show_entries.html', entries=page_entries, pg=page_data)

@app.route('/micrograph/<int:entry_id>')
def show_entry(entry_id):
    db = get_db()
    entry = db.query(Micrograph).filter(Micrograph.id == entry_id).first()
    author = entry.user
    return render_template('show_entry.html', entry=entry.info(), author=author.info())

@app.route('/visual_query/<int:entry_id>')
def visual_query(entry_id):
    db = get_db()
    query = db.query(Micrograph).filter(Micrograph.id == entry_id).first()
    author = query.user
    scores, nearest = features.query(entry_id)
    # write a single query and sort results on feature-space distance after
    # entries = db.query(Micrograph).filter(Micrograph.id.in_(nearest)).all()
    # write an individual query for each result -- won't scale
    entries = map(db.query(Micrograph).get, nearest)
    results = [entry.info() for entry in entries]
    results = zip(results, scores)
    return render_template('query_results.html', query=query.info(),
                           author=author.info(), results=results)


# this should work with flask and ssh-forwarding
bokeh_process = subprocess.Popen(
    ['bokeh-3.5', 'serve', '--allow-websocket-origin=localhost:5000',
     '--log-level=debug', 'visualize.py'], stdout=subprocess.PIPE)

@atexit.register
def kill_server():
    bokeh_process.kill()


@app.route('/visualize')
def bokeh_plot():
    session=pull_session(app_path='/visualize')
    bokeh_script=autoload_server(None,app_path="/visualize",session_id=session.id)
    # session=pull_session(app_path='/sliders')
    # bokeh_script=autoload_server(model=None, app_path='/sliders', session_id=session.id)
    # return render_template_string(app_html, bokeh_script=bokeh_script)
    return render_template('visualize.html', bokeh_script=bokeh_script)

if __name__ == '__main__':

    app.config.from_object('config')
    with app.app_context():
        # db.metadata.create_all(bind=db.engine)
        app.run(debug=False)
        # app.run(host='0.0.0.0', debug=False)
