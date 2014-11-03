from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, PickleType
from sqlalchemy.orm import sessionmaker

from datetime import datetime
import os, collections, ConfigParser

from ..utilities import get_persistent_store_engine
# Create DB Engine, SessionMaker, and Base for jobs DB
Engine = get_persistent_store_engine("gsshaidx_db")
jobs_sessionmaker = sessionmaker(bind=Engine)
Base = declarative_base()


class Jobs(Base):
    '''
    ORM for storing job data
    '''
    __tablename__ = 'job_scenarios'

    #Columns
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created = Column(DateTime)
    user_id = Column(String)
    original_model = Column(PickleType)
    new_model = Column(PickleType)
    current_kmls = Column(String)
    percentage = Column(Integer)
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

    def __init__(self, name, user_id, original_model):

        #Set default values
        self.name = name
        self.created = datetime.now()
        self.user_id = user_id
        self.original_model = original_model
        self.percentage = 0
        self.new_model = {}
        self.run_urls = {}
        self.result_urls = {}
        self.status = "pending"

    def __repr__(self):
        return "Id: ('%s'), name: ('%s'), user_id: ('%s'), status: ('%s'), original model: ('%s'), new model: ('%s'), percentage: ('%s'),current kmls: ('%s'), run urls: ('%s'), run date: ('%s'), new name ('%s'), result urls ('%s')" % (self.id, self.name, self.user_id, self.status, self.original_model, self.new_model, self.percentage,self.current_kmls, self.run_urls, self.run_date, self.new_name, self.result_urls)