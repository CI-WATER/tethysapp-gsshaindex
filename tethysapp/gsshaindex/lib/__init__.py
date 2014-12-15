import os, ConfigParser, zipfile, shutil, urllib2, StringIO
from collections import namedtuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gsshapy.lib import db_tools as dbt
from owslib.wps import WebProcessingService
from owslib.wps import monitorExecution
from mapkit.ColorRampGenerator import ColorRampEnum
from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine
from gsshapy.orm import ProjectFile
from datetime import datetime
from os import path

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

def get_new_job(job_id, user_id, session):
    # Get the job and project file id from the database
    success = True

    try:
        job = session.query(Jobs).\
                    filter(Jobs.user_id == user_id).\
                    filter(Jobs.original_id == job_id).\
                    filter(Jobs.status == "new").one()
        return job, success
    except:
        success = False
        job = ""
        return job, success

def get_pending_job(job_id, user_id, session):
    # Get the job and project file id from the database
    success = True

    try:
        job = session.query(Jobs).\
                    filter(Jobs.user_id == user_id).\
                    filter(Jobs.original_id == job_id).\
                    filter(Jobs.status == "pending").one()
        return job, success
    except:
        success = False
        job = ""
        return job, success

def clear_folder(workspace_folder_path):
    '''
    This function deletes a folder if it exists and then recreates it
    '''
    try:
        shutil.rmtree(workspace_folder_path)
    except:
        pass
    os.makedirs(workspace_folder_path)

def extract_mask(url, extractPath):
    '''
    This function finds the mask file from the zip file at the url and extracts it to a specified location
    url = location of the zipped GSSHA file
    extract_path = where the mask file should be extracted to
    '''

    # Find zip file at the url and find the mask file
    zip_file = urllib2.urlopen(url)
    zf = zipfile.ZipFile(StringIO.StringIO(zip_file.read()))
    try:
        for file in zf.namelist():
            if file.endswith('.msk'):
                mask_file=file
        # Extract the mask file
        zf.extract(mask_file, extractPath)

        return mask_file

    except:
        mask_file = "blank"
        return mask_file


def extract_projection(url, extract_path):
    '''
    This function finds the projection file from the zip file at the url and extracts it to a specified location
    url = location of the zipped GSSHA file
    extract_path = where the projection file should be extracted to
    '''

    # Find zip file at the url and find the mask file
    zip_file = urllib2.urlopen(url)
    zf = zipfile.ZipFile(StringIO.StringIO(zip_file.read()))
    try:
        for file in zf.namelist():
            if file.endswith('.pro'):
                projection_file=file

        # Extract the mask file
        zf.extract(projection_file, extract_path)

        return projection_file

    except:
        projection_file = "blank"
        return projection_file


def check_dataset(name, CKAN_engine):

    dataset = CKAN_engine.search_datasets({'name': name})

    if dataset['result']['count'] == 0:
        dataset = CKAN_engine.create_dataset(name)
    else:
        pass

    return dataset


def add_kml_CKAN(dataset, CKAN_engine, kml_file, kml_name):
    '''
    This function adds a kml file to CKAN
    kml_file = where the kml is located
    kml_name = the name of the kml file
    '''

    result = CKAN_engine.create_resource(dataset['result']['results'][0]['id'], name=kml_name, file=kml_file, format="kml")

    return result['result'], result['success']


def extract_zip_from_url(user_id, download_url, workspace):
    '''
    Extract zip directory to workspace in a directory
    with a unique name consisting of a timestamp and user id.

    user_id =  id of user performing operation
    download_url = url where zip archive can be downloaded
    workspace = location to extract file

    returns extract_path
    '''
    # Setup workspace
    time_stamp = datetime.isoformat(datetime.now()).split('.')[0]

    # Replace chars
    for char in (':', '-', 'T'):
        time_stamp = time_stamp.replace(char, '')

    normalized_id = user_id.replace('-', '')
    unique_dir = ''.join((time_stamp, normalized_id))

    # Extract
    extract_path = path.join(workspace, unique_dir)
    zip_file = urllib2.urlopen(download_url)
    zf = zipfile.ZipFile(StringIO.StringIO(zip_file.read()))
    zf.extractall(extract_path)

    return extract_path, unique_dir

def add_zip_GSSHA(dataset, GSSHA_file_path, CKAN_engine, GSSHA_file_name, new_description, date, user_id, *kwargs):

    result = CKAN_engine.create_resource(dataset['result']['results'][0]['id'], name=GSSHA_file_name, file=GSSHA_file_path, format="zip", model="GSSHA", description=new_description + "  Modified on "+ date +" by "+ user_id)

    return result['result'], result['success']

def flyGssha(link,resultsFile):
    '''
    This function submits the link to the zipped GSSHA file and gets the result
    '''
    wps = WebProcessingService('http://ci-water.byu.edu:9999/wps/WebProcessingService', verbose=False, skip_caps=True)

    processid = 'rungssha'
    inputs = [('url', link)]

    output = "outputfile"

    execution = wps.execute(processid, inputs, output)

    monitorExecution(execution)

    result = execution.getOutput(resultsFile)

    print "GSSHA has taken off!"


def extract_otl (url, extract_path):
    '''
    This function finds the otl file from the zip file at the url and extracts it to a specified location
    url = location of the zipped GSSHA file
    extract_path = where the mask file should be extracted to
    '''
    # Find zip file at the url and find the mask file
    zip_file = urllib2.urlopen(url)
    zf = zipfile.ZipFile(StringIO.StringIO(zip_file.read()))
    for file in zf.namelist():
#         if file.startswith("Results"):
            if file.endswith('.otl'):
                otl_file=file

    # Extract the mask file
    zf.extract(otl_file, extract_path)

    return otl_file