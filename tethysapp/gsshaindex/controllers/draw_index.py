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


def edit_index(request, job_id, index_name):
    """
    Controller for the edit index by manually drawing in edits page.
    """
    context = {}
    user = str(request.user)

    # Get the job from the database
    job_session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user, job_session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id
    project_file_id = job.new_model_id

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    indexMapDir = os.path.join(userDir, 'index_maps')

    gsshapy_session = gsshapy_sessionmaker()

    # Use project id to link to original map table file
    project_file = gsshapy_session.query(ProjectFile).filter(ProjectFile.id == project_file_id).one()
    new_index = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()
    mapTables = new_index.mapTables
    indices = new_index.indices

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

    # Set up map properties
    editable_map = {'height': '600px',
                    'width': '100%',
                    'reference_kml_action': '/apps/gsshaindex/'+ job_id + '/get-index-maps/'  + index_name,
                    'maps_api_key':maps_api_key,
                    'drawing_types_enabled': ['POLYGONS'],
                    'initial_drawing_mode': 'POLYGONS',
                    'output_format': 'WKT'}

    context['google_map'] = editable_map
    context['mapTables'] = mapTables
    context['indices'] = indices
    context['resource_names'] = resource_names
    context['resource_url'] = resource_url
    context['resource_list'] = resource_list
    context['index_name'] = index_name
    context['job_id'] = job_id

    return render(request, 'gsshaindex/edit_index.html', context)

def submit_edits(request, job_id, index_name):
    '''
    Controller that handles submissions of edits from the user after they manually edit an index map.
    '''
    context = {}
    user = str(request.user)
    params = request.POST

    # Get the job from the database
    job_session = jobs_sessionmaker()
    job, success = gi_lib.get_pending_job(job_id, user, job_session)
    CKAN_engine = get_dataset_engine(name='gsshaindex_ciwweb', app_class=GSSHAIndex)

    # Get project file id
    project_file_id = job.new_model_id

    #Create session
    gsshapy_session = gsshapy_sessionmaker()

    # Specify the workspace
    controllerDir = os.path.abspath(os.path.dirname(__file__))
    gsshaindexDir = os.path.abspath(os.path.dirname(controllerDir))
    publicDir = os.path.join(gsshaindexDir,'public')
    userDir = os.path.join(publicDir, str(user))
    indexMapDir = os.path.join(userDir, 'index_maps')

    # Use project id to link to original map table file
    project_file = gsshapy_session.query(ProjectFile).filter(ProjectFile.id == project_file_id).one()
    index_raster = gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()
    mask_file = gsshapy_session.query(RasterMapFile).filter(RasterMapFile.projectFileID == project_file_id).filter(RasterMapFile.fileExtension == "msk").one()

    mapTables = index_raster.mapTables

    jsonGeom = json.loads(params['geometry'])
    geometries= jsonGeom['geometries']

    #Convert from json to WKT
    for geometry in geometries:
        wkt = geometry['wkt']

        value = geometry['properties']['value']
        print "WKT: ", value

        #Loop through indices and see if they match
        index_raster_indices = index_raster.indices
        index_present = False
        for index in index_raster_indices:
            if int(index.index) == int(value):
                index_present = True
                break

        # Create new index value if it doesn't exist and add change the number of ids
        if index_present == False:
            new_indice = MTIndex(value, "", "")
            new_indice.indexMap = index_raster
            for mapping_table in mapTables:
                print "Mapping Table:", mapping_table
                distinct_vars = gsshapy_session.query(distinct(MTValue.variable)).\
                                 filter(MTValue.mapTable == mapping_table).\
                                 order_by(MTValue.variable).\
                                 all()
                print "Distinct Vars: ", distinct_vars
                variables = []
                for var in distinct_vars:
                    variables.append(var[0])

                for variable in variables:
                    print variable
                    new_value = MTValue(variable, 0)
                    new_value.mapTable = mapping_table
                    new_value.index = new_indice

        if project_file.srid == None:
            srid = 26912
        else:
            srid = project_file.srid

            gsshapy_session.commit()
        print "id1: ", index_raster.id
        # Change values in the index map
        statement = '''UPDATE idx_index_maps
                        SET raster = ST_SetValue(raster,1, ST_Transform(ST_GeomFromText(\''''+ unicode(wkt) +'''\',4326),'''+ unicode(srid) +'''),'''+ unicode(value) +''')
                        WHERE id = '''+ unicode(index_raster.id) +''';
                        '''
        result = gsshapy_engine.execute(statement)

        gsshapy_session.commit()

    print "id: ", index_raster.id
    # Crop the index map by the mask map
    statementclip = ''' UPDATE idx_index_maps
                        SET raster = ST_MapAlgebra(
                        (SELECT raster FROM idx_index_maps WHERE id = '''+ unicode(index_raster.id) +'''),1,
                        (SELECT raster FROM idx_index_maps WHERE id = '''+ unicode(mask_file.id) +'''),1,
                        '([rast1]*[rast2])'
                        )
                        WHERE id = '''+ unicode(index_raster.id) +''';
                    '''

    # Get the values in the index map
    statement3 = '''SELECT (pvc).*
                    FROM (SELECT ST_ValueCount(raster,1,true) As pvc
                    FROM idx_index_maps WHERE id = '''+ unicode(index_raster.id) +''') AS foo
                    ORDER BY (pvc).value;
                    '''
#         result2 = gsshapy_engine.execute(statementclip)
    result3 = gsshapy_engine.execute(statement3)

    numberIDs = 0
    ids = []
    for row in result3:
        numberIDs +=1
        ids.append(row.value)

#         index_raster.mapTables[mapTableNumber].numIDs = numberIDs
#         gsshapy_session.commit()

    map_table_count = 0
    for mapping_table in mapTables:

        index_raster.mapTables[map_table_count].numIDs = numberIDs
        gsshapy_session.commit()

        indices = gsshapy_session.query(distinct(MTIndex.index), MTIndex.id, MTIndex.description1, MTIndex.description2).\
                               join(MTValue).\
                               filter(MTValue.mapTable == mapTables[map_table_count]).\
                               order_by(MTIndex.index).\
                               all()

        for index in indices:
            if not int(index[0]) in ids:
                bob = gsshapy_session.query(MTIndex).get(index.id)
                for val in bob.values:
                    gsshapy_session.delete(val)
                gsshapy_session.delete(bob)

        gsshapy_session.commit()
        map_table_count +=1

    print ids

    index_raster =  gsshapy_session.query(IndexMap).filter(IndexMap.mapTableFile == project_file.mapTableFile).filter(IndexMap.name == index_name).one()

    # Create kml file name and path
    current_time = time.strftime("%Y%m%dT%H%M%S")
    resource_name = index_raster.name + "_" + str(user) + "_" + current_time
    kml_ext = resource_name + '.kml'
    clusterFile = os.path.join(indexMapDir, kml_ext)

    # Generate color ramp
    index_raster.getAsKmlClusters(session=gsshapy_session, path=clusterFile, colorRamp=ColorRampEnum.COLOR_RAMP_HUE, alpha=0.6)

    index_map_dataset = gi_lib.check_dataset("index-maps", CKAN_engine)
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

    context['index_name'] = index_name
    context['job_id'] = job_id

    return redirect(reverse('gsshaindex:edit_index', kwargs={'job_id':job_id, 'index_name':index_name}))
