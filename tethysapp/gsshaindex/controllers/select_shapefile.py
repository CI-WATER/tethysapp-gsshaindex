from mapkit.RasterConverter import RasterConverter
from sqlalchemy import distinct

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import JsonResponse
import operator, random, pickle, pprint, zipfile, time, ConfigParser, os, json
from gsshapy.orm import *
from gsshapy.lib import db_tools as dbt
from django.http import JsonResponse
from tethys_apps.utilities import get_dataset_engine
from ..app import GSSHAIndex
import tethysapp.gsshaindex.lib as gi_lib
from ..lib import raster2pgsql_path, maps_api_key
from datetime import datetime, date
from mapkit.ColorRampGenerator import ColorRampEnum
import requests
import subprocess
from tethys_apps.sdk import get_spatial_dataset_engine

from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine

# Get app.ini
controller_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(os.path.abspath(os.path.dirname(controller_dir)), 'app.ini')
app_config = ConfigParser.RawConfigParser()
app_config.read(config_path)
shp2pgsql = app_config.get('postgis', 'shp2pgsql_path')

def shapefile_index(request, job_id, index_name, shapefile_id):
    """
    Controller for the selecting the shapefile to use to define the index map.
    """
    context = {}
    user = str(request.user)

    # Get the job from the database
    job_session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user, job_session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id
    project_file_id = job.new_model_id

    # Make sure there is a shapefile dataset
    shapefile_dataset = gi_lib.check_dataset("shapefiles", CKAN_engine)

    # Create a session
    gsshapy_session = gsshapy_sessionmaker()

    shapefile_list = []

    # Get list of shapefiles
    id = shapefile_dataset['result']['results'][0]['id']
    shapefile_search = CKAN_engine.search_datasets({'id':shapefile_dataset['result']['results'][0]['id']})
    shapefile_search_list =  shapefile_search['result']['results'][0]['resources']
    print "SHAPEFILES: ",shapefile_search_list
    if len(shapefile_search_list) == 0:
        shapefile_id = "NONE"
        editable_map = {'height': '600px',
                        'width': '100%',
                        'maps_api_key':maps_api_key,
                        'output_format': 'WKT'}

        context['job_id'] = job_id
        context['index_name'] = index_name
        context['shapefile_list'] = shapefile_list
        context['google_map'] = editable_map
        context['shapefile_id'] = shapefile_id

        return render(request, 'gsshaindex/select_shapefile.html', context)
    else:
        pass

    # Fill the array with information on the shapefiles
    for result in shapefile_search_list:
        if result.get('description')=='':
            description = "NONE"
        else:
            description = result.get('description')
        shapefile_list.append({"name":result.get('name'), "id":result.get('id'), "description":description, "url":result.get('url')})

    for shapefile in shapefile_list:
        if shapefile['id'] == shapefile_id:
            file_id = shapefile['id']
            file_name = shapefile['name']
            file_url = shapefile['url']
            file_description = shapefile['description']

    shapefile_list.sort(key=operator.itemgetter('name'))

    print "SHAPEFILE LIST: ", shapefile_list

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    indexMapDir = os.path.join(userDir, 'index_maps')

    # Use project id to link to original map table file
    project_file = gsshapy_session.query(ProjectFile).filter(ProjectFile.id == project_file_id).one()
    new_index = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()
    mapTables = new_index.mapTables

    # Get list of index files
    resource_list = json.loads(job.current_kmls)

    resource_names = []
    resource_url = []
    # Get array of names and urls
    for key in resource_list:
        resource_names.append(key)

    # Create kml file name and path
    current_time = time.strftime("%Y%m%dT%H%M%S")
    resource_name = new_index.name + "_" + str(user) + "_" + current_time
    kml_ext = resource_name + '.kml'
    clusterFile = os.path.join(indexMapDir, kml_ext)

    # See if kmls are present in the database
    file_present = False
    for key in resource_list:
        if key == index_name:
            file_present = True

    if file_present == False:
        # Generate color ramp
        new_index.getAsKmlClusters(session=gsshapy_session, path=clusterFile, colorRamp=ColorRampEnum.COLOR_RAMP_HUE, alpha=0.6)

        index_map_dataset = gi_lib.check_dataset("index-maps", CKAN_engine)
        resource, status = gi_lib.add_kml_CKAN(index_map_dataset, CKAN_engine, clusterFile, resource_name)

        for resource in result['resources']:
            if resource['name'] == resource_name:
                resource_list[new_index.name] = {'url':resource['url'], 'full_name':resource['name']}
                break

        job.current_kmls = json.dumps(resource_list)

    job_session.commit()
    job_session.close()

    overlay_result = show_overlay(None, job_id, index_name)

    print list(overlay_result['resource']['latlon_bbox'][:-1])

    if overlay_result['success'] == True:
        map_view = {'height': '600px',
                    'width': '100%',
                    'controls': ['ZoomSlider',
                                 {'ZoomToExtent': {'projection': 'EPSG:4326',
                                                   'extent': list(overlay_result['resource']['latlon_bbox'][:-1])}},
                    ],
                    'layers': [{'WMS': {'url': overlay_result['layer']['catalog']+'wms',
                                        'params': {'LAYERS': overlay_result['layer']['name']},
                                        'serverType': 'geoserver'}
                                },
                    ],
                    'view': {'projection': 'EPSG:4326',
                             'center': [-100, 40], 'zoom': 3.5,
                             'maxZoom': 18, 'minZoom': 3},
                    'base_map': 'OpenStreetMap'
  }

    else:

        map_view = {'height': '600px',
                            'width': '100%',
                            'maps_api_key':maps_api_key,
                            'output_format': 'WKT'}




    # Create an array of the projections for the selet_projection modal
    projection_query = '''SELECT srid, srtext FROM spatial_ref_sys'''

    result_prj_query = gsshapy_engine.execute(projection_query)

    projection_list = []

    for row in result_prj_query:
        srid = row['srid']
        short_desc = row['srtext'].split('"')[1]
        projection_list.append((short_desc, srid))

    select_input2 = {'display_text': 'Select Projection',
                'name': 'select_projection',
                'multiple': False,
                'options': projection_list}

    context['job_id'] = job_id
    context['index_name'] = index_name
    context['shapefile_list'] = shapefile_list
    context['file_name'] = file_name
    context['file_id'] = file_id
    context['file_description'] = file_description
    context['file_url'] = file_url
    context['shapefile_id'] = shapefile_id
    context['projection_list'] = projection_list
    context['select_input2'] = select_input2
    context['map_view'] = map_view


    return render(request, 'gsshaindex/select_shapefile.html', context)


def show_overlay(request, job_id, index_name):
    """
    This action is used to pass the kml data to the google map.
    It must return a JSON response with a Python dictionary that
    has the key 'kml_links'.
    """
    kml_links = []

    context = {}

    sde = get_spatial_dataset_engine(name='gsshaindex_geoserver', app_class=GSSHAIndex)
    result = sde.get_layer(layer_id='gsshaindex:jocelynn')
    resource = sde.get_resource(resource_id='gsshaindex:jocelynn', debug=True)

    if result['success'] == True:
        url = result['result']['wms']['kml']
        print url
        kml_links.append(url)

    if not request:
        return {'layer': result['result'], 'resource': resource['result'], 'success':result['success']}
    else:
        return JsonResponse({'kml_links': kml_links, 'success':result['success']})


def get_srid_from_wkt(request):
    url = request.GET['url']
    url = "http://prj2epsg.org/search.json?mode=wkt&terms=" + url
    r= requests.get(url)
    status = r.status_code
    if status == 200:
        result =  r.json()
        prj_code =  str(result['codes'][0]['code'])
        return JsonResponse({'prj_code':prj_code})
    else:
        return JsonResponse({'prj_code':'error'})


def shapefile_upload(request, job_id, index_name, shapefile_id):
    """
    Controller for uploading shapefiles.
    """
    context = {}
    user = str(request.user)

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))

    # Clear the workspace
    gi_lib.clear_folder(userDir)

    # Create a session
    gsshapy_session = gsshapy_sessionmaker()

    # Get the params
    params = request.POST
    print "PARAMS: ", params
    files = request.FILES

    input_files = []
    for file in files.getlist('shapefile_files'):
        print file
        input_files.append(file)

    name = params['shapefile_name']
    description = params['shapefile_description']
    srid = params['select_projection']
    # Reformat the name by removing bad characters
    bad_char = "',.<>()[]{}=+-/\"|:;\\^?!~`@#$%&* "
    for char in bad_char:
        new_name = name.replace(char,"_")
    zip_name = new_name + ".zip"
    zip_path = os.path.join(userDir, zip_name)

    shp_list = []

    for file in input_files:
        print file.name
        if file.name.endswith('.shp'):
            shp_list.append({file.name: file.file})
            new_name = file.name[:-4]
        elif file.name.endswith('.shx'):
            shp_list.append({file.name: file.file})
        elif file.name.endswith('.dbf'):
            shp_list.append({file.name: file.file})
        elif file.name.endswith('.prj'):
            shp_list.append({file.name: file.file})
        elif file.name.endswith('.sbx'):
            shp_list.append({file.name: file.file})
        elif file.name.endswith('.sbn'):
            shp_list.append({file.name: file.file})
        elif file.name.endswith('.xml'):
            shp_list.append({file.name: file.file})

    print new_name
    print shp_list

    temp_dir = os.path.join(userDir, new_name)
    os.mkdir(temp_dir)

    for thing in shp_list:
        file_path = os.path.join(temp_dir, thing.keys()[0])

        with open(file_path, 'w') as f:
            f.write(thing.values()[0].read())

    # Get list of files to be zipped
    writeFile_list = os.listdir(temp_dir)

    # Add files to the zip folder
    with zipfile.ZipFile(zip_path, "w") as shp_zip:
        for item in writeFile_list:
            abs_path = os.path.join(temp_dir, item)
            archive_path = os.path.join(new_name, item)
            shp_zip.write(abs_path, archive_path)

    # Add shapefile to database
    # Clear the workspace

    wkt_json = {'type': 'WKTGeometryCollection',
                            'geometries': ''}

    kml = ""


    ### Need to figure out what to do with this code
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if "." in file:
                new_name = str(user)+file[-4:]
                os.rename(os.path.join(root,file), os.path.join(root,new_name))
                if file.endswith(".dbf"):
                    dbf_path = os.path.join(root,new_name)

    #Try deleting that table name
    delete_statement = '''DROP TABLE '''+ user +''';'''
    try:
        gsshapy_engine.execute(delete_statement)
    except:
        pass

    # Write statement that will create table for shapefile in the database
    shapefile2pgsql = subprocess.Popen([shp2pgsql,
                                        '-s',
                                        srid,
                                        str(dbf_path)],
                                       stdout=subprocess.PIPE)

    print srid

    # Check to see if there are errors or if it worked
    sql, error = shapefile2pgsql.communicate()
    print "ERROR:", error

    if error == None:
        result = gsshapy_engine.execute(sql)


        # Start Spatial Dataset Engine
        dataset_engine = get_spatial_dataset_engine(name='gsshaindex_geoserver', app_class=GSSHAIndex)

        # Check to see if Spatial Dataset Engine Exists
        workspace = gi_lib.check_workspace(dataset_engine)

        feature_resource = dataset_engine.create_postgis_feature_resource(store_id = 'gsshaindex:shapefiles', table=user, host='172.17.42.1', port='5435', database='gsshaindex_gsshapy_db',user='tethys_db_manager',password='(|w@ter', debug=True)




    # Add the files to CKAN
    # CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)
    # shapefile_dataset = gi_lib.check_dataset("shapefiles", CKAN_engine)
    # result = gi_lib.append_shapefile_CKAN(shapefile_dataset, CKAN_engine, zip_path, name, description, srid)

    return redirect(reverse('gsshaindex:shapefile_index', kwargs={'job_id':job_id, 'index_name':index_name, 'shapefile_id':shapefile_id}))

