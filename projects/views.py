from django.shortcuts import render, redirect
from .windowstypes import calc_windtype_profiles

def interfaz_prueba(request):
    if 'ventanas' not in request.session:
        request.session['ventanas'] = []

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'agregar':
            nueva_ventana = {
                'alto': request.POST.get('alto'),
                'ancho': request.POST.get('ancho'),
                'tipo': request.POST.get('tipo'),
                'color': request.POST.get('color'),
                'perfiles': calc_windtype_profiles(request.POST.get('tipo'),request.POST.get('ancho'),request.POST.get('alto'))
            }
            request.session['ventanas'].append(nueva_ventana)
            request.session.modified = True

        elif accion == 'limpiar':
            request.session['ventanas'] = []
            request.session.modified = True

        return redirect('interfaz_prueba')

    # SE CAMBIÓ 'interfaz.html' POR 'interface.html'
    return render(request, 'interface.html', {'ventanas': request.session['ventanas']})

def pagina_exportar(request):
    ventanas = request.session.get('ventanas', [])
    return render(request, 'export.html', {'ventanas': ventanas})