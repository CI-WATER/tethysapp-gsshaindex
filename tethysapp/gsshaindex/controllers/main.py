from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse
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


from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine

def home(request):
    """
    Controller for the app home page.
    """
    context = {}
    session = jobs_sessionmaker()
    user = str(request.user)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)
    session = jobs_sessionmaker()

    # Check to see if there's a models package
    present = gi_lib.check_package('gssha-models', CKAN_engine)

    # Check if the submit button has been clicked and if there is a file_id
    if ('file_id' in request.POST):
        params = request.POST
        file_id = params['file_id']
        if file_id == "":
            messages.error(request, 'No GSSHA Model is selected')
        else:
            job,success = gi_lib.get_new_job(file_id,user,session)
            job.status = "pending"
            date = datetime.now()
            formatted_date = '{:%Y-%m-%d-%H-%M-%S}'.format(date)
            new_id = file_id + "-" + formatted_date
            job.original_id = new_id
            session.commit()
            return redirect(reverse('gsshaindex:extract_gssha', kwargs={'job_id':new_id}))

    # Find all the GSSHA models in the datasets
    results = CKAN_engine.get_dataset('gssha-models')
    resources = results['result']['resources']

    # Create empty array to hold the information for the GSSHA models
    model_list = []

    no_files = True

    # Fill the array with information on the GSSHA models
    if len(resources) > 0:
        no_files = False
        for result in resources:
            file_id = result.get('id')
            # Check to see if the files are already in the database and add them if they aren't
            job,success = gi_lib.get_new_job(file_id,user,session)
            if success == False:
                if result['description'] == "":
                    file_description = "None"
                else:
                    file_description = result['description']
                file_name = result.get('name')
                file_url = result.get('url')
                file_certification = result.get('certification')
                new_job = Jobs(name=file_name, user_id=user, original_description=file_description, original_id=file_id, original_url=file_url, original_certification=file_certification)
                session.add(new_job)
                session.commit()
                context['job_id'] = new_job.id
            else:
                file_name = job.original_name
                file_description = job.original_description

            model_list.append((file_name, file_id, file_description))

    if no_files == False:
        # Display a google map with the first kml
        first_file_id = model_list[0][1]
        print "FIRST FILE ID: ", first_file_id

        google_map = {'height': '500px',
                        'width': '100%',
                        'reference_kml_action': '/apps/gsshaindex/get-mask-map/' + str(first_file_id),
                        'maps_api_key':maps_api_key}
        # Populate the drop-down menu
        select_model = {'display_text': 'Select GSSHA Model',
                    'name': 'select_a_model',
                    'multiple': False,
                    'options': model_list,
                    'initial': model_list[0]}

    else:
        #Display a google map with kmls
        google_map = {'height': '500px',
                        'width': '100%',
                        'maps_api_key':maps_api_key}
        select_model = ""

    context['model_list'] = model_list
    context['google_map'] = google_map
    context['select_model'] = select_model

    #Display the index page
    return render(request, 'gsshaindex/home.html', context)

def get_mask_map(request, file_id):
    """
    This action is used to pass the kml data to the google map.
    It must return a JSON response with a Python dictionary that
    has the key 'kml_links'.
    """
    kml_links = []

    session = jobs_sessionmaker()
    user = str(request.user)
    job, success = gi_lib.get_new_job(file_id, user,session)

    print job.kml_url

    if job.kml_url != None:
        print "A MASK MAP EXISTS"
        kml_links.append(job.kml_url)
        #TODO Need some way to check and see if the link works or if it's broken
        return JsonResponse({'kml_links': kml_links})
    else:
        # Check that there's a package to store kmls
        CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)
        present = gi_lib.check_package('kmls', CKAN_engine)

        # Specify the workspace
        controllerDir = os.path.abspath(os.path.dirname(__file__))
        gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
        publicDir = os.path.join(gsshaindexDir,'public')
        userDir = os.path.join(publicDir, str(user))

        # Clear the workspace
        gi_lib.clear_folder(userDir)

        url = job.original_url
        maskMapDir = os.path.join(userDir, 'mask_maps')
        extractPath = os.path.join(maskMapDir, file_id)
        mask_file = gi_lib.extract_mask(url, extractPath)
        if mask_file == "blank":
            print "Mask File Didn't Exist"
            job.kml_url = ''
            session.commit()
            return JsonResponse({'kml_links': ''})
        else:
            projection_file = gi_lib.extract_projection(url,extractPath)

            # Set up kml file name and save location
            name = job.original_name
            norm_name = name.replace(" ","")
            current_time = time.strftime("%Y%m%dT%H%M%S")
            kml_name = norm_name + "_" + user + "_" + current_time
            kml_ext = kml_name + ".kml"
            kml_file = os.path.join(extractPath, kml_ext)

            colors = [(237,9,222),(92,245,61),(61,184,245),(171,61,245),(250,245,105),(245,151,44),(240,37,14),(88,5,232),(5,232,190),(11,26,227)]
            color = [random.choice(colors)]

            # Extract mask map and create kml
            gsshapy_session = gsshapy_sessionmaker()
            if projection_file != "blank":
                srid = ProjectionFile.lookupSpatialReferenceID(extractPath, projection_file)
            else:
                print("There is no projection file, so default is being used")
                srid = 4302
            mask_map = RasterMapFile()
            mask_map.read(directory=extractPath, filename=mask_file, session=gsshapy_session, spatial=True, spatialReferenceID=srid)
            mask_map.getAsKmlClusters(session=gsshapy_session, path=kml_file, colorRamp={'colors':color, 'interpolatedPoints':1})

            mask_map_dataset = gi_lib.check_dataset("mask-maps", CKAN_engine)

            # mask_map_dataset = mask_map_dataset['result']['results'][0]['id']

            # Add mask kml to CKAN for viewing
            resource, success = gi_lib.add_kml_CKAN(mask_map_dataset, CKAN_engine, kml_file, kml_name)

            # Check to ensure the resource was added and save it to database by adding "kml_url"
            if success == True:
                job.kml_url = resource['url']
                session.commit()
                kml_links.append(job.kml_url)
                return JsonResponse({'kml_links': kml_links})


def extract_gssha(request, job_id):
    '''
    This takes the file name and id that were submitted and unzips the files, finds the index maps, and creates kmls.
    '''
    context = {}
    user = str(request.user)
    session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user,session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    indexMapDir = os.path.join(userDir, 'index_maps')

    # Clear the workspace
    gi_lib.clear_folder(userDir)
    gi_lib.clear_folder(indexMapDir)

    # Get url for the resource and extract the GSSHA file
    url = job.original_url
    extract_path, unique_dir = gi_lib.extract_zip_from_url(user, url, userDir)

    # Create GSSHAPY Session
    gsshapy_session = gsshapy_sessionmaker()

    # Find the project file
    for root, dirs, files in os.walk(userDir):
        for file in files:
            if file.endswith(".prj"):
                project_name = file
                project_path = os.path.join(root, file)
                read_dir = os.path.dirname(project_path)

    # Create an empty Project File Object
    project = ProjectFile()

    project.readInput(directory=read_dir,
                      projectFileName=project_name,
                      session = gsshapy_session,
                      spatial=True)

    # Create empty dictionary to hold the kmls from this session
    current_kmls = {}

    # Store model information
    job.new_model_name = project.name
    job.new_model_id = project.id
    job.created = datetime.now()

    # Get index maps
    index_list = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project.mapTableFile).all()

    # Loop through the index
    for current_index in index_list:
        # Create kml file name and path
        current_time = time.strftime("%Y%m%dT%H%M%S")
        resource_name = current_index.name + "_" + str(user) + "_" + current_time
        kml_ext = resource_name + '.kml'
        clusterFile = os.path.join(indexMapDir, kml_ext)

         # Generate color ramp
        current_index.getAsKmlClusters(session=gsshapy_session,
                                       path = clusterFile,
                                       colorRamp = ColorRampEnum.COLOR_RAMP_HUE,
                                       alpha=0.6)

        index_map_dataset = gi_lib.check_dataset("index-maps", CKAN_engine)

        resource, status = gi_lib.add_kml_CKAN(index_map_dataset, CKAN_engine, clusterFile, resource_name)

        # If the kml is added correctly, create an entry for the current_kmls with the name as the index name
        if status == True:
            current_kmls[current_index.name] = {'url':resource['url'], 'full_name':resource['name']}

    # Add the kmls with their url to the database
    job.current_kmls = json.dumps(current_kmls)
    session.commit()

    context['job_id'] = job_id

    return redirect(reverse('gsshaindex:select_index', kwargs={'job_id':job_id}))


def select_index(request, job_id):
    """
    Controller for the app home page.
    """
    context = {}
    user = str(request.user)
    session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user,session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id
    project_file_id = job.new_model_id

    # Get list of shapefiles
    shapefile_list = get_resource_by_field_value('model:Shapefile')
    if len(shapefile_list.get('results')) == 0:
        shapefile_id = "NONE"
    else:
        shapefile_id = shapefile_list.get('results')[0]['id']
    print shapefile_id

    # Give options for editing the index map
    if ('select_index' in request.POST):
        params = request.POST
        map_name = params['index_name']
        if (params['method'] == "Create polygons"):
            redirect(t.url_for('gsshaindex-edit-index', map_name=map_name, job_id=job_id))
        elif (params['method'] == "Download shapefile"):
#                 h.flash_error("Select by polygon is currently in production and hasn't been initialized yet.")
            redirect(t.url_for('gsshaindex-shapefile-index', map_name=map_name, job_id=job_id, shapefile_id = shapefile_id))
        elif (params['method'] == "Merge index maps"):
            redirect(t.url_for('gsshaindex-combine-index', map_name=map_name, job_id=job_id))

    print "CERTIFICATION", job.original_certification

    # Get list of index files
    resource_kmls = json.loads(job.current_kmls)

    # Create arrays of the names and urls
    resource_name = []
    resource_url = []
    for key in resource_kmls:
        resource_name.append(key)
        resource_url.append(resource_kmls[key]['url'])

    # Set the first index as the active one
    map_name = str(resource_name[0])

    #Create session
    gsshapy_session = gsshapy_sessionmaker()

    # Use project id to link to map table file
    project_file = gsshapy_session.query(ProjectFile).filter(ProjectFile.id == project_file_id).one()
    index_raster = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == map_name).one()
    indices = index_raster.indices


    # Set up map properties
    editable_map = {'height': '600px',
                    'width': '100%',
                    # 'reference_kml_action': '/apps/gssha-index/get-index-maps/' + c.job_id + '/' + c.map_name,
                    'maps_api_key':maps_api_key,
                    'drawing_types_enabled':[]}

    context['shapefile_list'] = shapefile_list
    context['editable_map'] = editable_map
    context['project_name'] = job.original_name
    context['resource_name'] = resource_name
    context['map_name'] = map_name
    context['job_id'] = job_id

    return render(request, 'gsshaindex/namepg.html', context)


def get_index_maps(request, job_id, index_name):
    '''
    This action is used to pass the kml data to the google map. It must return the key 'kml_link'.
    '''
    # Get the job id and user id
    job_id = job_id
    index_name = map_name
    user = str(request.user)
    session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user,session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get the list of index files to display
    resource_list = json.loads(job.current_kmls)

    # Get the kml url
    kml_links = resource_list[map_name]['url']

    return JsonResponse({'kml_links': kml_links})


def secondpg(request, name):
    """
    Controller for the app home page.
    """
    context = {}

    context['name'] = name

    messages.error(request, 'My Message')

    return render(request, 'gsshaindex/namepg.html', context)


def status(request):
    return render(request, 'gsshaindex/namepg.html', context)