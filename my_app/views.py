from django.shortcuts import render

# Create your views here.
def form_view(request):
	"""Render the form page."""
	return render(request, 'form.html')

