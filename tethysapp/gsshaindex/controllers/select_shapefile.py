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

from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine

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

    editable_map = {'height': '600px',
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

    select_input2 = {'display_text': 'Select2',
                'name': 'Select Projection',
                'multiple': False,
                'options': projection_list}

    context['job_id'] = job_id
    context['index_name'] = index_name
    context['shapefile_list'] = shapefile_list
    context['google_map'] = editable_map
    context['file_name'] = file_name
    context['file_id'] = file_id
    context['file_description'] = file_description
    context['file_url'] = file_url
    context['shapefile_id'] = shapefile_id
    context['projection_list'] = projection_list
    context['select_input2'] = select_input2


    return render(request, 'gsshaindex/select_shapefile.html', context)


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
    srid = params['projection-number']
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
            new_name = file[:-4]
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

    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)
    shapefile_dataset = gi_lib.check_dataset("shapefiles", CKAN_engine)

    result = gi_lib.append_shapefile_CKAN(shapefile_dataset, CKAN_engine, zip_path, name, description)
    print zip_path
    print name
    print description

    return redirect(reverse('gsshaindex:shapefile_index', kwargs={'job_id':job_id, 'index_name':index_name, 'shapefile_id':shapefile_id}))


def show_overlay(request, job_id, index_name, shapefile_id):
    """
    This action is used to pass the kml data to the google map.
    It must return a JSON response with a Python dictionary that
    has the key 'kml_links'.
    """
    kml_links = []

    context = {}
    user = str(request.user)

    # Get the job from the database
    job_session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user, job_session)

    # print job.kml_url
    #
    # if job.kml_url != None:
    #     print "A MASK MAP EXISTS"
    #     kml_links.append(job.kml_url)
    #     return JsonResponse({'kml_links': kml_links})
    # else:
    #     # Check that there's a package to store kmls
    #     CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)
    #     present = gi_lib.check_package('kmls', CKAN_engine)
    #
    #     # Specify the workspace
    #     controllerDir = os.path.abspath(os.path.dirname(__file__))
    #     gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    #     publicDir = os.path.join(gsshaindexDir,'public')
    #     userDir = os.path.join(publicDir, str(user))
    #
    #     # Clear the workspace
    #     gi_lib.clear_folder(userDir)
    #
    #     url = job.original_url
    #     maskMapDir = os.path.join(userDir, 'mask_maps')
    #     extractPath = os.path.join(maskMapDir, file_id)
    #     mask_file = gi_lib.extract_mask(url, extractPath)
    #     if mask_file == "blank":
    #         print "Mask File Didn't Exist"
    #         job.kml_url = ''
    #         session.commit()
    #         return JsonResponse({'kml_links': ''})
    #     else:
    #         projection_file = gi_lib.extract_projection(url,extractPath)
    #
    #         # Set up kml file name and save location
    #         name = job.original_name
    #         norm_name = name.replace(" ","")
    #         current_time = time.strftime("%Y%m%dT%H%M%S")
    #         kml_name = norm_name + "_" + user + "_" + current_time
    #         kml_ext = kml_name + ".kml"
    #         kml_file = os.path.join(extractPath, kml_ext)
    #
    #         colors = [(237,9,222),(92,245,61),(61,184,245),(171,61,245),(250,245,105),(245,151,44),(240,37,14),(88,5,232),(5,232,190),(11,26,227)]
    #         color = [random.choice(colors)]
    #
    #         # Extract mask map and create kml
    #         gsshapy_session = gsshapy_sessionmaker()
    #         if projection_file != "blank":
    #             srid = ProjectionFile.lookupSpatialReferenceID(extractPath, projection_file)
    #         else:
    #             print("There is no projection file, so default is being used")
    #             srid = 4302
    #         mask_map = RasterMapFile()
    #         mask_map.read(directory=extractPath, filename=mask_file, session=gsshapy_session, spatial=True, spatialReferenceID=srid)
    #         mask_map.getAsKmlClusters(session=gsshapy_session, path=kml_file, colorRamp={'colors':color, 'interpolatedPoints':1})
    #
    #         mask_map_dataset = gi_lib.check_dataset("mask-maps", CKAN_engine)
    #
    #         # mask_map_dataset = mask_map_dataset['result']['results'][0]['id']
    #
    #         # Add mask kml to CKAN for viewing
    #         resource, success = gi_lib.add_kml_CKAN(mask_map_dataset, CKAN_engine, kml_file, kml_name)
    #
    #         # Check to ensure the resource was added and save it to database by adding "kml_url"
    #         if success == True:
    #             job.kml_url = resource['url']
    #             session.commit()
    #             kml_links.append(job.kml_url)
    #             return JsonResponse({'kml_links': kml_links})
    return JsonResponse({'kml_links': kml_links})