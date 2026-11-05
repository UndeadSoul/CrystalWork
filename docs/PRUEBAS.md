# Pruebas — CrystalWork

> Qué pruebas tiene el proyecto, cómo correrlas, qué verifica cada una y qué falta cubrir.
> Complementa [ESTADO.md](ESTADO.md) y [VALIDACIONES.md](VALIDACIONES.md).
> Última actualización: **2026-11-05** — **71 tests, todos pasan** (~35 s).

## 1. Cómo correrlas

Desde `CrystalWork/`, con el entorno virtual activo (`..\venv\Scripts\activate` en Windows):

```bash
python manage.py test                          # todas
python manage.py test projects                 # una app
python manage.py test projects.tests.PagosTests                         # una clase
python manage.py test projects.tests.PagosTests.test_no_supera_el_saldo # un test
python manage.py test -v 2                     # muestra el nombre de cada test
python manage.py test --keepdb                 # reutiliza la base de pruebas (más rápido)
```

- Django crea una **base SQLite en memoria** y aplica **todas las migraciones** antes de correr. Así, las migraciones de saneamiento y las `CheckConstraint` también quedan probadas. No toca `db.sqlite3` ni los datos de ejemplo.
- Los tests no dependen de `seed_data.json` ni de `seed_demo`. Cada clase arma sus propios datos en `setUpTestData`. El catálogo base (series, perfiles, insumos) se crea con `asegurar_catalogo(empresa)`, como en una empresa nueva.
- Las pruebas usan `APITestCase` y llaman a la API real (`/api/...`) con `force_authenticate`. Así se prueban juntos los permisos, los serializers, las vistas y la base de datos. La excepción es `DesactivacionTests`, que inicia sesión con usuario y contraseña para probar el JWT.

## 2. Resumen

| Archivo | Clases | Tests | Qué cubre |
|---|---|---:|---|
| [users/tests.py](../users/tests.py) | 4 | 14 | Aislamiento entre empresas, admin sin datos operativos, permisos por rol, desactivación |
| [core/tests.py](../core/tests.py) | 2 | 15 | Concurrencia optimista en cotizaciones y en precios |
| [core/test_pricing.py](../core/test_pricing.py) | 5 | 25 | Cálculo de precios: costo por ventana, agregados por línea, datos faltantes, total de la cotización |
| [projects/tests.py](../projects/tests.py) | 2 | 14 | Pagos, cancelación de proyectos, exportación a PDF |
| [analytics/tests.py](../analytics/tests.py) | 2 | 3 | Fechas en hora local (Chile) y registro del último ingreso |
| `alerts/tests.py`, `api/tests.py` | — | 0 | Vacíos (plantilla de Django) |
| **Total** | **15** | **71** | |

Django busca los tests en los archivos `test*.py` de cada app, así que `tests.py` y `test_pricing.py` se ejecutan los dos.

## 3. Detalle por archivo

### 3.1 `users/tests.py` — aislamiento y permisos (14)

**Escenario común (`BaseEscenario`):** empresas **A** y **B**, cada una con su catálogo; el administrador del sistema (superusuario); `jefe.a`, `operario.a` y `jefe.b`. A tiene un cliente, una plancha, un precio por color, una cotización aprobada con una ventana, su proyecto y un registro de cambio. Todos los usuarios tienen la contraseña `CLAVE`.

`OPERATIVOS` es la lista de endpoints con datos de empresa: clientes, cotizaciones, proyectos, analytics y catálogo.

| Clase | Test | Verifica |
|---|---|---|
| `AdministradorSinDatosOperativosTests` | `test_no_accede_a_datos_operativos` | El admin recibe **403** en todas las listas de `OPERATIVOS` |
| | `test_no_accede_a_objetos_de_una_empresa` | 403 al ver el cliente, la cotización, el proyecto, la hoja de corte o el perfil de A, y al aprobar una cotización |
| | `test_si_gestiona_empresas_y_usuarios` | 200 en `/api/me/`, `/api/empresas/` y `/api/usuarios/` |
| `AislamientoEntreEmpresasTests` | `test_listas_no_muestran_datos_de_otra_empresa` | El jefe de B ve listas vacías y su propio catálogo, nunca el de A |
| | `test_objetos_de_otra_empresa_son_404` | 11 URLs de objetos de A responden **404**, no 403, para no revelar que existen |
| | `test_no_modifica_datos_de_otra_empresa` | Los PATCH/POST sobre datos de A dan 404 y la base no cambia (nombre, precio, usuario activo) |
| | `test_no_cotiza_con_cliente_de_otra_empresa` | Cotizar con un cliente de A da 400 en `cliente` |
| | `test_dashboard_solo_cuenta_su_empresa` | Los KPIs de B están en cero y son distintos de los de A |
| `PermisosPorRolTests` | `test_operario_sin_precios_finanzas_ni_usuarios` | El operario recibe 403 en catálogo, configuración, cambios, ingresos, usuarios y empresas, y al aprobar |
| | `test_operario_si_trabaja_con_su_empresa` | El operario ve clientes, cotizaciones y proyectos de su empresa |
| | `test_jefe_no_gestiona_empresas` | El jefe recibe 403 en `/api/empresas/` |
| | `test_jefe_solo_ve_sus_operarios` | `/api/usuarios/` muestra al jefe solo `operario.a`: ni a sí mismo ni a otros jefes |
| `DesactivacionTests` | `test_usuario_desactivado_no_inicia_sesion_ni_usa_sesion_abierta` | Login 401, y su token ya emitido deja de funcionar |
| | `test_empresa_desactivada_bloquea_a_sus_usuarios` | Login 401 con `code: empresa_inactiva`; el token abierto da 401; la otra empresa sigue funcionando |

### 3.2 `core/tests.py` — concurrencia (15)

Simula **dos jefes de la misma empresa**, cada uno con su propio `APIClient`, como si tuvieran dos navegadores abiertos. Ver [core/concurrencia.py](../core/concurrencia.py).

**`ConcurrenciaCotizacionTests`:** en `setUp`, el jefe 1 crea una cotización con una ventana (versión 1). Helpers: `editar`, `aprobar`, `rechazar`, `actual`, `hay_proyecto`.

| Test | Verifica |
|---|---|
| `test_editar_incrementa_version_y_registra_autor` | Editar sube la versión a 2 y registra `modificada_por` |
| `test_no_se_aprueba_una_version_que_no_se_vio` | Jefe 2 edita; jefe 1 aprueba con la versión 1 → **409** `conflicto_version` ("modificada por jefe2"), sin proyecto. Con la versión 2 sí aprueba |
| `test_no_se_edita_una_cotizacion_ya_aprobada` | Editar una aprobada → 409 ("aprobada por jefe1"); las ventanas no cambian |
| `test_aprobacion_durante_el_guardado_de_una_edicion` | Con `mock`, la aprobación llega *durante* el recálculo de la edición: la aprobación recibe 409 y la cotización queda Pendiente, en versión 2, sin proyecto. Es el caso que antes dejaba una cotización Pendiente con un proyecto creado |
| `test_no_se_resuelve_dos_veces` | Aprobar y luego rechazar la misma versión → 409; tampoco con la versión nueva |
| `test_sin_version_se_rechaza` | Aprobar sin `version` → 400 |
| `test_error_de_validacion_no_consume_la_version` | Una edición inválida (ancho 10) → 400; la versión y los datos no cambian |
| `test_recalcular_no_cambia_una_aprobada` | `recalcular` sobre una aprobada → 409 |

**`ConcurrenciaPreciosTests`:** cubre el catálogo (`ControlVersionMixin`).

| Test | Verifica |
|---|---|
| `test_no_se_pisa_un_valor_cambiado_por_otro_jefe` | Insumo: jefe 2 guarda con la versión vieja → 409, con `detail` ("jefe1 modificó este valor") y `actual` (valor vigente). El valor del jefe 1 se conserva |
| `test_filas_distintas_no_se_bloquean` | Dos jefes editan insumos distintos al mismo tiempo sin conflicto |
| `test_configuracion_general` | Margen y transporte de la empresa: la segunda escritura con la versión vieja → 409 |
| `test_perfil_y_serie` | Lo mismo para perfil de serie; la serie se versiona por separado |
| `test_error_de_validacion_no_consume_la_version` | Precio negativo → 400; la versión no cambia |
| `test_sin_version_se_rechaza` | PATCH sin `version` → 400 |
| `test_mensaje_de_conflicto_en_la_zona_del_usuario` | La hora del mensaje 409 sale en la zona de la cabecera `X-Zona-Horaria`. Se prueba con Santiago y Tokio (`subTest`) |

### 3.3 `core/test_pricing.py` — cálculo de precios (25)

Prueba [core/pricing.py](../core/pricing.py) con **totales esperados calculados a mano**. El escenario (`EscenarioPrecios`) carga un catálogo de valores redondos para que cada cifra se pueda verificar con lápiz. El docstring del archivo y las constantes `ALUMINIO`, `VIDRIO` y `AGREGADOS_L20/L25` muestran la cuenta paso a paso:

- **Aluminio:** L20 a $1.000 por metro de perfil y L25 a $2.000. El riel inferior simple pesa el doble ($2.000/m en L20), para distinguirlo del riel inferior estándar.
- **Vidrio:** plancha de 2 × 3 m a $60.000, es decir $10.000/m², con 20% de merma. Burlete a $100/m.
- **Agregados:** los pestillos y rodamientos de L25 tienen precios muy distintos a los de L20. Si una ventana usara el insumo de la otra línea, el total cambiaría mucho y el test fallaría.
- **Empresa:** margen 20%, transporte $1.000/km.
- **Ventana base:** 1000 × 1000 mm, Mate, Incoloro 4 mm. Su costo es **$24.455**: aluminio $9.836, vidrio $10.159 y agregados $4.460.

| Clase | Test | Verifica |
|---|---|---|
| `CostoVentanaTests` | `test_desglose_de_una_ventana` | Aluminio, vidrio, agregados y total de la ventana base. El total redondea la suma sin redondear, no la suma de los redondeos |
| | `test_cada_tipo_usa_su_serie_y_sus_perfiles` | Costo de Linea20lluvia, Linea20simple y Linea25lluvia: serie, descuentos de corte y perfil del riel |
| | `test_riel_simple_usa_el_perfil_riel_inferior_simple` | Subir el precio del riel inferior simple cambia solo los tipos "riel simple" |
| | `test_dimensiones_cambian_el_costo` | Una ventana más chica cuesta menos y una más grande cuesta más |
| | `test_iva` | 19% de IVA redondeado a peso, mitad hacia arriba; neto nulo → 0 |
| `AgregadosPorLineaTests` | `test_l20_cobra_sus_agregados` / `test_l25_cobra_sus_agregados` | Cada línea cobra sus agregados, en riel simple y en riel lluvia. Es la regresión del error en que L20 no cobraba agregados |
| | `test_cada_linea_usa_su_pestillo_y_rodamiento` | L20 usa `PESTILLO_L20`/`RODAMIENTO_L20` y L25 usa los suyos; el resto de los insumos es común |
| | `test_cambiar_un_insumo_de_una_linea_no_afecta_a_la_otra` | Cambiar el pestillo L25 no modifica el costo de una L20 |
| | `test_sin_linea_definida_no_hay_agregados` | Línea 42 (pendiente de definir) no tiene agregados |
| `DatosFaltantesTests` | `test_falta_precio_del_color` / `test_falta_peso_de_la_serie` / `test_falta_plancha_de_vidrio` / `test_falta_un_insumo` / `test_tipo_sin_serie` | Cada dato faltante lanza `PricingError` con un mensaje claro, sin inventar un precio. Un insumo faltante de una línea no bloquea a la otra |
| | `test_se_informan_todos_los_faltantes_juntos` | Si faltan varios datos, se informan todos a la vez |
| | `test_precio_en_cero_no_es_faltante` | Un precio en 0 se calcula como costo 0, no como dato faltante. La regla para el 0 se definirá con las alertas |
| `TotalCotizacionTests` (API) | `test_margen_y_cantidad` | Costo $24.455 + 20% = precio unitario $29.346; × 3 = $88.038 |
| | `test_total_con_transporte_monto_agregado_e_iva` | Neto = ventanas L20 y L25 + transporte (12,5 km × $1.000) + monto agregado. IVA y bruto correctos |
| | `test_transporte_con_decimales_se_redondea_a_peso` | 12,3 km × $999 = $12.287,7 se redondea a $12.288. La respuesta al guardar coincide con la cotización al volver a abrirla (ver nota) |
| | `test_sin_transporte_no_se_cobra_aunque_haya_distancia` | Sin transporte marcado, la distancia se ignora |
| | `test_ventana_sin_precio_no_suma_al_total` | Una ventana sin precio queda con `precio_calculado = False`, subtotal 0, y no suma al total |
| | `test_recalcular_toma_los_precios_actuales` | Después de cargar el precio que faltaba, `recalcular` actualiza la cotización |
| `PerfilesPorTipoTests` (sin base de datos) | `test_largos_linea20_lluvia` / `test_linea42_aun_no_tiene_cortes` | Largos y cantidades de corte que usa el cálculo de aluminio |

> **Error encontrado y corregido con estos tests:** cuando la distancia tenía decimales y el resultado daba centavos (12,3 km × $999), el total de la cotización quedaba con centavos en memoria. Al guardar, el total bruto mostrado era $1 menor que al volver a abrirla, porque la base de datos redondeaba recién al guardar. Ahora `Cotizacion.recalcular_total()` ([core/models.py](../core/models.py)) redondea el transporte a peso, mitad hacia arriba, igual que el resto del cálculo.
>
> **Verificación de los tests:** se introdujeron errores a propósito en `pricing.py` y en cada caso fallaron tests: L20 sin agregados (13), pestillo de la línea equivocada (12), sin el perfil de riel simple (2) y sin la merma del vidrio (9).

### 3.4 `projects/tests.py` — pagos, cancelación y PDF (14)

**Escenario común (`EscenarioProyecto`):** empresa Alfa con jefe y operario; empresa Beta con su jefe; un proyecto de **neto $100.000** (bruto **$119.000**). Helpers: `como(usuario)`, `pagar(monto, fecha, comentario)` y `anular(pago_id, motivo)`. Las dos clases heredan de esta base, así que sus tests no se repiten.

**`PagosTests`** (ver [projects/pagos.py](../projects/pagos.py)):

| Test | Verifica |
|---|---|
| `test_pagos_parciales_y_total` | $50.000 → `ABONADO`, saldo $69.000, queda registrado quién pagó; luego $69.000 → `PAGADO`, saldo 0 |
| `test_dos_personas_registran_pagos_sin_pisarse` | Jefe y operario registran pagos; el abonado es la suma |
| `test_no_supera_el_saldo` | No se puede pagar más que el saldo ("Supera el saldo pendiente ($19.000)"), ni pagar un proyecto ya pagado por completo |
| `test_validaciones` | Monto 0, negativo o decimal; fecha futura o anterior al mínimo; comentario con `<script>` → 400 en el campo. El abonado sigue en 0 |
| `test_anular_recalcula_y_queda_en_el_historial` | Anular recalcula el estado y el saldo y guarda quién anuló y por qué. Queda en el registro de cambios ("Pago registrado", "Pago anulado", "Pago") |
| `test_no_se_anula_dos_veces` | La segunda anulación → 409 ("ya fue anulado por jefe1") |
| `test_anular_requiere_motivo_y_ser_jefe` | Sin motivo → 400; el operario → 403 |
| `test_estado_de_pago_no_se_edita_directo` | Un PATCH de `estado_pago` o `monto_abonado` se ignora, porque se calculan a partir de los pagos |
| `test_otra_empresa_no_registra_pagos` | El jefe de otra empresa → 404 |

**`CancelacionYPdfTests`:**

| Test | Verifica |
|---|---|
| `test_cancelar_exige_motivo` | Cancelar sin motivo → 400; con motivo → 200, y el registro de cambios guarda "Cancelado: \<motivo\>" |
| `test_solo_el_jefe_cancela_y_reactiva` | El operario no cancela ni reactiva (403). Al reactivar se limpia el motivo |
| `test_cancelado_no_recibe_pagos_ni_cuenta_como_facturado` | Un proyecto cancelado no acepta pagos (400) y sale de "facturado" y "por cobrar" en el dashboard |
| `test_pdf_cotizacion_proyecto_y_hoja_de_corte` | Los 3 PDF responden 200, `application/pdf`, como descarga (`attachment`) y con contenido `%PDF`, en el caso más completo: con un pago y el proyecto cancelado |
| `test_pdf_respeta_permisos` | Otra empresa → 404; el admin → 403 |

> Los PDF se prueban solo en su generación (que no fallen y sean un PDF válido). El contenido y el diseño se revisaron a mano (sección 4).

### 3.5 `analytics/tests.py` — fechas (3)

| Clase | Test | Verifica |
|---|---|---|
| `IngresosEnHoraDeChileTests` (`SimpleTestCase`, sin base) | `test_proyecto_de_noche_se_cuenta_en_su_dia_y_mes_local` | Un proyecto del 31-10 a las 23:30 en Chile (01-11 a las 02:30 en UTC) se cuenta en **octubre**, no en noviembre |
| | `test_semana_usa_el_dia_local` | El mismo proyecto se cuenta el día 31/10 en la vista semanal |
| `UltimoIngresoTests` | `test_iniciar_sesion_registra_el_ultimo_ingreso` | Al iniciar sesión por `/api/token/` se guarda `last_login` (`UPDATE_LAST_LOGIN`) |

## 4. Verificaciones manuales

No están automatizadas. Se hicieron al implementar cada cambio y conviene repetirlas antes de entregar una versión.

| Qué | Cómo | Estado actual |
|---|---|---|
| **Build del frontend** | `npm run build` en `crystalworkfe/` | Compila |
| **Lint del frontend** | `npm run lint` (oxlint) | 8 avisos, todos anteriores a estos cambios. Un aviso nuevo indica una regresión |
| **Instalación desde cero** | Base vacía → `python manage.py migrate` → `loaddata seed_data.json` **o** `seed_demo` → iniciar sesión con los usuarios de la demo | Funciona |
| **PDF** | Generar los 3 PDF desde la app y revisarlos a ojo: columnas que no se cortan, unidades ("1188mm", "1200mm × 1200mm"), totales sin cortarse entre páginas, pie con la numeración | Revisados |
| **Concurrencia en la UI** | Dos navegadores con usuarios distintos: editar y aprobar la misma cotización, y editar la misma fila de precios → se ve el aviso de conflicto y se carga la versión actual | Probado contra la API; la pantalla no se ha probado en el navegador |
| **Zona horaria** | Cambiar la zona del sistema operativo y abrir la app → las horas se muestran en hora local, con el sufijo `(GMT±x)` si es distinta de la del servidor | Pendiente de probar en el navegador |
| **Pantallas** | Recorrer cotización → aprobación → proyecto → pagos → cancelación → PDF, con jefe y con operario | Pendiente de recorrer en el navegador después de los últimos cambios |

## 5. Qué falta cubrir

Ordenado por riesgo: lo primero, si falla, produce resultados incorrectos sin que nadie lo note.

1. **Hoja de corte** (`projects/cutlist.py`): faltan la separación por código de ventana (que no agrupe perfiles iguales de ventanas distintas), el orden de los perfiles y el uso del riel inferior simple. Los largos de corte de Linea20lluvia ya se prueban en `core/test_pricing.py`.
2. **Precios, casos pendientes:** Linea25simple con su descuento propio, ventanas en los extremos (300 y 3000 mm) y cambios de margen. El caso de los precios en 0 se definirá con las alertas.
3. **Validaciones** ([VALIDACIONES.md](VALIDACIONES.md)): solo los pagos tienen pruebas de validación. Faltan casos por campo (nombre, RUT único y su normalización, email, dirección, rangos 300–3000 mm, cantidad ≤ 10, monto agregado solo con comentario, transporte ≤ $50.000) y una prueba de que las `CheckConstraint` rechazan datos aunque no pasen por la API.
4. **Gestión de usuarios**: faltan crear, editar y desactivar desde la API; que el jefe no pueda asignar empresa ni rol; y la contraseña.
5. **Frontend**: no hay tests automatizados. Las funciones puras de `utils/` (`validacion.js`, `format.js`, `edicionBloque.js`, `errors.js`) se podrían probar con Vitest sin montar componentes.
6. **Postgres**: todo se prueba en SQLite. Antes del despliegue hay que correr la suite contra Postgres, porque los bloqueos con `UPDATE` y las restricciones pueden comportarse distinto.

## 6. Cómo agregar tests

- Ubicación: la app que contiene el código probado. Un tema grande va en su propio archivo `test_<tema>.py`, como `core/test_pricing.py`. Django los encuentra solo.
- Reutiliza los escenarios: hereda de `BaseEscenario` (users), `EscenarioProyecto` (projects) o `EscenarioPrecios` (precios) en vez de crear los datos de nuevo. Pon los tests en una **subclase** y no en la base, para que no se ejecuten dos veces.
- Arma los datos en `setUpTestData`, que se crean una vez por clase. Deja para `setUp` lo que cada test modifica.
- Usa `subTest` cuando recorras varios casos (URLs, valores inválidos), para que el fallo indique cuál fue.
- Prueba a través de la API (`/api/...`) y verifica también lo que quedó en la base (`refresh_from_db`). Así no basta con que la respuesta tenga el código correcto.
- Para fechas, usa `timezone.localdate()` (hora de Chile) o fija la fecha con `mock.patch`. No uses `date.today()` ni fechas UTC.
- Nombres en español, que describan la regla: `test_no_supera_el_saldo`, `test_solo_el_jefe_cancela_y_reactiva`.
- Al terminar, actualiza el total y las tablas de este documento.
