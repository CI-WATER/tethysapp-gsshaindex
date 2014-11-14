import os, ConfigParser, zipfile
from collections import namedtuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gsshapy.lib import db_tools as dbt
from owslib.wps import WebProcessingService
from owslib.wps import monitorExecution
from mapkit.ColorRampGenerator import ColorRampEnum
from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine
from gsshapy.orm import ProjectFile

# Get app.ini
gsshaindex_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
config_path = os.path.join(gsshaindex_dir, 'app.ini')
app_config = ConfigParser.RawConfigParser()
app_config.read(config_path)

public_ckan = app_config.get('development', 'public_ckan')
user_api = app_config.get('development', 'user_api')
develop_state = app_config.get('development', 'develop')
raster2pgsql_path = app_config.get('postgis', 'raster2pgsql_path')
maps_api_key = app_config.get('api_key', 'maps_api_key')

def check_package(name, engine):
    '''
    Check to see if package name exists and if it doesn't, create it.
    This code is a variation of the code for Parley's Creek.
    '''
    context = {}

    result = engine.list_datasets()

    present = True
    if result['success']:
        package_list = result['result']
        if name not in package_list:
            engine.create_dataset(name)
            present = False
    else:
        print(result['error'])

    return present

def get_job(job_id, user_id):
    # Get the job and project file id from the database
    session = jobs_sessionmaker()
    success = True
    try:
        job = session.query(Jobs).\
                    filter(Jobs.user_id == user_id).\
                    filter(Jobs.id == job_id).one()
        return job, success
    else:
        success = False
        job = ""
        return job, success