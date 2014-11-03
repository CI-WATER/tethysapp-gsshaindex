
from gsshapy.orm import metadata as gsshapy_metadata


def init_primary(first_time):
    """
    An example persistent store initializer function
    """
    from models.model import engine, SessionMaker, StreamGage, Base

    # Create tables
    Base.metadata.create_all(engine)

    # First time add data
    if first_time:
        # Make a session
        session = SessionMaker()

        # Create StreamGage objects
        provo = StreamGage(name='Provo River Near Provo', lat=40.23833, lon=-111.6975)
        woodland = StreamGage(name='Lower River Near Woodland', lat=40.557778, lon=-111.181111)

        # Add to the session and commit
        session.add(provo)
        session.add(woodland)
        session.commit()


def init_gsshaidx_db(first_time):
    from .models.jobs import Engine, Base
    #Create tables
    Base.metadata.create_all(Engine)


def init_gsshapy_db(first_time):
    from models.gsshapy_db import gsshapy_engine
    #Create tables
    gsshapy_metadata.create_all(gsshapy_engine)


def init_shapefile_db(first_time):
    from models.shapefile_db import shapefile_engine
    #Create tables
    gsshapy_metadata.create_all(shapefile_engine)