from ..model import Jobs, SessionMaker
import tethysapp.gsshaindex.lib as gi_lib


def info_by_id(request, id):

    job = gi_lib.get_job(id, request.user)

    description = job.

    description = "This is a fancy description"

    return {"description":description}