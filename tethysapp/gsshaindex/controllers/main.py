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
    job, success = gi_lib.get_pending_job(job_id, user, session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id
    project_file_id = job.new_model_id

    # Give options for editing the index map
    if ('select_index' in request.POST):
        params = request.POST
        print params
        index_name = params['index_name']
        print index_name
        if (params['method'] == "Create polygons"):
            return redirect(reverse('gsshaindex:edit_index', kwargs={'job_id':job_id, 'index_name':index_name}))
        elif (params['method'] == "Upload shapefile"):
            # messages.error(request, "Select by polygon is currently in production and hasn't been initialized yet.")
            return redirect(reverse('gsshaindex:shapefile_index', kwargs={'job_id':job_id, 'index_name':index_name, 'shapefile_name':"None"}))
        elif (params['method'] == "Merge index maps"):
            # messages.error(request, "Merging index maps is currently in production and hasn't been initialized yet.")
            return redirect(reverse('gsshaindex:combine_index', kwargs={'job_id':job_id, 'index_name':index_name}))

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
                    'reference_kml_action': '/apps/gsshaindex/'+ job_id + '/get-index-maps/'  + map_name,
                    'maps_api_key':maps_api_key,
                    'drawing_types_enabled':[]}

    context['google_map'] = editable_map
    context['project_name'] = job.original_name
    context['resource_name'] = resource_name
    context['map_name'] = map_name
    context['job_id'] = job_id

    # return render(request, 'gsshaindex/namepg.html', context)
    return render(request, 'gsshaindex/select_index.html', context)


def get_index_maps(request, job_id, index_name):
    '''
    This action is used to pass the kml data to the google map. It must return the key 'kml_link'.
    '''
    # Get the job id and user id
    job_id = job_id
    map_name = index_name
    user = str(request.user)
    session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user,session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get the list of index files to display
    resource_list = json.loads(job.current_kmls)

    # Get the kml url
    kml_links = resource_list[map_name]['url']

    print kml_links

    return JsonResponse({'kml_links': [kml_links]})


def zip_file(request, job_id):
    '''
    This zips up the GSSHA files in preparation of their being run
    '''
    context = {}

    # Get the job id and user id
    job_id = job_id
    user = str(request.user)
    session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user,session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    project_file_id = job.new_model_id

    # Get the name and description from the submission
    params=request.POST
    not_clean_name = params['new_name']
    new_description = params['new_description']

    # Reformat the name by removing bad characters
    # bad_char = "',.<>()[]{}=+-/\"|:;\\^?!~`@#$%&* "
    bad_char = "',.<>[]{}=+-/\"|:;\\^?!~`@#$%&*"
    for char in bad_char:
        new_name = not_clean_name.replace(char,"_")

    #Create session
    gsshapy_session = gsshapy_sessionmaker()

    # Get project from the database
    projectFileAll = gsshapy_session.query(ProjectFile).get(project_file_id)

    # Create name for files
    project_name = projectFileAll.name
    if project_name.endswith('.prj'):
        project_name = project_name[:-4]
    pretty_date= time.strftime("%A %B %d, %Y %I:%M:%S %p")

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    newFileDir = os.path.join(userDir, 'newFile')
    writeFile = os.path.join(newFileDir, new_name)
    zipPath = os.path.join(newFileDir, '.'.join((new_name,'zip')))

    # Clear workspace folders
    gi_lib.clear_folder(newFileDir)
    gi_lib.clear_folder(writeFile)

    # Get all the project files
    projectFileAll.writeInput(session=gsshapy_session, directory=writeFile, name=new_name)

    # Make a list of the project files
    writeFile_list = os.listdir(writeFile)

    # Add each project file to the zip folder
    with zipfile.ZipFile(zipPath, "w") as gssha_zip:
        for item in writeFile_list:
            abs_path = os.path.join(writeFile, item)
            archive_path = os.path.join(new_name, item)
            gssha_zip.write(abs_path, archive_path)

    GSSHA_dataset = gi_lib.check_dataset("gssha-models", CKAN_engine)

    # Add the zipped GSSHA file to the public ckan
    results, success = gi_lib.add_zip_GSSHA(GSSHA_dataset, zipPath, CKAN_engine, new_name, new_description, pretty_date, user)

    # If the file zips correctly, get information and store it in the database
    if success == True:
        new_url = results['url']
        new_name = results['name']
        original_url = job.original_url
        original_name = job.original_name

    print "Original URL", original_url
    print "New URL", new_url

    model_data = {'original': {'url':original_url, 'name':original_name}, 'new':{'url':new_url, 'name':new_name}}
    job.run_urls = model_data
    job.new_name = new_name
    job.status = "ready to run"
    session.commit()

    return redirect(reverse('gsshaindex:status'))


def in_progress(request):
    context = {}

    # Get the user id
    user = str(request.user)

    # Get the jobs from the database
    session = jobs_sessionmaker()
    jobs = session.query(Jobs).\
                    filter(Jobs.user_id == user).\
                    filter(Jobs.status == "pending").\
                    order_by(Jobs.created.desc()).all()

    # Create array of pending jobs
    job_info=[]
    for job in jobs:
        info=[job.original_name, job.created, job.original_id]
        job_info.append(info)

    context['job_info'] = job_info

    return render(request, 'gsshaindex/uncompleted_jobs.html', context)

def status(request):
    context = {}

    # Get the user id
    user = str(request.user)

    # Get the jobs from the database
    session = jobs_sessionmaker()
    job = session.query(Jobs).\
                    filter(Jobs.user_id == user).\
                    order_by(Jobs.created.desc()).all()

    # Create array of jobs. If they haven't been submitted (new_name = None), don't add it to the list.
    job_info=[]
    for job in job:
        print job.new_name
        if job.new_name != None:
            info=[job.new_name, job.status, job.original_id]
            job_info.append(info)


    context['job_info'] = job_info

    return render(request, 'gsshaindex/jobs.html', context)

def fly(request, job_id):
    context = {}

    # Get the user id
    user = str(request.user)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    resultsPath = os.path.join(userDir, 'results')

    # Clear the results folder
    gi_lib.clear_folder(resultsPath)

    # Get the jobs from the database
    session = jobs_sessionmaker()
    job = session.query(Jobs).\
                    filter(Jobs.user_id == user).\
                    filter(Jobs.original_id == job_id).one()

    # Get the urls and names for the analysis
    run_urls = job.run_urls

    arguments={'new': {'url':run_urls['new']['url'], 'name':run_urls['new']['name']}, 'original':{'url':run_urls['original']['url'], 'name':run_urls['original']['name']}}

    # Set up for fly GSSHA
    job.status = "processing"
    session.commit()

    status = 'complete'

    results = []
    # results_urls = []
    results_urls = {}
    count = 0

    GSSHA_dataset = gi_lib.check_dataset("gssha-models", CKAN_engine)

    # Try running the web service
    # try:
    for k in arguments:
        url = str(arguments[k]['url'])
        print "URL: ", url

        if k == 'original' and job.original_certification=="Certified":
            print "The original model is certified"
            # results.append(url)
            results_urls['original']=url
            count +=1
            continue
        else:
            print "The model is not certified"
            resultsFile = os.path.join(resultsPath, arguments[k]['name'].replace(" ","_")+datetime.now().strftime('%Y%d%m%H%M%S'))
            gi_lib.flyGssha(url, resultsFile)

            # Push file to ckan dataset
            resource_name = ' '.join((arguments[k]['name'], '-Run',datetime.now().strftime('%b %d %y %H:%M:%S')))
            pretty_date= time.strftime("%A %B %d, %Y %I:%M:%S %p")
            result, success = gi_lib.add_zip_GSSHA(GSSHA_dataset, resultsFile, CKAN_engine, resource_name, "", pretty_date, user, certification="Certified")

            job.original_certification = "Certified"
            # session.commit()

            # Publish link to table
            # results.append(result['url'])
            if k=='original':
                results_urls['original']=result['url']
            else:
                results_urls['new']=result['url']
            count +=1

    if (count == 2):
        # results_urls = [results[0], results[1]]
        print results_urls
    else:
        status = 'failed'

    # except:
    #     status = 'failed'

    job.status = status
    job.result_urls = results_urls
    session.commit()
    session.close()


    return redirect(reverse('gsshaindex:status'))

def delete(request, job_id, return_to):
    context = {}

    # Get the user id
    user = str(request.user)

    # Get the job from the database and delete
    session = jobs_sessionmaker()
    job = session.query(Jobs).\
                    filter(Jobs.user_id == user).\
                    filter(Jobs.original_id == job_id).one()
    session.delete(job)
    session.commit()

    if return_to == "uncompleted":
        return redirect(reverse('gsshaindex:in_progress'))
    elif return_to == "jobs":
        return redirect(reverse('gsshaindex:status'))

def results(request, job_id, view_type):
    context = {}

    # Get the user id
    user = str(request.user)

    # Get the job from the database and delete
    session = jobs_sessionmaker()
    job = session.query(Jobs).\
                    filter(Jobs.user_id == user).\
                    filter(Jobs.original_id == job_id).one()

    # Get the run result urls
    result_files = job.result_urls

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    newResultsPath = os.path.join(userDir, 'new_results')
    originalResultsPath = os.path.join(userDir, 'original_results')

    # Clear the results folder
    gi_lib.clear_folder(userDir)
    gi_lib.clear_folder(newResultsPath)
    gi_lib.clear_folder(originalResultsPath)

    # Get the otl files
    new_otl_file = gi_lib.extract_otl(result_files['new'], newResultsPath)
    original_otl_file = gi_lib.extract_otl(result_files['original'], originalResultsPath)

    # Format the values for display with high charts
    new_values = []
    originalValues = []

    new_values = gi_lib.get_otl_values(newResultsPath, new_otl_file, new_values)
    originalValues = gi_lib.get_otl_values(originalResultsPath, original_otl_file, originalValues)

    # Set up for high charts hydrograph
    highcharts_object = {
            'chart': {
                'type': 'spline'
            },
            'title': {
                'text': 'Comparison Hydrograph'
            },
            'subtitle': {
                'text': 'Display of the two model results'
            },
            'legend': {
                'layout': 'vertical',
                'align': 'right',
                'verticalAlign': 'middle',
                'borderWidth': 0
            },
            'xAxis': {
                'title': {
                    'enabled': True,
                    'text': 'Time (hours)'
                },
                'labels': {
                    'formatter': 'function () { return this.value + " hr"; }'
                }
            },
            'yAxis': {
                'title': {
                    'enabled': True,
                    'text': 'Discharge (cfs)'
                },
                'labels': {
                    'formatter': 'function () { return this.value + " cfs"; }'
                }
            },
            'tooltip': {
                'headerFormat': '{series.name}',
                'pointFormat': '{point.x} hours: {point.y} cfs'
             },
            'series': [{
                'name': job.original_name.replace("_", " "),
                'color': '#0066ff',
                'dashStyle': 'ShortDash',
                'marker' : {'enabled': False},
                'data': originalValues
                },{
                'name': job.new_name.replace("_", " "),
                'marker' : {'enabled': False},
                'color': '#ff6600',
                'data': new_values}
            ]}

    hydrograph = {'highcharts_object': highcharts_object,
                        'width': '500px',
                        'height': '500px'}

    google_map = {'height': '600px',
                    'width': '100%',
                    'reference_kml_action': '/apps/gsshaindex/'+ job_id + '/get-depth-map/' + view_type,
                    'maps_api_key':maps_api_key}

    session.close()

    context['hydrograph'] = hydrograph
    context['google_map'] = google_map
    context['map_type'] = view_type
    context['original_name'] = job.original_name.replace("_", " ")
    context['new_name'] = job.new_name.replace("_", " ")
    context['original_file'] = job.result_urls['original']
    context['new_file'] = job.result_urls['new']
    context['job_id'] = job_id

    return render(request, 'gsshaindex/results.html', context)

def get_depth_map(request, job_id, view_type):
    context = {}

    # Get the user id
    user = str(request.user)

    # Get the job from the database and delete
    session = jobs_sessionmaker()
    job = session.query(Jobs).\
                    filter(Jobs.user_id == user).\
                    filter(Jobs.original_id == job_id).one()

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    depthMapDir = os.path.join(userDir, 'depth_maps')
    newDepthDir = os.path.join(depthMapDir, 'new')
    originalDepthDir = os.path.join(depthMapDir, 'original')

    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    kml_link = ""

    if view_type == "newTime":
        if job.newTime != None:
            kml_link = job.newTime
        else:
            result_url = job.result_urls['new']
            result = gi_lib.prepare_time_depth_map(user, result_url, job, newDepthDir, CKAN_engine)
            job.newTime = result['url']
            session.commit()
            kml_link = result['url']

    elif view_type == "newMax":
        if job.newMax != None:
            kml_link = job.newMax
        else:
            result_url = job.result_urls['new']
            result = gi_lib.prepare_max_depth_map(user, result_url, job, newDepthDir, CKAN_engine)
            job.newMax = result['url']
            session.commit()
            kml_link = result['url']

    elif view_type == "originalTime":
        if job.originalTime != None:
            kml_link = job.originalTime
        else:
            result_url = job.result_urls['original']
            result = gi_lib.prepare_time_depth_map(user, result_url, job, originalDepthDir, CKAN_engine)
            job.originalTime = result['url']
            session.commit()
            kml_link = result['url']

    elif view_type == "originalMax":
        if job.originalMax != None:
            kml_link = job.originalMax
        else:
            result_url = job.result_urls['original']
            result = gi_lib.prepare_max_depth_map(user, result_url, job, originalDepthDir, CKAN_engine)
            job.originalMax = result['url']
            session.commit()
            kml_link = result['url']

    elif view_type == "bothTime":
        if job.bothTime != None:
            kml_link = job.bothTime
        else:
            new_result_url = job.result_urls['new']
            original_result_url = job.result_urls['original']
            result = gi_lib.prepare_both_time_depth_map(user, new_result_url, original_result_url, job, newDepthDir, originalDepthDir, CKAN_engine)
            job.bothTime = result['url']
            session.commit()
            kml_link = result['url']

    elif view_type== "bothMax":
        if job.bothMax != None:
            kml_link = job.bothMax
        else:
            result_url = job.result_urls['new']
            original_result_url = job.result_urls['original']
            result = gi_lib.prepare_both_max_depth_map(user, new_result_url, original_result_url, job, newDepthDir, originalDepthDir, CKAN_engine)
            job.bothMax = result['url']
            session.commit()
            kml_link = result['url']

    else:
        kml_link=""

    session.close()

    return JsonResponse({'kml_links': kml_link})

def secondpg(request, name):
    """
    Controller for the app home page.
    """
    context = {}

    context['name'] = name

    messages.error(request, 'My Message')

    return render(request, 'gsshaindex/namepg.html', context)

def mapping_table(request):
    context = {}
    return render(request, 'gsshaindex/namepg.html', context)


