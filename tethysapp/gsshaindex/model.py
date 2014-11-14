from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, PickleType
from sqlalchemy.orm import sessionmaker

from datetime import datetime
import os, collections, ConfigParser

from .utilities import get_persistent_store_engine

# DB Engine, sessionmaker, and base
engine = get_persistent_store_engine('primary')
SessionMaker = sessionmaker(bind=engine)
Base = declarative_base()

# Create DB Engine, SessionMaker, and Base for jobs DB
Engine = get_persistent_store_engine("gsshaidx_db")
jobs_sessionmaker = sessionmaker(bind=Engine)
Base = declarative_base()

# Create DB gsshapy_engine and sessionmaker for Main DB
gsshapy_engine = get_persistent_store_engine("gsshapy_db")
gsshapy_sessionmaker = sessionmaker(bind=gsshapy_engine)

# Create DB shapefile_engine and sessionmaker for Shapefile DB
shapefile_engine = get_persistent_store_engine("shapefile_db")
shapefile_sessionmaker = sessionmaker(bind=shapefile_engine)

class StreamGage(Base):
    """
    Example SQLAlchemy model
    """
    __tablename__ = 'stream_gages'

    # Columns
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lat = Column(Float)
    lon = Column(Float)


class Jobs(Base):
    '''
    ORM for storing job data
    '''
    __tablename__ = 'job_scenarios'

    #Columns
    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    original_name = Column(String)
    original_id = Column(String)
    original_url = Column(String)
    original_description = Column(String)
    original_certification = Column(String)
    created = Column(DateTime)

    kml_url = Column(String)
    #Maybe won't need original model
    original_model = Column(PickleType)

    new_model = Column(PickleType)
    current_kmls = Column(String)
    run_urls = Column(PickleType)
    run_date = Column(DateTime)
    result_urls = Column(PickleType)
    new_name = Column(String)
    status = Column(String)
    old_max = Column(String)
    old_time = Column(String)
    new_max = Column(String)
    new_time = Column(String)
    both_max = Column(String)
    both_time = Column(String)

    def __init__(self, name, user_id, original_description, original_id, original_url, original_certification):

        #Set default values
        self.original_name = name
        self.created = datetime.now()
        self.user_id = user_id
        self.original_id = original_id
        self.original_description = original_description
        self.original_url = original_url
        self.original_certification = original_certification
        self.original_model = {}
        self.new_model = {}
        self.run_urls = {}
        self.result_urls = {}
        self.status = "pending"

    def __repr__(self):
        return "Id: ('%s'), name: ('%s'), user_id: ('%s'), status: ('%s'), kml_url: ('%s'), original model: ('%s'), new model: ('%s'), current kmls: ('%s'), run urls: ('%s'), run date: ('%s'), new name ('%s'), result urls ('%s')" % (self.id, self.name, self.user_id, self.status, self,kml_url, self.original_model, self.new_model, self.current_kmls, self.run_urls, self.run_date, self.new_name, self.result_urls)