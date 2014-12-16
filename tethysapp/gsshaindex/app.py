from tethys_apps.base import TethysAppBase, PersistentStore, app_controller_maker, DatasetService


class GSSHAIndex(TethysAppBase):
    """
    Tethys App Class for GSSHA Index.
    """

    name = 'GSSHA Index Map Editor'
    index = 'gsshaindex:home'
    icon = 'gsshaindex/images/luedit.jpg'
    package = 'gsshaindex'
    root_url = 'gsshaindex'
    color = '#87CEFA'
        
    def controllers(self):
        """
        Add controllers
        """
        AppController = app_controller_maker(self.root_url)

        controllers = (AppController(name='home',
                                     url='gsshaindex',
                                     controller='gsshaindex.controllers.main.home'
                       # ),AppController(name='secondpg',
                       #               url='gsshaindex/{name}',
                       #               controller='gsshaindex.controllers.main.secondpg'
                       ),AppController(name='info_by_id',
                                     url='gsshaindex/info-by-id/{file_id}',
                                     controller='gsshaindex.controllers.ajax.info_by_id'
                       ),AppController(name='extract_gssha',
                                     url='gsshaindex/{job_id}/extract-gssha',
                                     controller='gsshaindex.controllers.main.extract_gssha'
                       ),AppController(name='get_mask_map',
                                     url='gsshaindex/get-mask-map/{file_id}',
                                     controller='gsshaindex.controllers.main.get_mask_map'
                       ),AppController(name='select_index',
                                     url='gsshaindex/{job_id}/select-index',
                                     controller='gsshaindex.controllers.main.select_index'
                       ),AppController(name='get_index_maps',
                                     url='gsshaindex/{job_id}/get-index-maps/{index_name}',
                                     controller='gsshaindex.controllers.main.get_index_maps'
                       ),AppController(name='edit_index',
                                     url='gsshaindex/{job_id}/edit-index/{index_name}',
                                     controller='gsshaindex.controllers.draw_index.edit_index'
                       # ),AppController(name='shapefile_index',
                       #               url='gsshaindex/{job_id}/shapefile-index/{index_name}/(shapefile_id}',
                       #               controller='gsshaindex.controllers.shapefile_index'
                       # ),AppController(name='shapefile_upload',
                       #               url='gsshaindex/{job_id}/shapefile-upload/{index_name}/(shapefile_id}',
                       #               controller='gsshaindex.controllers.shapefile_upload'
                       # ),AppController(name='get_srid_from_wkt',
                       #               url='gsshaindex/get-srid-from-wkt/{url}',
                       #               controller='gsshaindex.controllers.get_srid_from_wkt'
                       # ),AppController(name='show_overlay',
                       #               url='gsshaindex/{job_id}/show_overlay/{index_name}/(shapefile_id}',
                       #               controller='gsshaindex.controllers.show_overlay'
                       # ),AppController(name='combine_index',
                       #               url='gsshaindex/{job_id}/combine-index/{index_name}',
                       #               controller='gsshaindex.controllers.combine_index'
                       ),AppController(name='submit_edits',
                                     url='gsshaindex/{job_id}/submit-edits/{index_name}',
                                     controller='gsshaindex.controllers.draw_index.submit_edits'
                       ),AppController(name='mapping_table',
                                     url='gsshaindex/{job_id}/mapping-table/{index_name}/{mapping_table_number}',
                                     controller='gsshaindex.controllers.index_desc_and_val.mapping_table'
                       ),AppController(name='replace_values',
                                     url='gsshaindex/{job_id}/replace-values/{index_name}/{mapping_table_number}',
                                     controller='gsshaindex.controllers.index_desc_and_val.replace_values'
                       ),AppController(name='submit_mapping_table',
                                     url='gsshaindex/{job_id}/submit-mapping-table/{index_name}/{mapping_table_number}',
                                     controller='gsshaindex.controllers.index_desc_and_val.submit_mapping_table'
                       ),AppController(name='zip_file',
                                     url='gsshaindex/{job_id}/zip-file',
                                     controller='gsshaindex.controllers.main.zip_file'
                       ),AppController(name='status',
                                       url='gsshaindex/status',
                                       controller='gsshaindex.controllers.main.status'
                       # ),AppController(name='job_status',
                       #               url='gsshaindex/{job_id}/job-status',
                       #               controller='gsshaindex.controllers.job-status'
                       ),AppController(name='fly',
                                     url='gsshaindex/{job_id}/fly',
                                     controller='gsshaindex.controllers.main.fly'
                       ),AppController(name='delete',
                                     url='gsshaindex/{job_id}/delete',
                                     controller='gsshaindex.controllers.main.delete'
                       ),AppController(name='results',
                                     url='gsshaindex/{job_id}/results/{view_type}',
                                     controller='gsshaindex.controllers.main.results'
                       ),AppController(name='get_depth_map',
                                     url='gsshaindex/{job_id}/get-depth-map/{view_type}',
                                     controller='gsshaindex.controllers.main.get_depth_map'
                       ),
        )

        return controllers

    def persistent_stores(self):
        """
        Add persistent stores
        """
        stores = (PersistentStore(name='primary',
                                  initializer='init_stores:init_primary',
                                  postgis=True
                  ),PersistentStore(name='gsshaidx_db',
                                  initializer='init_stores:init_gsshaidx_db',
                                  postgis=True
                  ),PersistentStore(name='gsshapy_db',
                                  initializer='init_stores:init_gsshapy_db',
                                  postgis=True
                  ),PersistentStore(name='shapefile_db',
                                  initializer='init_stores:init_shapefile_db',
                                  postgis=True
                  ),
        )

        return stores

    def dataset_services(self):
        """
        Add one or more dataset services
        """
        dataset_services = (DatasetService(name='gsshaindex_ciwweb',
                                           type='ckan',
                                           endpoint='http://ciwweb.chpc.utah.edu/api/3/action',
                                           apikey='c9f477f0-118f-49f1-8d5a-b35757689c74'
                                           ),
        )

        return dataset_services
