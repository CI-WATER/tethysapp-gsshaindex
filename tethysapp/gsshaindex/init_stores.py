from .model import Base, Engine, gsshapy_engine
from gsshapy.orm import metadata as gsshapy_metadata

def init_gsshaidx_db(first_time):
    #Create tables
    Base.metadata.create_all(Engine)

def init_gsshapy_db(first_time):
    #Create tables
    gsshapy_metadata.create_all(gsshapy_engine)
