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

def shapefile_index(request, job_id, index_name):
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

    # Find the contents of GeoServer for the user and display them
    dataset_engine = get_spatial_dataset_engine(name='gsshaindex_geoserver', app_class=GSSHAIndex)
    overlay_result = gi_lib.get_layer_and_resource(dataset_engine, user)
    pprint.pprint(overlay_result)

    if overlay_result['success'] == True:
        url = overlay_result['layer']['wms']['kml']
        file_name = overlay_result['resource']['name']
        coord_list = list(overlay_result['resource']['latlon_bbox'][:-1])
        avg_x = int(round((float(coord_list[0])+float(coord_list[1]))/2))
        avg_y = int(round((float(coord_list[2])+float(coord_list[3]))/2))

        map_view = {'height': '600px',
                    'width': '100%',
                    'controls': ['ZoomSlider',
                                 # {'ZoomToExtent': {'projection': projection,
                                 #                   'extent': ordered_list}},
                    ],
                    'layers': [{'WMS': {'url': url,
                                        'params': {'LAYERS': overlay_result['layer']['name'],},
                                        'serverType': 'geoserver'}
                                },
                    ],
                    'view': {'projection': 'EPSG:4326',
                             'center': [avg_x, avg_y], 'zoom': 6.5,
                             'maxZoom': 18, 'minZoom': 3},
                    'base_map': 'OpenStreetMap'
  }
        print map_view
        pprint.pprint(map_view)

    else:
        file_name =''
        map_view = {'height': '400px',
                    'width': '100%',
                    'controls': ['ZoomSlider',
                                 'Rotate',
                                 'FullScreen',
                                 'ScaleLine',
                                 {'ZoomToExtent': {'projection': 'EPSG:4326',
                                                   'extent': [-135, 22, -55, 54]}},
                                 {'MousePosition': {'projection': 'EPSG:4326'}},
                    ],

                    'view': {'projection': 'EPSG:4326',
                             'center': [-100, 40], 'zoom': 3.5,
                             'maxZoom': 18, 'minZoom': 3},
                    'base_map': 'OpenStreetMap'
  }

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
    context['file_name'] = file_name
    # context['file_description'] = file_description
    context['projection_list'] = projection_list
    context['select_input2'] = select_input2
    context['map_view'] = map_view


    return render(request, 'gsshaindex/select_shapefile.html', context)


def show_overlay(request, job_id, index_name, user, shapefile_name):
    """
    This action is used to pass the kml data to the google map.
    It must return a JSON response with a Python dictionary that
    has the key 'kml_links'.
    """
    kml_links = []
    context = {}

    print "SHAPEFILE NAME FROM SHOW OVERLAY ", shapefile_name

    dataset_engine = get_spatial_dataset_engine(name='gsshaindex_geoserver', app_class=GSSHAIndex)
    result = dataset_engine.get_layer(layer_id='gsshaindex:'+ shapefile_name, debug=True)
    resource = dataset_engine.list_resources(store=user, debug=True)

    if result['success'] == True:
        url = result['result']['wms']['kml']
        kml_links.append(url)

    if not request:
        if result['success'] == True:
            return {'layer': result['result'], 'resource': resource['result'], 'success':result['success']}
        else:
            return {'success':False}
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


def shapefile_upload(request, job_id, index_name):
    """
    Controller for uploading shapefiles.
    """
    context = {}
    user = str(request.user)
    user.lower()

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
    files = request.FILES.getlist('shapefile_files')

    shp_name = ''
    for file in files:
        if file.name.endswith('.shp'):
            shp_name = file.name[:-4]

    name = params['shapefile_name']
    description = params['shapefile_description']
    srid = params['select_projection']
    # Reformat the name by removing bad characters
    bad_char = "',.<>()[]{}=+-/\"|:;\\^?!~`@#$%&* "
    for char in bad_char:
        new_name = name.replace(char,"_")


    # Start Spatial Dataset Engine
    dataset_engine = get_spatial_dataset_engine(name='gsshaindex_geoserver', app_class=GSSHAIndex)

    # Check to see if Spatial Dataset Engine Exists
    workspace = gi_lib.check_workspace(dataset_engine)

    # Clear the store and create a new feature resource
    store = gi_lib.clear_store(dataset_engine, user)
    print "FEATURE RESOURCE"
    feature_resource = dataset_engine.create_shapefile_resource(store_id='gsshaindex:'+user, shapefile_upload=files, overwrite=False, debug=True)


    return redirect(reverse('gsshaindex:shapefile_index', kwargs={'job_id':job_id, 'index_name':index_name}))

