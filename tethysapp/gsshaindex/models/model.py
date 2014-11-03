from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, PickleType
from sqlalchemy.orm import sessionmaker

from datetime import datetime
import os, collections, ConfigParser

from ..utilities import get_persistent_store_engine

# DB Engine, sessionmaker, and base
engine = get_persistent_store_engine('primary')
SessionMaker = sessionmaker(bind=engine)
Base = declarative_base()

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

