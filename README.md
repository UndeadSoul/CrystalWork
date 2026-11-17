# CrystalWork — Backend

Plataforma para registrar y gestionar cotizaciones, proyectos y clientes de una
fábrica de ventanas de aluminio. API en **Django 6 + DRF** (autenticación JWT).

El frontend (React) está en el repositorio `crystalworkfe`.

---

## Puesta en marcha en una máquina nueva

La base de datos **no** se versiona, así que en una máquina nueva arranca vacía.
Hay que instalar dependencias, aplicar migraciones y **cargar datos iniciales**;
sin datos de catálogo (precios y planchas de vidrio) no se pueden crear
cotizaciones.

### 1. Backend

```bash
cd CrystalWorkBe
python -m venv venv
# Windows:  venv\Scripts\activate     |  Linux/Mac:  source venv/bin/activate
pip install -r requirements.txt

# Configuración: crea tu .env a partir de la plantilla (el .env NO se versiona)
copy .env.example .env      # Windows   |   Linux/Mac:  cp .env.example .env
# genera una SECRET_KEY y pégala en el .env:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

python manage.py migrate
```

> En desarrollo, si no creas el `.env`, el proyecto funciona igual con una clave
> insegura de respaldo. Para producción el `.env` (con `SECRET_KEY` propia y
> `DEBUG=False`) es **obligatorio**.

### 2. Datos iniciales — elige UNA opción

**Opción A — Datos de demo (recomendada para empezar de cero)**

Crea una empresa demo, usuarios y el catálogo completo con precios y planchas.
Es idempotente (se puede correr varias veces) y no pisa valores ya editados:

```bash
python manage.py seed_demo
```

Usuarios que crea:

| Usuario    | Contraseña      | Rol                |
|------------|-----------------|--------------------|
| `admin`    | `admin12345`    | Administrador del sistema (superusuario) |
| `jefe`     | `jefe12345`     | Jefe               |
| `operario` | `operario12345` | Operario           |

> Cambia estas contraseñas antes de cualquier uso real.

**Opción B — Replicar los datos actuales de otra máquina**

En la máquina de origen se genera un respaldo (ya incluido como
`seed_data.json`, regenerable con el comando de abajo). En la máquina nueva,
sobre una base recién migrada:

```bash
python manage.py loaddata seed_data.json
```

Esto restaura empresa, usuarios (con sus contraseñas), clientes, catálogo,
cotizaciones y proyectos tal como estaban.

Para regenerar el respaldo en la máquina de origen (UTF‑8):

```bash
# Windows PowerShell:  $env:PYTHONUTF8=1
PYTHONUTF8=1 python manage.py dumpdata --indent 2 \
  -e contenttypes -e auth.permission -e admin.logentry -e sessions \
  -o seed_data.json
```

> Si ya abriste la app en la máquina nueva y se crearon datos sueltos, parte de
> una base limpia: borra `db.sqlite3`, corre `migrate` y recién ahí `loaddata`.

### 3. Levantar el servidor

```bash
python manage.py runserver   # http://127.0.0.1:8000
```

### 4. Frontend

```bash
cd ../crystalworkfe
npm install
npm run dev
```

El frontend apunta por defecto a `http://127.0.0.1:8000`. Si el backend corre en
otra dirección/puerto, crea `crystalworkfe/.env`:

```
VITE_API_URL=http://<host>:<puerto>
```

---

## Configuración por entorno (variables)

Las variables se definen en `CrystalWorkBe/.env` (lo carga `python-dotenv` al
iniciar) o en el panel del hosting. La plantilla versionada es
[.env.example](.env.example): cópiala a `.env` y completa los valores. El `.env`
**no** se versiona (está en `.gitignore`), así que cada equipo tiene el suyo.

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | **Obligatoria en producción.** Sin ella se usa una clave insegura de desarrollo. Generar: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`. |
| `DEBUG` | `False` en producción. |
| `ALLOWED_HOSTS` | Hosts permitidos, separados por coma. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | Cambian la base a PostgreSQL automáticamente. |
| `CSRF_TRUSTED_ORIGINS` | Orígenes confiables para el admin. |

---

## Comandos útiles

```bash
python manage.py createsuperuser        # crear un admin
python manage.py changepassword <user>  # resetear una contraseña
python manage.py seed_demo               # asegurar empresa/usuarios/catálogo demo
```
