# Estado del proyecto — CrystalWork

> Documento vivo. Resume **qué es**, **cómo está**, **por qué se decidió cada cosa**
> y **qué falta**, para poder retomar el trabajo desde cualquier equipo.
> Última actualización: **2026-10-21**.

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

- **Administrador del sistema** (superusuario, sin empresa): crea empresas y jefes. (Fase 6, UI pendiente.)
- **Jefe**: gestiona su empresa, crea trabajadores, aprueba cotizaciones, edita precios, ve finanzas.
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
| 6 | **Multi-empresa / SaaS** (panel admin para crear empresas y jefes) | ⏳ Pendiente (siguiente) |

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
  - Largos en **mm**; cada ventana lleva un código = iniciales del cliente + nº de ventana (ej. `CLA1`).
- **Vidrio** ([core/pricing.py](../core/pricing.py) `_costo_vidrio`): **igual para los 4 tipos** (no depende del tipo). Por hoja: ancho `ancho/2 − 0.054`, alto `alto − 0.107`; `m² = anchoV × altoV × 2`; costo `= m² × (precioPlancha/áreaPlancha) × 1.20` (merma). Burlete = `(ancho×2 + alto×4) × precioPaquete/cantidadPaquete`.
- **IVA 19%:** el `total` almacenado es **NETO**; `iva` y `total_bruto` se calculan
  (`desglose_iva`). En **dashboard, listas y clientes** se muestra **bruto**; en los
  **detalles** se ve el desglose neto/IVA/bruto.
- **Pago parcial:** `Proyecto.monto_abonado`; "Por cobrar" = Σ `max(bruto − abonado, 0)` de los no pagados.
- **Control de cambios (auditoría)** ([core/models.py](../core/models.py) `CambioRegistro`, [core/audit.py](../core/audit.py)):
  registra cambios de estado de proyecto (fabricación/pago), `monto_abonado` y
  valores de precios (quién, cuándo, antes→después). Se ven en modales (ProyectoDetalle y Precios).

## 6. Seguridad — cómo está y qué falta

**Implementado:**
- Auth JWT (access 30 min / refresh 1 día). Permiso por defecto `IsAuthenticated`; `IsJefeOrAdmin` en precios/finanzas.
- **Aislamiento por empresa** en todos los `get_queryset` (`EmpresaScopedViewSet.filtrar_por_empresa`, `_HijoDeEmpresaViewSet`, etc.). Objetos de otra empresa → 404.
- Integridad de serializers: `read_only_fields` + asignación de `empresa`/`empleado`/totales en el servidor; dinero solo en `pricing.py`.
- Validación: RUT (módulo 11), dimensiones 300–2500 mm, longitudes; `EXCEPTION_HANDLER` (IntegrityError→400). ORM parametrizado (sin SQL crudo). React escapa (sin `dangerouslySetInnerHTML`).

**Pendiente de endurecer (antes de producción):**
- `SECRET_KEY` sin fallback inseguro; `DEBUG=False`; `ALLOWED_HOSTS` sin `*`; **CORS** cerrado a dominios propios (hoy `CORS_ALLOW_ALL_ORIGINS=True`).
- **Rotación/blacklist** de refresh tokens y **throttling** (fuerza bruta en login).
- Tokens en `localStorage` (riesgo XSS) — evaluar cookies httpOnly.
- HTTPS/HSTS y cookies seguras.
- **Tests automatizados** (no hay): prioridad tenant/permiso, pricing, serializers. `tests.py` vacíos.

## 7. Próximos pasos sugeridos

1. **Fase 6 — Multi-empresa:** panel del admin del sistema (crear empresa + jefe; onboarding usa `asegurar_catalogo`), gestión/activación de empresas, probar aislamiento con ≥2 empresas.
2. **Alertas** (app `alerts`): avisos de pendientes/pagos/proyectos atrasados.
3. **Endurecer seguridad** (sección 6) por variables de entorno.
4. **Línea 42:** definir perfiles/cortes para habilitarla.
5. **Tests** y despliegue con Postgres.

## 8. Convenciones

- Rama de trabajo `development` en ambos repos. Empezar con `git pull`, terminar con `git push`.
- La BD es local a cada equipo; para reproducir datos: `seed_demo` (demo) o `loaddata seed_data.json`.
- Frontend: `oxlint` limpio y `npm run build` OK antes de commitear. Backend: `python manage.py check` limpio.
- Dumps de datos: generar con `PYTHONUTF8=1` (evita cp1252 en Windows).
