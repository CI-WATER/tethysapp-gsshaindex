from mapkit.RasterConverter import RasterConverter
from sqlalchemy import distinct

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


def combine_index(request, job_id, index_name):
    """
    Controller for the edit index by manually drawing in edits page.
    """
    context = {}
    user = str(request.user)

    # Get the job from the database
    job_session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user, job_session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id and gsshapy_session
    project_file_id = job.new_model_id
    gsshapy_session = gsshapy_sessionmaker()

    # Use project id to link to original map table file
    project_file = gsshapy_session.query(ProjectFile).filter(ProjectFile.id == project_file_id).one()
    new_index = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()
    mapTables = new_index.mapTables
    indices = new_index.indices

    # Get list of index files
    resource_list = json.loads(job.current_kmls)

    # Create blank array for names and urls
    resource_names = []
    resource_url = []
    resource_info = []

    # Get array of names and urls
    for key in resource_list:
        resource_names.append(key)
        resource_url.append(resource_list[key]['url'])
        resource_info.append((key,key))

    select_input1 = {'display_text': "Select first index map",
                       'name': 'select1',
                       'multiple': False,
                       'options': resource_info}

    select_input2 = {'display_text': "Select second index map or none",
                       'name': 'select2',
                       'multiple': False,
                       'options': [("None", "none")] + resource_info}

    # if the next button was pressed
    if request.POST:
        params = request.POST
        # Error message if both maps selected are the same
        if params['select1'] == params['select2']:
            result = ""
            messages.error(request, "You must select two different index maps. Or if you'd like to replace this map with a different map, select None for the second option")
        # Process if only one map is selected
        elif params['select2'] == "none":
            select1_id = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == params['select1']).one()
            print "ID1: ", select1_id.id
            print "ID2: ", new_index.id
            statement = '''UPDATE idx_index_maps
                                  Set raster = ST_MapAlgebra(
                                  (SELECT raster FROM idx_index_maps WHERE id = '''+ unicode(select1_id.id) +'''), 1,
                                  (SELECT raster FROM idx_index_maps WHERE id = '''+ unicode(new_index.id) +'''), 1,
                                  '([rast1]*1000 + [rast2]*0)'
                                  )
                                WHERE id = '''+ unicode(new_index.id) +''';
                            '''
            result = gi_lib.timeout(gsshapy_engine.execute, args=(statement,), kwargs={}, timeout=10, result_can_be_pickled=False, default=None)
        # Process if two maps are selected
        else:
            # Get the ids for the two index maps to be combined
            select1_id = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == params['select1']).one()
            select2_id = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == params['select2']).one()
            # Combine the maps and give a unique id
            statement = '''UPDATE idx_index_maps
                              SET raster =ST_MapAlgebra(
                              (SELECT raster FROM idx_index_maps WHERE id = '''+ unicode(select1_id.id) +'''), 1,
                              (SELECT raster FROM idx_index_maps WHERE id = '''+ unicode(select2_id.id) +'''), 1,
                              '(([rast1]*1000) + [rast2])'
                              )
                            WHERE id = '''+ unicode(new_index.id) +''';
                        '''
            result = gi_lib.timeout(gsshapy_engine.execute, args=(statement,), kwargs={}, timeout=10, result_can_be_pickled=False, default=None)

        if result != "":
            # Get the values in the index map
            statement3 = '''SELECT (pvc).*
                            FROM (SELECT ST_ValueCount(raster,1,true) As pvc
                            FROM idx_index_maps WHERE id = '''+ unicode(new_index.id) +''') AS foo
                            ORDER BY (pvc).value;
                            '''
            result3 = gsshapy_engine.execute(statement3)

            # Get the indices for the index being changed
            indices = gsshapy_session.query(distinct(MTIndex.index), MTIndex.id, MTIndex.description1, MTIndex.description2).\
                                   join(MTValue).\
                                   filter(MTValue.mapTable == mapTables[0]).\
                                   order_by(MTIndex.index).\
                                   all()

            # Go through the map tables that use the index map
            map_table_count = 0
            for mapping_table in mapTables:

                # Reset the number of ids to start counting them
                numberIDs = 0
                ids = []

                # Go through each new id value
                for row in result3:
                    index_present = False
                    numberIDs +=1
                    ids.append(row.value)
                    large_id = int(row[0])
                    for index in new_index.indices:
                        if int(index.index) == int(row[0]):
                            index_present = True
                            break

                    if index_present == False:
                        if str(large_id).endswith("000") == False:
                            second_id = str(large_id).split("0")[-1]
                            first_id = (large_id - int(second_id))/1000
                        else:
                            first_id = (large_id)/1000
                            second_id = ""
                            description2 = ""

                        pastinfo1 = gsshapy_session.query(distinct(MTIndex.index), MTIndex.id, MTIndex.description1, MTIndex.description2).\
                                filter(MTIndex.idxMapID == select1_id.id).\
                                filter(MTIndex.index == first_id).\
                                all()
                        description1 = pastinfo1[0].description1 + " " + pastinfo1[0].description2

                        if second_id != "":
                            pastinfo2 = gsshapy_session.query(distinct(MTIndex.index), MTIndex.id, MTIndex.description1, MTIndex.description2).\
                                    filter(MTIndex.idxMapID == select2_id.id).\
                                    filter(MTIndex.index == second_id).\
                                    all()
                            description2 = pastinfo2[0].description1 + " " + pastinfo2[0].description2

                        # Create new index value
                        new_indice = MTIndex(row[0], description1, description2)
                        new_indice.indexMap = new_index
                        for mapping_table in mapTables:
                            distinct_vars = gsshapy_session.query(distinct(MTValue.variable)).\
                                             filter(MTValue.mapTable == mapping_table).\
                                             order_by(MTValue.variable).\
                                             all()

                            variables = []
                            for var in distinct_vars:
                                variables.append(var[0])

                            for variable in variables:
                                new_value = MTValue(variable, 0)
                                new_value.mapTable = mapping_table
                                new_value.index = new_indice

                # Delete indices that aren't present
                for index in indices:
                    if not int(index[0]) in ids:
                        fetched_index = gsshapy_session.query(MTIndex).get(index.id)
                        for val in fetched_index.values:
                            gsshapy_session.delete(val)
                        gsshapy_session.delete(fetched_index)

                new_index.mapTables[map_table_count].numIDs = numberIDs
                map_table_count +=1

            indices = gsshapy_session.query(distinct(MTIndex.index), MTIndex.id, MTIndex.description1, MTIndex.description2).\
                                   join(MTValue).\
                                   filter(MTValue.mapTable == mapTables[0]).\
                                   order_by(MTIndex.index).\
                                   all()

            index_raster =  gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()

            # Specify the workspace
            controllerDir = os.path.abspath(os.path.dirname(__file__))
            gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
            publicDir = os.path.join(gsshaindexDir,'public')
            userDir = os.path.join(publicDir, str(user))
            indexMapDir = os.path.join(userDir, 'index_maps')

            # Create kml file name and path
            current_time = time.strftime("%Y%m%dT%H%M%S")
            resource_name = index_raster.name + "_" + str(user) + "_" + current_time
            kml_ext = resource_name + '.kml'
            clusterFile = os.path.join(indexMapDir, kml_ext)

            index_map_dataset = gi_lib.check_dataset("index-maps", CKAN_engine)

            # Generate color ramp
            index_raster.getAsKmlClusters(session=gsshapy_session, path = clusterFile, colorRamp = ColorRampEnum.COLOR_RAMP_HUE, alpha=0.6)

            resource, status = gi_lib.add_kml_CKAN(index_map_dataset, CKAN_engine, clusterFile, resource_name)

            temp_list = json.loads(job.current_kmls)

            if status == True:
                for item in temp_list:
                        if item == index_name:
                            del temp_list[item]
                            temp_list[index_name] = {'url':resource['url'], 'full_name':resource['name']}
                            break

            job.current_kmls = json.dumps(temp_list)
            job_session.commit()
            gsshapy_session.commit()
            job_session.close()
            gsshapy_session.close()

            return redirect(reverse('gsshaindex:mapping_table', kwargs={'job_id':job_id, 'index_name':index_name, 'mapping_table_number':'0'}))

    job_session.commit()
    gsshapy_session.commit()
    job_session.close()
    gsshapy_session.close()

    # Set the first index as the active one
    index_names = str(resource_names[0])

    # Set up map properties
    editable_map = {'height': '400px',
                      'width': '100%',
                      'reference_kml_action': '/apps/gsshaindex/' + job_id + '/get-index-maps/' + index_names,
                      'maps_api_key':maps_api_key,
                      'drawing_types_enabled':[]}

    context['replaced_index'] = index_name
    context['index_name'] = index_names
    context['google_map'] = editable_map
    context['select_input1'] = select_input1
    context['select_input2'] = select_input2
    context['job_id'] = job_id
    context['resource_name'] = resource_names

    return render(request, 'gsshaindex/combine_index.html', context)
