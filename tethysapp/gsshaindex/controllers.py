from django.shortcuts import render
from django.contrib import messages
import operator, random, pickle, pprint, zipfile, time, ConfigParser, os, json
from gsshapy.orm import *
from gsshapy.lib import db_tools as dbt
from django.http import JsonResponse

from .model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine

# Get app.ini information
config_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.ini')
app_config = ConfigParser.RawConfigParser()
app_config.read(config_path)
raster2pgsql_path = app_config.get('postgis', 'raster2pgsql_path')
maps_api_key = app_config.get('api_key', 'maps_api_key')


def home(request):
    """
    Controller for the app home page.
    """
    context = {}

    session = jobs_sessionmaker()

    # Check to see if there's a models package
    # present = gi_lib.check_package('gssha-models')
    # print "The package was present? ",present

    # Check if the submit button has been clicked and if there is a file_id
    if ('submit_gssha' in request.POST):
        params = request.POST
        print params
        file_id = params['file_id']
        file_name = params['file_name']
        file_url = params['file_url']
        certification = params['file_certification']
        print file_url
        if file_id == "":
            messages.error(request, 'No GSSHA Model is selected')
        else:
            new_job = Jobs(name=file_name, user_id=context['user'], original_model={'id':file_id, 'url':file_url, 'name':file_name, 'certification':certification})
            session.add(new_job)
            session.commit()
            context['job_id'] = new_job.id
            # redirect(t.url_for('gsshaindex-extract-gssha', job_id=c.job_id))
            return render(request, 'gsshaindex/extract-gssha', context)

    # Create empty dictionary of cached masks if it doesn't exist
    # try:
    #     get_session_global('mask_cache')
    # except:
    #     mask_cache = {}
    #     set_session_global('mask_cache', mask_cache)

    # Find all the GSSHA models in the datasets
    # results = get_resource_by_field_value('model:GSSHA')
    results = {}

    # Create empty array to hold the information for the GSSHA models
    model_list = []
    # model_list = [{"name": "Test", "id": "TestID", "description": "TestDescription", "url": "TestURL", "certification": ""}]

    no_files = True

    # Fill the array with information on the GSSHA models
    if results.get('count') > 0:
        no_files = False
        for result in results.get('results'):
            if result.get('description') == "":
                description = "None"
            else:
                description = result.get('description')
            if result.get('certification') == "Certified":
                certification = "Certified"
            else:
                certification = ""
            model_list.append((result.get('name'), {"name": result.get('name'), "id": result.get('id'), "description": description, "url": result.get('url'), "certification": certification}))

    if no_files == False:

        model_list.sort(key=operator.itemgetter('name'))
        context['model_list'] = model_list
        file_id = model_list[0]['id']
        file_name = model_list[0]['name']
        file_url = model_list[0]['url']
        file_certification = model_list[0]['certification']

        #Display a google map with kmls
        google_map = {'height': '500px',
                        'width': '100%',
                        'kml_service': '/apps/gssha-index/get-mask-map/' + str(file_id),
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
        file_id = "'"
        file_name = ""
        file_url = ""
        file_certification = ""

    context['file_id'] = file_id
    context['file_name'] = file_name
    context['file_url'] = file_url
    context['file_certification'] = file_certification
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

    return JsonResponse({'kml_links': kml_links})

def secondpg(request, name):
    """
    Controller for the app home page.
    """
    context = {}

    context['name'] = name

    messages.error(request, 'My Message')

    return render(request, 'gsshaindex/namepg.html', context)
