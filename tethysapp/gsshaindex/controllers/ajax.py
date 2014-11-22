from ..model import Jobs, SessionMaker, jobs_sessionmaker
import tethysapp.gsshaindex.lib as gi_lib
from django.http import JsonResponse


def info_by_id(request, file_id):

    session = jobs_sessionmaker()
    user = str(request.user)
    job, success = gi_lib.get_job(file_id, user,session)

    return JsonResponse({"description":job.original_description, "name":job.original_name})