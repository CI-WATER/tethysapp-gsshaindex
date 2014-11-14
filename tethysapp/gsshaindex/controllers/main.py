from django.shortcuts import render
from django.contrib import messages
import operator, random, pickle, pprint, zipfile, time, ConfigParser, os, json
from gsshapy.orm import *
from gsshapy.lib import db_tools as dbt
from django.http import JsonResponse
from tethys_apps.utilities import get_dataset_engine
from ..app import GSSHAIndex
import tethysapp.gsshaindex.lib as gi_lib
from ..lib import raster2pgsql_path, maps_api_key


from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine

def home(request):
    """
    Controller for the app home page.
    """
    context = {}

    session = jobs_sessionmaker()
    user = str(request.user)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Check to see if there's a models package
    present = gi_lib.check_package('gssha-models', CKAN_engine)
    print "The package was present? ",present

    # Check if the submit button has been clicked and if there is a file_id
    if ('submit_gssha' in request.POST):
        params = request.POST
        print params
        file_id = params['file_id']

        if file_id == "":
            messages.error(request, 'No GSSHA Model is selected')
        else:
            context['file_id']=file_id
            return render(request, 'gsshaindex/extract-gssha', context)


    # Find all the GSSHA models in the datasets
    results = CKAN_engine.get_dataset('gssha-models', console=True)
    print "RESOURCES: ",results['result']['resources']
    resources = results['result']['resources']

    # Create empty array to hold the information for the GSSHA models
    model_list = []

    no_files = True

    # Fill the array with information on the GSSHA models
    if len(resources) > 0:
        no_files = False
        for result in resources:
            file_id = result.get('id')
            job,success = gi_lib.get_job(file_id,user)
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
                file_name = job['original_name']

            model_list.append((file_name, file_id))

    if no_files == False:

        # model_list.sort(key=operator.itemgetter('name'))
        first_file_id = model_list[0][1]
        first_file_name = model_list[0][0]

        print "FILE NAME and ID", file_name, " & ", file_id

        #Display a google map with kmls
        google_map = {'height': '500px',
                        'width': '100%',
                        # 'kml_service': '/apps/gssha-index/get-mask-map/' + str(file_id),
                        'maps_api_key':maps_api_key}

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
        first_file_id = "'"
        first_file_name = ""

    context['file_id'] = first_file_id
    context['file_name'] = first_file_name
    context['model_list'] = model_list
    context['google_map'] = google_map
    context['select_model'] = select_model

    print context

    #Display the index page
    return render(request, 'gsshaindex/home.html', context)

def get_mask_map(request):
    """
    This action is used to pass the kml data to the google map.
    It must return a JSON response with a Python dictionary that
    has the key 'kml_links'.
    """
    kml_links = []


    #Save it to database by querying for the job and adding "kml_url"

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