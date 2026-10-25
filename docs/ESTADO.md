# Estado del proyecto — CrystalWork

> Documento vivo. Resume **qué es**, **cómo está**, **por qué se decidió cada cosa**
> y **qué falta**, para poder retomar el trabajo desde cualquier equipo.
> Última actualización: **2026-10-23**.

## 1. Qué es

Plataforma para una fábrica de ventanas de aluminio: registrar/gestionar
**clientes**, **cotizaciones**, **proyectos** (cotizaciones aprobadas) e
**histórico**, calcular precios de ventanas y generar la **hoja de corte**.
Pensado **tenant-aware** (todo cuelga de `Empresa`) para crecer a SaaS multi-empresa.

- Moneda CLP (sin decimales). UI en español. Medidas de ventana en **mm**.

## 2. Arquitectura y repos

- **Backend:** Django 6 + DRF + SimpleJWT. Repo `UndeadSoul/CrystalWork` (carpeta `CrystalWorkBe`). Rama de trabajo: `development`.
- **Frontend:** React 19 + Vite + react-router. Repo `UndeadSoul/crystalworkfe`. Rama `development`.
- **Apps Django:** `core` (clientes, cotizaciones, catálogo, auditoría), `projects` (proyecto + hoja de corte), `users` (Empresa + Usuario), `analytics` (dashboard), `api` (`/api/me/`), `alerts` (vacía, futuro).
- **BD:** SQLite en dev; Postgres por variables `POSTGRES_*`. La BD **no** se versiona.

Puesta en marcha: ver [README.md](../README.md). Resumen: `migrate` → `seed_demo`
(o `loaddata seed_data.json`) → `runserver`; frontend `npm install` → `npm run dev`.

## 3. Roles

- **Administrador del sistema** (superusuario, sin empresa): gestiona empresas (`/empresas`) y usuarios de todas ellas (`/usuarios`). **No ve datos operativos** de las empresas (decisión de privacidad SaaS); al ingresar va a `/empresas`.
- **Jefe**: gestiona su empresa y a **sus operarios** (`/usuarios`), aprueba cotizaciones, edita precios, ve finanzas.
- **Operario**: crea cotizaciones y gestiona clientes. **No** ve finanzas.

## 4. Estado por fases

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Cimientos (auth, modelos base, layout) | ✅ |
| 1 | Clientes | ✅ |
| 2 | Cotizaciones (núcleo) + precios (backend + UI jefe) | ✅ |
| 3 | Aprobación del jefe → Proyecto | ✅ |
| 4 | Producción / hoja de corte | ✅ |
| 5 | Analítica / Dashboard | ✅ |
| 6 | **Multi-empresa / SaaS** (gestión de empresas y usuarios, aislamiento) | ✅ |

## 5. Decisiones clave de dominio

- **Precio de ventana = Aluminio + Vidrio + Agregados**, sobre el costo se aplica
  **margen configurable** por empresa. Precios en catálogo editable; cantidades y
  fórmulas en código ([core/pricing.py](../core/pricing.py)).
- **Series de aluminio L20 y L25** son distintas. Los perfiles se venden por
  paquete; el costo de cada perfil = `precio_paquete × (peso_perfil / peso_paquete)`
  y luego por regla de 3 según el largo usado.
- **Tipos de ventana (corredera):** L20 Riel Simple, L20 Riel Lluvia, L25 Riel
  Simple, L25 Riel Lluvia. Simple/Lluvia usan distinto **riel inferior**
  (override en pricing). Línea 42 (Fijo/Proyección) **pendiente** de definir cortes.
- **Hoja de corte** ([projects/windowstypes.py](../projects/windowstypes.py), [projects/cutlist.py](../projects/cutlist.py)):
  - Jamba: **sin descuento**, largo = alto de la ventana (×2).
  - Batiente y Traslapo: `alto − offset` (L20 simple 0.027 / L20 lluvia 0.035 / L25 simple 0.035 / L25 lluvia 0.045).
  - Riel sup/inf: `ancho − riel` (L20 0.012 / L25 0.016). Zócalo = Cabezal = `ancho/2`.
  - Largos en **mm**; cada ventana **física** lleva un código = iniciales del cliente + nº correlativo
    (ej. `CLA1`): una línea con cantidad 3 genera `CLA1`, `CLA2`, `CLA3`, cada una con sus piezas
    (no se agrupan cortes de ventanas distintas).
- **Vidrio** ([core/pricing.py](../core/pricing.py) `_costo_vidrio`): **igual para los 4 tipos** (no depende del tipo). Por hoja: ancho `ancho/2 − 0.054`, alto `alto − 0.107`; `m² = anchoV × altoV × 2`; costo `= m² × (precioPlancha/áreaPlancha) × 1.20` (merma). Burlete = `(ancho×2 + alto×4) × precioPaquete/cantidadPaquete`.
- **Agregados** ([core/pricing.py](../core/pricing.py) `agregados_usados`): mismas cantidades para las 4 correderas,
  pero **pestillos y rodamientos dependen de la línea**: insumos `PESTILLO_L20/L25` y
  `RODAMIENTO_L20/L25`, elegidos por la serie del tipo (`SERIE_POR_TIPO`). Se configuran
  en Precios → Insumos. (Migración `core.0010`: el insumo antiguo pasó a L20 y L25 se creó con sus mismos valores.)
- **Fechas** (zona `America/Santiago` = `TIME_ZONE`, `USE_TZ=True`):
  - Las fechas con hora (creación, ingreso, resolución, modificación, cambios, último ingreso) las pone **el
    servidor** (`auto_now_add` / `timezone.now()`) y se guardan en **UTC**.
  - Para agrupar o comparar por día/mes se convierten a hora de Chile (`timezone.localtime(...).date()`,
    `timezone.localdate()`); nunca `.date()` directo ni `date.today()` (darían el día UTC o el del sistema operativo).
  - El frontend las muestra con **fecha y hora en la zona del computador del usuario** (`formatFechaHora`): el ISO
    trae el desfase, así que la conversión es exacta. Si la zona local difiere de la del servidor (`/api/me/`
    → `zona_horaria_servidor`) se indica el desfase, p. ej. "00:15 (GMT+2)".
  - Los textos con hora que arma el servidor (mensajes de conflicto) usan la zona del navegador, que viaja en la
    cabecera `X-Zona-Horaria` ([core/zona.py](../core/zona.py)); las reglas de negocio siguen en la zona del servidor.
  - Pagos: se muestra la fecha del pago (sin hora, sin convertir) y cuándo se registró (hora del servidor).
  - La única fecha que elige el usuario es la del **pago** (`DateField`, sin hora): el rango válido (hoy y mínimo)
    lo entrega el servidor (`fecha_hoy`, `fecha_min_pago`).
  - El último ingreso se registra al iniciar sesión (`SIMPLE_JWT.UPDATE_LAST_LOGIN`).
- **IVA 19%:** el `total` almacenado es **NETO**; `iva` y `total_bruto` se calculan
  (`desglose_iva`). En **dashboard, listas y clientes** se muestra **bruto**; en los
  **detalles** se ve el desglose neto/IVA/bruto.
- **Proyecto cancelado** (`EstadoProduccion.CANCELADO`): se abandonó el proyecto. Exige `motivo_cancelacion`
  (queda en el control de cambios); **solo el jefe** cancela o reactiva. No recibe pagos nuevos y queda fuera de
  facturado, por cobrar, ingresos y ventanas fabricadas del dashboard. Reactivar = elegir otro estado (limpia el motivo).
- **Exportación a PDF** (ReportLab, en el servidor): cotización (`/api/cotizaciones/<id>/pdf/`), proyecto completo
  (`/api/proyectos/<id>/pdf/`) y solo hoja de corte (`/api/proyectos/<id>/hoja-corte/pdf/`, con columna "Listo" para
  el taller). Mismos permisos/aislamiento que la API; horas en la zona del usuario. Código: [core/pdf.py](../core/pdf.py),
  [projects/pdf.py](../projects/pdf.py). **Requiere `pip install -r requirements.txt`** (dependencia `reportlab`).
- **Pagos (abonos)** ([projects/pagos.py](../projects/pagos.py)): cada pago es un registro (`Pago`: monto, fecha,
  comentario, quién). `monto_abonado` = suma de pagos vigentes y `estado_pago` se **deriva** (0 Pendiente, parcial
  Abonado, total Pagado); no se editan a mano. Un pago no supera el saldo y **no se borra: se anula** (solo el jefe,
  con motivo; queda en el historial y en el control de cambios). Registrar/anular bloquea el proyecto (UPDATE de
  `version`) para que pagos simultáneos no superen el total. Los abonos anteriores se convirtieron en pagos
  (`projects.0007`). "Por cobrar" = Σ `max(bruto − abonado, 0)` de los no pagados.
- **Control de cambios (auditoría)** ([core/models.py](../core/models.py) `CambioRegistro`, [core/audit.py](../core/audit.py)):
  registra cambios de estado de proyecto (fabricación/pago), `monto_abonado` y
  valores de precios (quién, cuándo, antes→después). Se ven en modales (ProyectoDetalle y Precios).

## 6. Seguridad — cómo está y qué falta

**Implementado:**
- Auth JWT (access 30 min / refresh 1 día) con `users.auth.JWTEmpresaActivaAuthentication`: usuario desactivado o empresa
  desactivada → 401 también en sesiones abiertas (login devuelve `code: empresa_inactiva`).
- **Permisos** ([core/permissions.py](../core/permissions.py)): por defecto `EsUsuarioDeEmpresa` (jefe u operario);
  `EsJefe` en precios, finanzas y aprobar. **El administrador del sistema no accede a datos operativos** (clientes,
  cotizaciones, proyectos, precios, dashboard → 403): solo `/api/me/`, `/api/empresas/` y `/api/usuarios/`, que
  declaran sus permisos explícitamente. Un endpoint nuevo queda cerrado al admin salvo que se abra a propósito.
- **Gestión de usuarios** (`users/views.py`, `/api/usuarios/`, `/api/empresas/`): el jefe solo ve/gestiona operarios de su
  empresa (rol y empresa los fija el servidor); el admin gestiona todos menos superusuarios. No hay borrado: acciones
  `activar`/`desactivar` (conserva historial) y `clave` (la define el jefe/admin; validadores de Django). La empresa de
  un usuario no cambia tras crearlo. Crear empresa ejecuta `asegurar_catalogo`. No hay "Mi perfil" (decisión).
- **Aislamiento por empresa** en todos los `get_queryset` (`EmpresaScopedViewSet.filtrar_por_empresa`, `_HijoDeEmpresaViewSet`, etc.). Objetos de otra empresa → 404.
- Integridad de serializers: `read_only_fields` + asignación de `empresa`/`empleado`/totales en el servidor; dinero solo en `pricing.py`.
- **Validación en 3 capas** (frontend, backend y BD). Detalle campo por campo en
  [VALIDACIONES.md](VALIDACIONES.md). Reglas y límites en
  [core/validacion.py](../core/validacion.py), con espejo en `crystalworkfe/src/utils/validacion.js`
  (si se cambia una, cambiar la otra). Backend: validators del modelo + `MENSAJES_DRF`; BD:
  `CheckConstraint`/`UniqueConstraint` (migr. `core.0012`; `0011` ajustó los datos de ejemplo).
  En SQLite los caracteres permitidos se validan solo en frontend/backend (la BD controla largos y rangos).
  - Cliente: nombre 5–50 (letras con tildes/ñ y espacios); RUT obligatorio, módulo 11, guardado
    `12.345.678-9`, único por empresa; email con caracteres de correo; dirección opcional 5–100
    (letras, números, espacio y `. , # ° / -`).
  - Cotización: dirección de entrega igual a dirección; distancia 0,1–500 km (1 decimal), obligatoria
    solo con transporte; comentarios ≤1000 (letras, números y `. , : ¿ ? ¡ ! ( ) ° # $ % + / -`);
    monto agregado entero 0–10.000.000 y solo con comentario; 1–50 ventanas.
  - Ventana: ancho/alto **300–3000 mm**; cantidad 1–10; tipo con serie configurada y vidrio con
    plancha configurada; tipo/color/vidrio dentro de sus opciones (CHECK).
  - Cliente teléfono: opcional; dígitos, espacios y `+` inicial; 8–12 dígitos.
  - Proyecto: estados libres (se puede retroceder). Pago Pendiente → abono 0; Abonado → abono > 0 y
    ≤ total bruto, **si lo alcanza pasa solo a Pagado** (serializer). En la UI, al elegir "Abonado"
    se pide el monto y se guardan juntos.
  - Catálogo (**0 = sin configurar**, se avisará en Alertas): precios 0–10.000.000; margen 0–200 %
    (2 dec.); transporte 0–50.000 CLP/km; peso serie 0 ó 0,1–100 kg; peso perfil 0 ó 0,001–100 kg y
    ≤ peso de su serie (y la serie ≥ su perfil más pesado); largo tira 1–7 m (estándar 6 m, default
    de `asegurar_catalogo`); plancha 0,5–4 m; cantidad por paquete > 0. Migraciones `core.0013/0014`,
    `users.0003`, `projects.0004/0005`.
- **Errores y carga (frontend):** errores de la API normalizados (`utils/errors.js`) y mostrados con
  `FieldError` (bajo el campo) / `FormError` (general); `EXCEPTION_HANDLER` devuelve siempre
  `{campo: [...]}` o `{detail}`. Carga: barra global por peticiones axios (`BarraCarga`), `Loader` y `BotonCarga`.
- ORM parametrizado (sin SQL crudo). React escapa (sin `dangerouslySetInnerHTML`).

**Pendiente de endurecer (antes de producción):**
- `SECRET_KEY` sin fallback inseguro; `DEBUG=False`; `ALLOWED_HOSTS` sin `*`; **CORS** cerrado a dominios propios (hoy `CORS_ALLOW_ALL_ORIGINS=True`).
- **Rotación/blacklist** de refresh tokens y **throttling** (fuerza bruta en login).
- Tokens en `localStorage` (riesgo XSS) — evaluar cookies httpOnly.
- HTTPS/HSTS y cookies seguras.
- **Concurrencia en cotizaciones** ([core/concurrencia.py](../core/concurrencia.py)): control de versiones optimista.
  `Cotizacion.version` + `modificada_por/en`. Editar, aprobar, rechazar y recalcular exigen la `version` que el
  usuario tenía en pantalla y la toman con un `UPDATE` condicional atómico (versión + estado Pendiente). Si otro
  usuario la cambió → **409** `code: conflicto_version` con quién y cuándo. Todo dentro de `transaction.atomic`.
  Evita aprobar una versión no vista y el caso simultáneo que dejaba la cotización Pendiente con un proyecto
  creado. En la UI: el detalle recarga la versión actual al recibir 409; el formulario de edición ofrece
  "Cargar versión actual" o "Ver cotización". `recalcular` ya no cambia cotizaciones aprobadas.
- **Concurrencia en Precios:** cada fila del catálogo (serie, perfil, precio por color, plancha, insumo) y la
  configuración general tienen `version` (`ControlVersionMixin`). La edición en bloque envía **solo las filas
  modificadas** con su versión (`crystalworkfe/src/utils/edicionBloque.js`); si otra persona cambió una fila → 409:
  se muestra su valor vigente con quién/cuándo (del registro de cambios) y se conserva lo escrito en las demás.
- Clientes: el último que guarda gana (decisión: no se controla).
- **Tests automatizados** (`python manage.py test`, 37): [users/tests.py](../users/tests.py) (aislamiento entre 2
  empresas, admin sin datos operativos, permisos por rol, desactivación), [core/tests.py](../core/tests.py)
  (concurrencia en cotizaciones y precios) y [projects/tests.py](../projects/tests.py) (pagos). Faltan: pricing,
  hoja de corte, validaciones.

## 7. Próximos pasos sugeridos

1. **Panel del administrador** (opcional): métricas de uso por empresa (activas, usuarios, nº de cotizaciones) sin exponer detalle.
2. **Alertas** (app `alerts`): avisos de pendientes/pagos/proyectos atrasados.
3. **Endurecer seguridad** (sección 6) por variables de entorno.
4. **Línea 42:** definir perfiles/cortes para habilitarla.
5. **Tests** y despliegue con Postgres.

## 8. Convenciones

- Rama de trabajo `development` en ambos repos. Empezar con `git pull` (y `pip install -r requirements.txt` +
  `python manage.py migrate` si cambiaron), terminar con `git push`.
- La BD es local a cada equipo; para reproducir datos: `seed_demo` (demo) o `loaddata seed_data.json`.
- Frontend: `oxlint` limpio y `npm run build` OK antes de commitear. Backend: `python manage.py check` limpio.
- Dumps de datos: generar con `PYTHONUTF8=1` (evita cp1252 en Windows).
