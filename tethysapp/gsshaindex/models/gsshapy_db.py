from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, PickleType
from sqlalchemy.orm import sessionmaker

from datetime import datetime
import os, collections, ConfigParser

from ..utilities import get_persistent_store_engine

# Create DB gsshapy_engine and sessionmaker for Main DB
gsshapy_engine = get_persistent_store_engine("gsshapy_db")
gsshapy_sessionmaker = sessionmaker(bind=gsshapy_engine)
