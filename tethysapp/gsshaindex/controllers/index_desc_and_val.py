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
from sqlalchemy import MetaData, create_engine, distinct

from ..model import Jobs, jobs_sessionmaker, gsshapy_sessionmaker, gsshapy_engine

def mapping_table(request, job_id, index_name, mapping_table_number):
    '''
    This identifies the mapping tables that relate to the index map that is being edited and prepares them to be displayed for editing.
    '''
    context = {}

    # Get the user id and the project file id
    user = str(request.user)
    session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user,session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id
    project_file_id = job.new_model_id

    #Create session
    gsshapy_session = gsshapy_sessionmaker()

    # Use project id to link to map table file
    project_file = gsshapy_session.query(ProjectFile).filter(ProjectFile.id == project_file_id).one()
    index_raster = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()
    indices = index_raster.indices
    mapTables = index_raster.mapTables

    mapping_table_number = int(mapping_table_number)

    # Process for if descriptions are submitted
    if ('submit_descriptions' in request.POST):
        params = request.POST
        for key in params:
            if "indice" in key:
                if "desc1" in key:
                    identity = int(key.replace("indice-desc1-",""))
                    mapDesc1 = gsshapy_session.query(MTIndex).get(identity)
                    mapDesc1.description1 = params[key]

                else:
                    identity = key.replace("indice-desc2-","")
                    mapDesc2 = gsshapy_session.query(MTIndex).get(identity)
                    mapDesc2.description2 = params[key]

        gsshapy_session.commit()

     # Get list of index files
    resource_kmls = json.loads(job.current_kmls)

    # Create array of kml names and urls
    resource_name = []
    resource_url = []
    for key in resource_kmls:
        resource_name.append(key)
        resource_url.append(resource_kmls[key]['url'])

    # Find the associated map tables and add them to an array
    arrayMapTables = []
    count = 0
    for table in mapTables:
        name =  str(table.name)
        clean = name.replace("_"," ")
        arrayMapTables.append([clean, table.name, count])
        count +=1

    print mapTables
    print arrayMapTables

    # Find the variables that are related to the active map table
    distinct_vars = gsshapy_session.query(distinct(MTValue.variable)).\
                                 filter(MTValue.mapTable == mapTables[mapping_table_number]).\
                                 order_by(MTValue.variable).\
                                 all()

    # Create an array of the variables in the active map table
    variables = []
    for var in distinct_vars:
        variables.append(var[0])

    # Cross tabulate manually to populate the mapping table information
    indices = gsshapy_session.query(distinct(MTIndex.index), MTIndex.id, MTIndex.description1, MTIndex.description2).\
                           join(MTValue).\
                           filter(MTValue.mapTable == mapTables[mapping_table_number]).\
                           order_by(MTIndex.index).\
                           all()

    # Get all the values to populate the table
    var_values = []
    for var in variables:
        values = gsshapy_session.query(MTValue.id, MTValue.value).\
                              join(MTIndex).\
                              filter(MTValue.mapTable == mapTables[mapping_table_number]).\
                              filter(MTValue.variable == var).\
                              order_by(MTIndex.index).\
                              all()
        var_values.append(values)
    zipValues = zip(*var_values)

    # Dictionary of properties for the map
    google_map = {'height': '400px',
                      'width': '100%',
                      'kml_service': '/apps/gsshaindex/' + job_id + '/get-index-maps/' + index_name,
                      'maps_api_key':maps_api_key}

    num_indices = []
    i=0
    for indice in indices:
        num_indices.append(i)
        i += 1
    print num_indices

    context['indices'] = indices
    context['job_id'] = job_id
    context['index_name'] = index_name
    context['mapping_table_number'] = mapping_table_number
    context['resource_kmls'] = resource_kmls
    context['resource_name'] = resource_name
    context['resource_url'] = resource_url
    context['mapTables'] = arrayMapTables
    context['variables'] = variables
    context['google_map'] = google_map
    context['values'] = zipValues
    context['num_indices'] = [num_indices]

    return render(request, 'gsshaindex/mapping_table.html', context)


def replace_values(request):
    context = {}
    return render(request, 'gsshaindex/namepg.html', context)

def submit_mapping_table(request):
    context = {}
    return render(request, 'gsshaindex/namepg.html', context)