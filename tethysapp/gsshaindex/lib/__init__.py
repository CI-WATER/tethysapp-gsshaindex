import os, ConfigParser, zipfile, shutil, urllib2, StringIO
from collections import namedtuple
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gsshapy.orm import *
from gsshapy.lib import db_tools as dbt
from owslib.wps import WebProcessingService
from owslib.wps import monitorExecution
from mapkit.ColorRampGenerator import ColorRampEnum
from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine
from gsshapy.orm import ProjectFile
from datetime import datetime
from os import path
from multiprocessing import Process, Queue
from tethys_apps.sdk import get_spatial_dataset_engine
import glob

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

# def create_duplicate_job(job_id, user_id, session):
#     # Get the job and project file id from the database and duplicate
#
#     original_job = session.query(Jobs).\
#                 filter(Jobs.user_id == user_id).\
#                 filter(Jobs.original_id == job_id).\
#                 filter(Jobs.status == "new").one()
#
#     new_job = Jobs(name=original_job.original_name, user_id=user_id, original_description=original_job.original_description, original_id=job_id, original_url=original_job.original_url, original_certification=original_job.original_certification)
#
#     return new_job

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

def add_zip_GSSHA(dataset, GSSHA_file_path, CKAN_engine, GSSHA_file_name, new_description, date, user_id, certification=''):

    result = CKAN_engine.create_resource(dataset['result']['results'][0]['id'], name=GSSHA_file_name, file=GSSHA_file_path, format="zip", model="GSSHA", certification=certification, description=new_description + "  Modified on "+ date +" by "+ user_id)

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
    extract_path = where the otl file should be extracted to
    '''
    # Find zip file at the url and find the otl file
    zip_file = urllib2.urlopen(url)
    zf = zipfile.ZipFile(StringIO.StringIO(zip_file.read()))
    for file in zf.namelist():
        if file.endswith('.otl'):
            otl_file=file

    # Extract the otl file
    zf.extract(otl_file, extract_path)

    otl_fileDir = os.path.join(extract_path, otl_file)

    return otl_fileDir

def find_otl (otl_path):
    '''
    otl_path = where the otl file is
    '''
    # Find the otl file
    otl_file = glob.glob(otl_path+"/*.otl")
    file_path = otl_file[0]
    return file_path

def get_otl_values(file_path, value_array):
    '''
    This takes an otl file location and an empty array and fills the array with the values from the otl file
    '''
    # newFileDir = os.path.join(file_path, otl_file)
    with open(file_path, 'r') as f:
        values = [row.strip().split('   ') for row in f]
    for thing in values:
        formatted_value = []
        for item in thing:
            item = float(item)
            formatted_value.append(item)
        value_array.append(formatted_value)

    return value_array

def add_depth_map_CKAN(dataset, CKAN_engine, depth_file, depth_name):
    '''
    This function adds a kml file to CKAN
    kml_file = where the kml is located
    kml_name = the name of the kml file
    '''

    result = CKAN_engine.create_resource(dataset['result']['results'][0]['id'], name=depth_name, file=depth_file, format="kmz")

    return result['result'], result['success']

def append_shapefile_CKAN(dataset, CKAN_engine, zip_file_path, name, description, srid):
    '''
    This function adds a kml file to CKAN
    kml_file = where the kml is located
    kml_name = the name of the kml file
    '''

    result = CKAN_engine.create_resource(dataset['result']['results'][0]['id'], name=name, file=zip_file_path, format="zip", description=description, srid=srid)

    return result['result'], result['success']

def prepare_time_depth_map(user, result_url, job, depthMapDir, CKAN_engine):

    print "Preparing time depth map"

    # Clear the results folder
    clear_folder(depthMapDir)

    # Create gsshapy_session
    gsshapy_session = gsshapy_sessionmaker()

    # Get project file id
    project_file_id = job.new_model_id

    # Extract the GSSHA file
    extract_path, unique_dir = extract_zip_from_url(user, result_url, depthMapDir)

    # Find the project file
    for root, dirs, files in os.walk(depthMapDir):
        for file in files:
            if file.endswith(".prj"):
                project_name = file
                project_path = os.path.join(root, file)
                read_dir = os.path.dirname(project_path)
                depth_file = project_path[:-3]+"kmz"
                resource_name = project_name[:-4]+" time step depth"

    # Create an empty Project File Object
    project_file = ProjectFile()

    # Invoke the read command on the Project File Object to get the output files in the database
    project_file.readOutput(directory=read_dir,
                      projectFileName=project_name,
                      session=gsshapy_session,
                      spatial=True)
    try:
        # Create a kml using the depth map
        depth_map_raster =  gsshapy_session.query(WMSDatasetFile).filter(WMSDatasetFile.projectFileID == project_file.id).filter(WMSDatasetFile.fileExtension == "dep").one()
        depth_map_raster.getAsKmlGridAnimation(session=gsshapy_session, projectFile=project_file, path=depth_file,colorRamp = ColorRampEnum.COLOR_RAMP_HUE, alpha=0.5)

        depth_raster = check_dataset("depth-maps", CKAN_engine)
        result, status = add_depth_map_CKAN(depth_raster, CKAN_engine, depth_file, resource_name)
    except:
        result={'url':""}

    return result

def prepare_max_depth_map(user, result_url, job, depthMapDir, CKAN_engine):

    print "Preparing max depth map"

    # Clear the results folder
    clear_folder(depthMapDir)

    # Create gsshapy_session
    gsshapy_session = gsshapy_sessionmaker()

    # Get project file id
    project_file_id = job.new_model_id

    # Extract the GSSHA file
    extract_path, unique_dir = extract_zip_from_url(user, result_url, depthMapDir)

    # Find the project file
    for root, dirs, files in os.walk(depthMapDir):
        for file in files:
            if file.endswith(".prj"):
                project_name = file
                project_path = os.path.join(root, file)
                read_dir = os.path.dirname(project_path)
                depth_file = project_path[:-3]+"kmz"
                resource_name = project_name[:-4]+" max depth"

    # Create an empty Project File Object
    project_file = ProjectFile()

    # Invoke the read command on the Project File Object to get the output files in the database
    project_file.readOutput(directory=read_dir,
                      projectFileName=project_name,
                      session=gsshapy_session,
                      spatial=True)
    print project_file.id
    # Create a kml using the depth map
    # try:
    depth_map_raster =  gsshapy_session.query(WMSDatasetFile).filter(WMSDatasetFile.projectFileID == project_file.id).filter(WMSDatasetFile.fileExtension == "gfl").one()
    depth_map_raster.getAsKmlGridAnimation(session=gsshapy_session, projectFile=project_file, path=depth_file,colorRamp = ColorRampEnum.COLOR_RAMP_HUE, alpha=0.5)

    depth_raster = check_dataset("depth-maps", CKAN_engine)
    result, status = add_depth_map_CKAN(depth_raster, CKAN_engine, depth_file, resource_name)
    # except:
    #     result={'url':""}

    return result

def prepare_both_max_depth_map(user, new_result_url, original_result_url, job, newDepthDir, originalDepthDir, CKAN_engine):

    # Clear the results folder
    clear_folder(depthMapDir)

    # Create gsshapy_session
    gsshapy_session = gsshapy_sessionmaker()

    # Get project file id
    project_file_id = job.new_model_id

    # Extract the GSSHA file
    extract_path, unique_dir = extract_zip_from_url(user, result_url, depthMapDir)

    # Find the project file
    for root, dirs, files in os.walk(newDepthMapDir):
        for file in files:
            if file.endswith(".prj"):
                new_project_name = file
                new_project_path = os.path.join(root, file)
                new_read_dir = os.path.dirname(project_path)
                new_depth_file = project_path[:-3]+"kmz"

    # Find the project file
    for root, dirs, files in os.walk(originalDepthMapDir):
        for file in files:
            if file.endswith(".prj"):
                original_project_name = file
                original_project_path = os.path.join(root, file)
                original_read_dir = os.path.dirname(project_path)
                original_depth_file = project_path[:-3]+"kmz"

    # Create an empty Project File Object
    new_project_file = ProjectFile()
    original_project_file = ProjectFile()

    # Invoke the read command on the Project File Object to get the output files in the database
    new_project_file.readOutput(directory=new_read_dir,
                      projectFileName=new_project_name,
                      session=gsshapy_session,
                      spatial=True)

    original_project_file.readOutput(directory=original_read_dir,
                      projectFileName=original_project_name,
                      session=gsshapy_session,
                      spatial=True)

    # Create a kml using the depth map
    try:
        new_depth_map_raster =  gsshapy_session.query(WMSDatasetFile).filter(WMSDatasetFile.projectFileID == new_project_file.id).filter(WMSDatasetFile.fileExtension == "gfl").one()
        original_depth_map_raster =  gsshapy_session.query(WMSDatasetFile).filter(WMSDatasetFile.projectFileID == original_project_file.id).filter(WMSDatasetFile.fileExtension == "gfl").one()

        # depth_map_raster.getAsKmlGridAnimation(session=gsshapy_session, projectFile=project_file, path=depth_file,colorRamp = ColorRampEnum.COLOR_RAMP_HUE, alpha=0.5)

        # depth_raster = check_dataset("depth-maps", CKAN_engine)
        # result, status = add_depth_map_CKAN(depth_raster, CKAN_engine, depth_file, resource_name)
    except:
        result={'url':""}

    return result


def timeout(func, args=(), kwargs={}, timeout=1, default=None, result_can_be_pickled=True):
	"""
	a wrapper function that allows a timeout to be set for the given function (func)

	arg: func - a function to be executed with timeout
	arg: args - a tuple of arguments for func
	arg: kwargs - a dictionary of key-word arguments for func
	arg: timeout - the amount of time in second to wait for func before timeing out
	arg: default - the value to return if func timesout before completing
	arg: result_can_be_pickled - boolean stating weather the result of func is picklable (default=True)

	return: the return value from func or default
	"""
	if result_can_be_pickled:
		from multiprocessing import Process, Manager
		import thread
		class TimedProcess(Process):
			def __init__(self, l):
				super(TimedProcess, self).__init__()
				self.list = l

			def run(self):
				try:
					result = func(*args, **kwargs)
					self.list.append(result)
				except Exception as e:
					self.list.append(e)

		mng = Manager()
		l = mng.list()
		p = TimedProcess(l)
		p.start()
		p.join(timeout)
		if p.is_alive():
			p.terminate()
			return default
		else:
			return l[0]
	else:
		import time #, KeyboardInterrupt


		try:
			import thread as _thread
			import threading as _threading
		except ImportError:
			import dummy_thread as _thread
			import dummy_threading as _threading
			pass

		start = time.time()

		def interrupt():
			print 'interrupting ', time.time() - start
			_thread.interrupt_main()

		result = default
		try:
			t = _threading.Timer(timeout, interrupt)
			t.start()
			start = time.time()
			result = func(*args, **kwargs)
			t.cancel()
		except KeyboardInterrupt as e:
			pass
		return result


def set_timeout(timeout_wait, default=None, result_can_be_pickled=True):
	"""
	a decorator for the timeout function above

	USAGE:  @set_timeout(1, None)
			def func():
				. . .

	arg: timeout_wait - the amount of time in second to wait for function to complete
	arg: default - the return value of the function if the function times out before completing
	"""
	def decorator(function):
		def function_wrapper(*args, **kwargs):
			return timeout(function, args=args, kwargs=kwargs,
				timeout=timeout_wait, default=default,
				result_can_be_pickled=result_can_be_pickled)
		return function_wrapper
	return decorator

def draw_update_index(statement, raster_id):
    print "Function entered"
    result = gsshapy_engine.execute(statement)
    for row in result:
        second_different_statement = "UPDATE idx_index_maps SET raster = '{0}' WHERE id = {1};".format(row[0], raster_id)
        result2 = gsshapy_engine.execute(second_different_statement)
        result = True
    print "Function exited"
    return result

def check_workspace(dataset_engine):

    workspace = dataset_engine.get_workspace('gsshaindex')

    if workspace['success'] == False:
        workspace = dataset_engine.create_workspace('gsshaindex','http://host/apps/gsshaindex')
        print "Workspace created"
    else:
        pass
        print "Workspace already exists"

    return workspace

def delete_layer(dataset_engine, user):

    result = dataset_engine.get_layer(layer_id='gsshaindex:' + user)
    if result['success'] == True:
        layer = dataset_engine.delete_layer(layer_id='gsshaindex:' + user)
        print "Layer deleted"
    else:
        pass
    return result

def delete_resource(dataset_engine, user):

    result = dataset_engine.get_resource(resource_id='gsshaindex:' + user)
    if result['success'] == True:
        resource = dataset_engine.delete_resource(resource_id='gsshaindex:' + user)
        print "Resource deleted"
    else:
        pass
    return result

def clear_store(dataset_engine, user):

    try:
        # Get list of resources in the user's store
        resource_list = dataset_engine.list_resources(store=user)

        # If there are resources in the list
        if resource_list['success'] == True:
            # Get list of layers
            for resource in resource_list['result']:
                layer = dataset_engine.delete_layer(layer_id='gsshaindex:' + resource)
                resource = dataset_engine.delete_resource(resource_id='gsshaindex:' + resource)

        store = dataset_engine.delete_store(store_id='gsshaindex:'+user)
    except:
        store = {'success':True}

    return store

def get_layer_and_resource(dataset_engine, user, shapefile_name):

    # Get list of resources in the user's store
    try:
        resource_list = dataset_engine.list_resources(store=user+'-'+shapefile_name, debug=True)
    except:
        return {'success':False}

    # If there are resources in the list
    if resource_list['success'] == True and len(resource_list['result'])>0:
        # Get list of layers
        for resource in resource_list['result']:
            layer = dataset_engine.get_layer(layer_id='gsshaindex:' + resource)
            resource = dataset_engine.get_resource(resource_id='gsshaindex:' + resource)
            if layer['success']==True and resource['success'] == True:
                return {'layer':layer['result'], 'resource':resource['result'], 'success':True}
            else:
                return {'success':False}
    else:
        return {'success':False}