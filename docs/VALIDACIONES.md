# Validaciones de campos — CrystalWork

> Referencia de las restricciones de cada campo editable: qué se permite, dónde
> se valida y cómo cambiar una regla. Complementa [ESTADO.md](ESTADO.md).
> Última actualización: **2026-10-24**.

## 1. Cómo funciona

Cada campo se valida en **tres capas**, con las mismas reglas:

| Capa | Dónde | Qué hace |
|---|---|---|
| **Frontend** | `crystalworkfe/src/utils/validacion.js` | Quita al escribir los caracteres no permitidos (avisa *"No se permite: …"* bajo el campo) y valida largo, rango y obligatoriedad al guardar. Los inputs de enteros bloquean `e + - . ,`. |
| **Backend** | [core/validacion.py](../core/validacion.py) (límites, regex, validators) + serializers | Los validators están en los modelos; DRF los aplica. `MENSAJES_DRF` reemplaza los mensajes genéricos de DRF para mantener un formato común. Las reglas entre campos están en los `validate()` de los serializers. |
| **Base de datos** | `Meta.constraints` de cada modelo | `CheckConstraint` (largos, rangos, opciones válidas, reglas entre campos) y `UniqueConstraint`. Bloquean datos inválidos aunque se salte la API. |

Además:

- **Normalización:** el backend quita espacios repetidos y en los extremos en nombres, direcciones y teléfonos. El RUT se guarda siempre como `12.345.678-9`, para que la unicidad no dependa de cómo se escribió.
- **Ejemplos de formato:** cada campo de escritura muestra un ejemplo (placeholder) tomado de `EJEMPLOS` y de
  `REGLAS[...].ejemplo` en `validacion.js`. Cada ejemplo cumple su propia regla: copiarlo nunca da error.
- **Formato de errores:** la API responde `{campo: ["mensaje"]}` o `{detail: "mensaje"}` ([core/exceptions.py](../core/exceptions.py)). El frontend muestra el error bajo su campo (`FieldError`) o como error general (`FormError`).
- **Limitación de SQLite:** no hace cumplir `max_length` ni permite regex en un `CHECK`. Por eso los largos se controlan con `CHECK` (`campo__length`), y los **caracteres permitidos se validan solo en frontend y backend**. En Postgres se podrían agregar `CHECK` con regex.
- La seguridad no depende de estas listas: el ORM parametriza las consultas (no hay inyección SQL) y React escapa el HTML. Las listas de caracteres permitidos son una capa adicional.

## 2. Conjuntos de caracteres

`Letras` = `A-Z a-z Á É Í Ó Ú Ü Ñ á é í ó ú ü ñ`.

| Conjunto | Permitido | Se usa en |
|---|---|---|
| Nombre de persona | Letras y espacio | Nombre de cliente, nombre y apellido de usuario |
| Dirección | Letras, dígitos, espacio y `. , # ° / -` | Dirección de cliente, de entrega y de empresa |
| Comentario | Letras, dígitos, espacios y saltos de línea, y `. , : ¿ ? ¡ ! ( ) ° # $ % + / -` | Comentarios de cotización |
| Email | `A-Z a-z 0-9 . _ % + - @` y formato `algo@dominio.tld` | Email de cliente, usuario y empresa |
| Teléfono | Dígitos, espacios y un `+` solo al inicio | Teléfono de cliente, usuario y empresa |
| Usuario | `A-Z a-z 0-9 . _ -` (sin espacios ni tildes) | Nombre de usuario |
| Nombre de empresa | Letras, dígitos, espacio y `. , & -` | Nombre de empresa |

Quedan fuera, entre otros, `; ' " < > = { } [ ] \ | * ^ ~` y el backtick.

## 3. Restricciones por entidad

"Opcional" = puede quedar vacío; si se completa, debe cumplir la regla.

### Cliente

| Campo | Obligatorio | Regla | BD |
|---|---|---|---|
| nombre | Sí | 5–50 caracteres, nombre de persona (sin dígitos) | `cliente_nombre_largo` |
| rut | Sí | Módulo 11; se guarda `12.345.678-9`; **único por empresa** | `cliente_rut_unico_por_empresa`, `cliente_rut_largo` (9–12) |
| teléfono | Opcional | Conjunto teléfono, 8–12 dígitos, máx. 20 caracteres | `cliente_telefono_largo` |
| email | Opcional | Conjunto email, máx. 100 | — |
| dirección | Opcional | 5–100, conjunto dirección | `cliente_direccion_largo` |

### Cotización

| Campo | Obligatorio | Regla | BD |
|---|---|---|---|
| cliente | Sí | Debe pertenecer a la empresa del usuario | — |
| dirección de entrega | Opcional | Igual que la dirección del cliente | `cotizacion_direccion_largo` |
| distancia (km) | Solo con transporte | 0,1–500, máx. 1 decimal. Sin transporte se guarda vacía | `cotizacion_distancia_segun_transporte` |
| comentarios | Opcional | Máx. 1000, conjunto comentario | `cotizacion_comentarios_largo` |
| monto agregado | Opcional | Entero 0–10.000.000, sin negativos. **Solo si hay un comentario** (en la UI se habilita al escribir uno) | `cotizacion_monto_agregado_rango`, `cotizacion_monto_agregado_con_comentario` |
| ventanas | Sí | 1–50 por cotización | — (solo backend y frontend) |
| estado | — | Pendiente / Aprobada / Rechazada | `cotizacion_estado_valido` |

### Ventana (de una cotización)

| Campo | Regla | BD |
|---|---|---|
| tipo | Opción válida **y con serie de aluminio configurada** (Línea 42 no disponible) | `ventana_tipo_valido` |
| color | Opción válida | `ventana_color_valido` |
| vidrio | Opción válida **y con plancha configurada** en Precios | `ventana_vidrio_valido` |
| ancho / alto | Entero 300–3000 mm | `ventana_dimensiones_rango` |
| cantidad | Entero 1–10 | `ventana_cantidad_rango` |

### Proyecto

| Campo | Regla | BD |
|---|---|---|
| estado de fabricación | Opción válida; se puede retroceder libremente | `proyecto_estado_produccion_valido` |
| estado de pago | **Derivado de los pagos** (no se edita): sin pagos Pendiente, parcial Abonado, total Pagado | `proyecto_estado_pago_valido` |
| monto abonado | **Derivado:** suma de los pagos vigentes | `proyecto_abono_segun_estado_pago` |

### Pago (de un proyecto)

| Campo | Obligatorio | Regla | BD |
|---|---|---|---|
| monto | Sí | Entero 1–10.000.000 y **no mayor que el saldo pendiente** (se verifica con el proyecto bloqueado) | `pago_monto_rango` |
| fecha | Sí | No futura ni anterior a la fecha de ingreso de la cotización | — |
| comentario | Opcional | Máx. 200, conjunto comentario | — |
| motivo de anulación | Sí al anular | 5–200, conjunto comentario. Solo el jefe anula; un pago anulado no se puede anular de nuevo (409) | `pago_anulado_con_fecha` |

### Catálogo de precios (solo el jefe)

**El valor 0 significa "sin configurar / sin precio"** en precios y pesos (se avisará en la fase de Alertas). Cualquier otro valor debe estar en rango.

| Campo | Regla | Decimales | BD |
|---|---|---|---|
| Margen de ganancia | 0–200 % | 2 | `empresa_margen_rango` |
| Precio de transporte por km | 0–50.000 CLP | 0 | `empresa_transporte_km_rango` |
| Peso total de la serie | 0, o 0,1–100 kg; no menor que su perfil más pesado | 3 | `serie_peso_total_rango` |
| Peso de cada perfil | 0, o 0,001–100 kg; **no mayor que el peso total de su serie** (si ambos están configurados) | 3 | `perfil_peso_rango` |
| Largo de tira | 1–7 m (estándar 6 m: valor inicial de `asegurar_catalogo`) | 3 | `perfil_largo_tira_rango` |
| Precio del paquete por color | 0–10.000.000 CLP | 0 | `precio_serie_rango`, `precio_serie_color_valido` |
| Ancho / alto de plancha | 0,5–4 m | 3 | `plancha_ancho_rango`, `plancha_alto_rango` |
| Precio de plancha | 0–10.000.000 CLP | 0 | `plancha_precio_rango`, `plancha_tipo_valido` |
| Precio del paquete de insumo | 0–10.000.000 CLP | 0 | `insumo_precio_rango` |
| Cantidad por paquete de insumo | Mayor que 0 (es divisor del cálculo, no admite 0) | 3 | `insumo_cantidad_paquete_positiva` |

Las reglas entre peso de perfil y peso de serie se validan en `PerfilSerieSerializer.validate` y `SerieAluminioSerializer.validate_peso_total_kg`. En Precios → Aluminio, si el peso total baja se guardan primero los perfiles, y si sube, primero la serie (`fase` en `guardarEnBloque`).

### Empresa (solo el administrador)

| Campo | Obligatorio | Regla | BD |
|---|---|---|---|
| nombre | Sí | 3–100, conjunto nombre de empresa | `empresa_nombre_largo` |
| rut | Opcional | Módulo 11, se guarda formateado; **único entre empresas** | `empresa_rut_unico` (si no está vacío), `empresa_rut_largo` |
| teléfono | Opcional | Igual que el del cliente | `empresa_telefono_largo` |
| email | Opcional | Conjunto email, máx. 100 | — |
| dirección | Opcional | 5–100, conjunto dirección | `empresa_direccion_largo` |

### Usuario (jefe: sus operarios; administrador: todos)

| Campo | Obligatorio | Regla | BD |
|---|---|---|---|
| nombre de usuario | Sí | 3–30, conjunto usuario; único | Único (Django) |
| nombre / apellido | Sí (en la API) | 2–50, nombre de persona | `usuario_nombre_largo`, `usuario_apellido_largo` (aceptan vacío por usuarios antiguos) |
| email | Opcional | Conjunto email | — |
| teléfono | Opcional | Igual que el del cliente | `usuario_telefono_largo` |
| contraseña | Sí al crear | Validadores de Django: mín. 8, no solo números, no muy común, no parecida al usuario. Se cambia con la acción `clave` | — |
| empresa / rol | Admin: obligatorios al crear. Jefe: los fija el servidor (operario de su empresa) | La empresa no cambia después de crear el usuario | `usuario_empresa_y_rol` (todo no-superusuario tiene empresa y rol válido) |

## 4. Cómo cambiar una regla

1. Cambiar el límite o la regex en [core/validacion.py](../core/validacion.py) **y** su espejo en `crystalworkfe/src/utils/validacion.js` (`LIMITES`, `REGLAS`, `PERMITIDOS`). Revisar que el ejemplo del campo (`EJEMPLOS` / `REGLAS[...].ejemplo`) siga cumpliendo la regla nueva.
2. Si cambia un rango o un largo usado en un `CheckConstraint`, correr `python manage.py makemigrations`. Si hay datos que no cumplirían la regla nueva, crear **antes** una migración de datos que los ajuste (ver la sección 5).
3. Si el mensaje de DRF sale genérico ("Asegúrese de que…"), agregar el campo a `MENSAJES_DRF` y usar `val.mensajes(...)` en el `extra_kwargs` del serializer.
4. Recordar que Django aplica `%` a los mensajes de los validators: un `%` literal se escribe `%%`.
5. Verificar con `python manage.py check`, `python manage.py test`, `npm run build` y `npx oxlint`.

## 5. Migraciones de ajuste de datos

Antes de crear las restricciones, estas migraciones dejaron los datos existentes dentro de las reglas. Copian los valores dentro de la migración a propósito, para que no cambien si después cambian las reglas:

| Migración | Qué ajusta |
|---|---|
| `core.0011_sanear_datos_validacion` | Textos con caracteres no permitidos, RUT inválido o repetido (reemplazo `90.000.000 + id`), distancia y monto fuera de rango, ventanas fuera de rango (las de 0×0 pasaron a 300×300) |
| `core.0013_sanear_catalogo_y_telefono` | Valores del catálogo y de la empresa fuera de rango (se acotan; el 0 se conserva); teléfonos inválidos quedan vacíos |
| `projects.0004_sanear_abono` | Abono según el estado de pago (Abonado sin monto vuelve a Pendiente; si cubre el total, pasa a Pagado) |

Las restricciones en sí están en `core.0012`, `core.0014`, `users.0003`, `users.0004` y `projects.0005`.

## 6. Sin validación específica (por ahora)

- **Insumo:** `codigo`, `nombre` y `unidad` se reenvían al guardar en Precios, pero no tienen reglas propias. Son un catálogo fijo y no se editan desde la UI.
- **Login:** usuario y contraseña solo son obligatorios. Falta *throttling* contra fuerza bruta (ver la sección 6 de ESTADO.md).
