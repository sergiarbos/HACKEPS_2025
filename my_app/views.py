from django.shortcuts import render

def home_view(request):
    return render(request, 'paginaboto.html')

def form_view(request):
    return render(request, 'html_complet.html')

def result_view(request):
    return render(request, 'pantalla_final.html')
