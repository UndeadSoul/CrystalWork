from django.shortcuts import render, redirect

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
    # SE CAMBIÓ 'exportar.html' POR 'export.html'
    return render(request, 'export.html', {'ventanas': ventanas})