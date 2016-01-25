from tethys_sdk.base import TethysAppBase, url_map_maker
from tethys_sdk.stores import PersistentStore


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
        
    def url_maps(self):
        """
        Add Url Maps
        """
        UrlMap = url_map_maker(self.root_url)

        url_maps = (UrlMap(name='home',
                           url='gsshaindex',
                           controller='gsshaindex.controllers.main.home'),
                    UrlMap(name='info_by_id',
                           url='gsshaindex/info-by-id/{file_id}',
                           controller='gsshaindex.controllers.ajax.info_by_id'),
                    UrlMap(name='extract_gssha',
                           url='gsshaindex/{job_id}/extract-gssha',
                           controller='gsshaindex.controllers.main.extract_gssha'),
                    UrlMap(name='extract_existing_gssha',
                           url='gsshaindex/{job_id}/extract-existing-gssha',
                           controller='gsshaindex.controllers.main.extract_existing_gssha'),
                    UrlMap(name='get_mask_map',
                           url='gsshaindex/get-mask-map/{file_id}',
                           controller='gsshaindex.controllers.main.get_mask_map'),
                    UrlMap(name='select_index',
                           url='gsshaindex/{job_id}/select-index',
                           controller='gsshaindex.controllers.main.select_index'),
                    UrlMap(name='get_index_maps',
                           url='gsshaindex/{job_id}/get-index-maps/{index_name}',
                           controller='gsshaindex.controllers.main.get_index_maps'),
                    UrlMap(name='edit_index',
                           url='gsshaindex/{job_id}/edit-index/{index_name}',
                           controller='gsshaindex.controllers.draw_index.edit_index'),
                    UrlMap(name='shapefile_index',
                           url='gsshaindex/{job_id}/shapefile-index/{index_name}/{shapefile_name}',
                           controller='gsshaindex.controllers.select_shapefile.shapefile_index'),
                    UrlMap(name='shapefile_upload',
                           url='gsshaindex/{job_id}/shapefile-upload/{index_name}',
                           controller='gsshaindex.controllers.select_shapefile.shapefile_upload'),
                    UrlMap(name='get_srid_from_wkt',
                           url='gsshaindex/get-srid-from-wkt',
                           controller='gsshaindex.controllers.select_shapefile.get_srid_from_wkt'),
                    UrlMap(name='show_overlay',
                           url='gsshaindex/{job_id}/show-overlay/{index_name}/{user}/{shapefile_name}',
                           controller='gsshaindex.controllers.select_shapefile.show_overlay'),
                    UrlMap(name='get_geojson_from_geoserver',
                           url='gsshaindex/get-geojson-from-geoserver/{user}/{shapefile_name}',
                           controller='gsshaindex.controllers.select_shapefile.get_geojson_from_geoserver'),
                    UrlMap(name='replace_index_with_shapefile',
                           url='gsshaindex/{job_id}/replace-index-with-shapefile/{index_name}/{shapefile_name}',
                           controller='gsshaindex.controllers.select_shapefile.replace_index_with_shapefile'),
                    UrlMap(name='combine_index',
                           url='gsshaindex/{job_id}/combine-index/{index_name}',
                           controller='gsshaindex.controllers.combine_index.combine_index'),
                    UrlMap(name='submit_edits',
                           url='gsshaindex/{job_id}/submit-edits/{index_name}',
                           controller='gsshaindex.controllers.draw_index.submit_edits'),
                    UrlMap(name='mapping_table',
                           url='gsshaindex/{job_id}/mapping-table/{index_name}/{mapping_table_number}',
                           controller='gsshaindex.controllers.index_desc_and_val.mapping_table'),
                    UrlMap(name='replace_values',
                           url='gsshaindex/{job_id}/replace-values/{index_name}/{mapping_table_number}',
                           controller='gsshaindex.controllers.index_desc_and_val.replace_values'),
                    UrlMap(name='submit_mapping_table',
                           url='gsshaindex/{job_id}/submit-mapping-table/{index_name}/{mapping_table_number}',
                           controller='gsshaindex.controllers.index_desc_and_val.submit_mapping_table'),
                    UrlMap(name='zip_file',
                           url='gsshaindex/{job_id}/zip-file',
                           controller='gsshaindex.controllers.main.zip_file'),
                    UrlMap(name='status',
                             url='gsshaindex/status',
                             controller='gsshaindex.controllers.main.status'),
                    UrlMap(name='in_progress',
                             url='gsshaindex/in-progress',
                             controller='gsshaindex.controllers.main.in_progress'),
                    # UrlMap(name='job_status',
                    #        url='gsshaindex/{job_id}/job-status',
                    #        controller='gsshaindex.controllers.job-status'),
                    UrlMap(name='fly',
                           url='gsshaindex/{job_id}/fly',
                           controller='gsshaindex.controllers.main.fly'),
                    UrlMap(name='delete',
                           url='gsshaindex/{job_id}/delete/{return_to}',
                           controller='gsshaindex.controllers.main.delete'),
                    UrlMap(name='results',
                           url='gsshaindex/{job_id}/results/{view_type}',
                           controller='gsshaindex.controllers.main.results'),
                    UrlMap(name='get_depth_map',
                           url='gsshaindex/{job_id}/get-depth-map/{view_type}',
                           controller='gsshaindex.controllers.main.get_depth_map'),
                    )

        return url_maps

    def persistent_stores(self):
        """
        Add persistent stores
        """
        stores = (PersistentStore(name='gsshaidx_db',
                                  initializer='init_stores:init_gsshaidx_db',
                                  spatial=True),
                  PersistentStore(name='gsshapy_db',
                                  initializer='gsshaindex.init_stores.init_gsshapy_db',
                                  spatial=True),
                  )

        return stores

    # def dataset_services(self):
    #     """
    #     Add one or more dataset services
    #     """
    #     dataset_services = (DatasetService(name='gsshaindex_ciwweb',
    #                                        type='ckan',
    #                                        endpoint='http://ciwckan.chpc.utah.edu/api/3/action',
    #                                        apikey='c9f477f0-118f-49f1-8d5a-b35757689c74'),
    #                         )
    #
    #     return dataset_services


    # def spatial_dataset_services(self):
    #     """
    #     Add one or more dataset services
    #     """
    #     spatial_dataset_services = (SpatialDatasetService(name='gsshaindex_geoserver',
    #                                                       type='geoserver',
    #                                                       endpoint='http://192.168.59.103:8181/geoserver/rest',
    #                                                       username='admin',
    #                                                       password='geoserver'),
    #                                 )
    #
    #     return spatial_dataset_services
