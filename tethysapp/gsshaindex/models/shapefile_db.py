from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, PickleType
from sqlalchemy.orm import sessionmaker

from datetime import datetime
import os, collections, ConfigParser

from ..utilities import get_persistent_store_engine

# Create DB shapefile_engine and sessionmaker for Shapefile DB
shapefile_engine = get_persistent_store_engine("shapefile_db")
shapefile_sessionmaker = sessionmaker(bind=shapefile_engine)
