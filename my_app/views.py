from django.shortcuts import render
from .neighborhood_recommender import recommend_neighborhoods_from_answers

def home_view(request):
    return render(request, 'paginaboto.html')

def form_view(request):
    return render(request, 'html_complet.html')

def result_view(request):
    if request.method == "POST":
        answers = {
            "income": request.POST.get("renda_mediana"),
            "density": request.POST.get("densitat_poblacio"),
            "age": request.POST.get("edat_mediana"),
            "gastronomy": request.POST.get("oferta_gastronomica"),
            "green": request.POST.get("zones_verdes"),
            "culture": request.POST.get("oferta_cultural"),
            "pt_access": request.POST.get("transport_public"),
            "bus_availability": request.POST.get("metro_bus"),
            "bike_lanes": request.POST.get("carrils_bici"),
            "walkability": request.POST.get("caminabilitat"),
            "safety": request.POST.get("seguretat_requerida"),
            "main_priority": request.POST.get("prioritat"),
        }

        recs = recommend_neighborhoods_from_answers(answers, top_n=5)
        # Convertim a diccionaris per passar-ho fàcilment al template
        context = {"recs": recs.to_dict(orient="records")}
        return render(request, "pantalla_final.html", context)

    # Si algú entra per GET, simplement mostra una pàgina buida o redirigeix:
    return render(request, "pantalla_final.html", {"recs": []})
