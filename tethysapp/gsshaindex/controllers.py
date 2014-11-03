from django.shortcuts import render


def home(request):
    """
    Controller for the app home page.
    """
    context = {}

    # Check to see if there's a models package
    # present = gi_lib.check_package('gssha-models')
    # print "The package was present? ",present



    return render(request, 'gsshaindex/home.html', context)

def secondpg(request,name):
    """
    Controller for the app home page.
    """
    context = {}

    context['name'] = name

    return render(request, 'gsshaindex/namepg.html', context)
