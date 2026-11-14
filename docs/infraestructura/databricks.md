# Entorno de Databricks

## Workspace

1. Es un workspace compartido de **Databricks Free Edition**, configurado por el catedrático.
2. Los integrantes del equipo tienen rol de administrador del workspace.
3. Catálogos existentes al 2026-11-11: `samples`, `system`, `test_catalog` y `workspace`.
4. El catálogo `workspace` ya tiene esquemas de actividades anteriores, como `bronze`, `silver` y `gold`. Por eso el proyecto usa un catálogo propio, o un prefijo si no se puede crear. Ver [esquemas_medallion.md](../datos/esquemas_medallion.md).

## Límites de Free Edition que afectan al proyecto

Tomados de la [documentación oficial de límites de Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations):

| Límite | Efecto en el proyecto |
|---|---|
| Solo cómputo serverless | No hay clusters propios. No se pueden instalar programas del sistema con apt, como Tesseract o exiftool |
| Salida a internet restringida a dominios de confianza | Hay que confirmar cada dominio. Ya funcionó leer archivos de `raw.githubusercontent.com` en el Ejercicio 5 |
| Máximo 5 tareas de job concurrentes por cuenta | El pipeline no debe lanzar más de 5 tareas en paralelo. Con varios desarrolladores probando a la vez, conviene coordinar |
| Un solo SQL warehouse, tamaño 2X-Small | Consultas livianas |
| Cuota de uso justa: si se excede, el cómputo se apaga el resto del día | El pipeline debe ser incremental y no reprocesar todo |
| Sin acceso a la consola de cuenta ni a APIs de cuenta | Solo se pueden usar APIs del workspace. Unity Catalog, jobs y notebooks son del workspace, así que sí se pueden manejar con código |

La página no menciona si funcionan los file arrival triggers. Por eso el job usa una programación semanal, que el enunciado también acepta.

## Cómputo: clusters del enunciado contra serverless

El enunciado pide desarrollar en un cluster interactivo, correr el job en un job cluster, documentar la configuración de cada uno y explicar la diferencia de costo y propósito. También acepta "el cómputo que indique el catedrático".

| Enunciado | Qué es | En Free Edition |
|---|---|---|
| Cluster interactivo (all-purpose) | Se enciende a mano y se conectan notebooks para desarrollar. Cobra mientras está encendido, aunque nadie lo use. Por eso el enunciado exige apagado automático a los 30 minutos sin uso | Serverless interactivo: el cómputo de los notebooks. No se configura ni hay que apagarlo |
| Job cluster | Se crea al iniciar una corrida del job y se destruye al terminar. Solo cobra durante la corrida. Es más barato | Serverless de jobs: se asigna a cada corrida y se libera al terminar |

En serverless no se elige versión de runtime, tipo de nodo ni cantidad de workers: Databricks los administra. Las librerías se instalan por notebook con `%pip`, y la versión del entorno serverless se ve en el panel **Environment** de cada notebook. Esta equivalencia hay que confirmarla con el catedrático.

## Lecciones aprendidas

| Situación | Causa | Qué hacer |
|---|---|---|
| Las imágenes mostradas con `displayHTML` se ven con colores invertidos: lo negro sale claro, lo blanco gris y el rojo rosado | En modo oscuro, Databricks invierte los tonos claros y oscuros de las salidas de `displayHTML`. Fuente: [HTML outputs in dark mode](https://docs.databricks.com/aws/en/notebooks/notebook-ui) | Agregar la clase `nodarkmode` a los elementos que muestran imágenes. Para revisar una sola salida, usar el ícono de sol de esa salida |
| Las fotos de iPhone se ven un poco apagadas al mostrarlas | Vienen en el perfil de color Display P3 y el navegador asume sRGB | Convertir a sRGB antes de mostrarlas. No afecta el EXIF ni la lectura del precio |
| Una corrida vieja de un job ya no aparece | Databricks guarda el historial de corridas por 60 días. Fuente: [monitorear jobs](https://docs.databricks.com/aws/en/jobs/monitor) | Si hace falta conservar un resultado, abrir la corrida, elegir la tarea y exportarla a HTML. Los hallazgos se resumen en `docs/` |

**Código contra resultados:**

1. Hacer commit desde una carpeta Git guarda el código del notebook, no sus resultados. Los notebooks están en formato fuente (`.py`), que no incluye salidas.
2. El bundle despliega en `/Workspace/Shared/.bundle/gas_price/prod`. Nunca modifica las carpetas Git personales.
3. Las exportaciones de corridas no se suben al repo. Incluyen rutas de los buckets y coordenadas GPS exactas de las fotos, y el repo es público.
4. Los notebooks se mantienen en formato `.py`. Databricks permite guardar las salidas de notebooks `.ipynb` en Git, pero un administrador tiene que habilitarlo y las salidas expondrían esos mismos datos. Además, las imágenes incrustadas harían los cambios difíciles de revisar. Fuente: [formato de notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-format).
5. Hacer pull en una carpeta Git borra las salidas de los notebooks que cambian. Si una corrida interactiva importa, exportarla antes del pull.

## Conceptos de almacenamiento en Unity Catalog

| Concepto | Qué es | Ejemplo en el proyecto |
|---|---|---|
| External location | Permiso para usar una ruta de S3 con una credencial. La crea un administrador | `xloc-raw`, `xloc-cusn`, `xloc-ag`, `xloc-au`, creadas por el catedrático |
| Tabla administrada | Tabla cuyos archivos guarda y administra Unity Catalog. Si se borra la tabla, se borran sus datos | Ninguna tabla del pipeline. El modelo registrado sí vive así |
| Ubicación administrada | Ruta donde un esquema guarda sus tablas administradas. Si el esquema no tiene una, usa la del catálogo | No se usa: requiere `CREATE MANAGED STORAGE`, que no tenemos |
| Tabla externa | Tabla que apunta a archivos en una ruta elegida a mano. Si se borra la tabla, los archivos quedan | Todas las tablas de bronce, plata y oro, en `equipo-01/<capa>/<tabla>` de cada bucket |
| Volumen | Objeto de Unity Catalog para guardar archivos que no son tablas, como imágenes o Excel | Un volumen administrado en bronce para la copia del Excel y los checkpoints |

**Por qué las tablas van en los buckets.** El diagrama del catedrático pone cada capa en S3, y él creó una external location por capa. Las tablas son externas, en una ruta fija dentro del prefijo `equipo-01/` de cada bucket. Ver la sección "Estado final" al final de este documento.

**Raw no necesita ningún objeto.** Las fotos se leen directo por ruta, con el permiso `READ FILES` que ya tenemos.

## External locations

Las 4 external locations las creó el catedrático el 2026-09-12. Cada una usa su propia credencial de almacenamiento. No tenemos credenciales de AWS.

| Nombre | Capa | Bucket | Solo lectura | File events |
|---|---|---|---|---|
| xloc-raw | Raw | `cc3105-raw-...` | Sí | Activados |
| xloc-cusn | Bronce (Cu y Sn) | `cc3105-cusn-...` | Sí | Activados |
| xloc-ag | Plata (Ag) | `cc3105-ag-...` | Sí | Activados |
| xloc-au | Oro (Au) | `cc3105-au-...` | No | Activados |

Revisado el 2026-11-11 en la pestaña Overview de cada external location. La opción "Limit to read-only use" tiene prioridad sobre el permiso `WRITE FILES`: aunque tengamos ese permiso en las 4, solo se puede escribir en `xloc-au`.

En el código no se escriben las URL de los buckets. Se obtienen en tiempo de ejecución con `DESCRIBE EXTERNAL LOCATION`, así el repo público no las expone.

## Permisos

Estado inicial, del 2026-11-11, según `SHOW GRANTS ON EXTERNAL LOCATION`. Los permisos actuales están en "Estado final", al final de este documento. Las 4 ubicaciones tenían los mismos permisos:

| Principal | Permiso |
|---|---|
| account users | BROWSE |
| account users | READ FILES |
| account users | WRITE FILES |

**Qué significa:**

1. Podemos leer las fotos de raw por ruta. Es lo que usa el notebook de exploración.
2. En raw no podemos escribir, porque la ubicación está limitada a solo lectura.
3. "File events" activado en raw permite detectar fotos nuevas y disparar el job.

**Qué faltaba entonces:** para que un esquema guarde sus tablas en un bucket hace falta `CREATE MANAGED STORAGE` sobre esa external location. Según la [documentación de ubicaciones administradas](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/managed-storage), ese permiso es el que permite definir la ubicación al crear el esquema. No aparece en la lista, aunque podríamos tenerlo como administradores. Hay que probarlo.

## Prueba de permisos

Correr en el SQL Editor, una sentencia a la vez. Reemplazar `<url_bronce>` por la URL que devuelve `DESCRIBE EXTERNAL LOCATION xloc-cusn`. Si una sentencia falla, anotar el mensaje de error.

**Paso 1: ¿podemos crear un catálogo?**

```sql
CREATE CATALOG IF NOT EXISTS gas_price_prueba;
```

**Paso 2: ¿podemos guardar tablas en el bucket de bronce?** Si el paso 1 funcionó, usar `gas_price_prueba` como catálogo. Si falló, usar `workspace`.

```sql
CREATE SCHEMA IF NOT EXISTS <catálogo>.prueba_permisos MANAGED LOCATION '<url_bronce>gas_price/prueba';
CREATE TABLE <catálogo>.prueba_permisos.t AS SELECT 1 AS x;
SELECT * FROM <catálogo>.prueba_permisos.t;
```

**Limpieza:**

```sql
DROP SCHEMA IF EXISTS <catálogo>.prueba_permisos CASCADE;
DROP CATALOG IF EXISTS gas_price_prueba CASCADE;
```

| Resultado | Qué significa |
|---|---|
| Pasos 1 y 2 funcionan | Catálogo `gas_price` con tablas en los buckets. Es la opción preferida |
| Paso 1 falla y paso 2 funciona | Esquemas con prefijo en `workspace`, con tablas en los buckets |
| Paso 2 falla | Hay que pedir `CREATE MANAGED STORAGE` al catedrático |

## Resultado de la prueba (2026-11-11)

1. `CREATE CATALOG IF NOT EXISTS gas_price` funcionó. El catálogo existe.
2. Crear un esquema con ubicación en `xloc-cusn` falló con: `PERMISSION_DENIED: Creating a schema with a read-only storage location is not supported`.

La causa es que `xloc-cusn` tiene activada la opción "Limit to read-only use". Con una ubicación de solo lectura no se puede crear un esquema sobre ella ni escribir archivos por ruta, aunque tengamos `WRITE FILES`. Lo mismo aplica a `xloc-ag`. Solo `xloc-au` permite escritura.

3. Crear un esquema con ubicación en `xloc-au` falló con: `PERMISSION_DENIED: Principal '...' does not have CREATE MANAGED STORAGE on External Location 'xloc-au'`.

| Ubicación | Problema |
|---|---|
| xloc-cusn | Solo lectura y falta `CREATE MANAGED STORAGE` |
| xloc-ag | Solo lectura y falta `CREATE MANAGED STORAGE` |
| xloc-au | Falta `CREATE MANAGED STORAGE` |

Se le pide al catedrático desactivar "Limit to read-only use" en `xloc-cusn` y `xloc-ag`, y otorgar `CREATE MANAGED STORAGE` en las tres.

## Estado final (2026-11-13)

Primero el catedrático indicó que Free Edition no permitía escribir en un proveedor de nube externo, y se acordó trabajar todo en Databricks. El mismo día logró habilitar la escritura. Revisado con la CLI:

| External location | Solo lectura | Permisos de `account users` |
|---|---|---|
| `xloc-raw` | Sí | `BROWSE`, `READ FILES`, `WRITE FILES` |
| `xloc-cusn` | No | `BROWSE`, `CREATE EXTERNAL TABLE`, `READ FILES`, `WRITE FILES` |
| `xloc-ag` | No | `BROWSE`, `CREATE EXTERNAL TABLE`, `READ FILES`, `WRITE FILES` |
| `xloc-au` | No | `BROWSE`, `CREATE EXTERNAL TABLE`, `READ FILES`, `WRITE FILES` |

Con eso:

1. **Todas las tablas son externas,** en el bucket de su capa y dentro del prefijo `equipo-01/`. `CREATE EXTERNAL TABLE` es el permiso que lo permite. `CREATE MANAGED STORAGE` no hace falta.
2. **Raw sigue siendo de solo lectura.** Las fotos se leen desde ahí.
3. **El volumen `archivos` y el modelo se quedan en Databricks.** Nadie los lee desde afuera.
4. **La API no cambia.** El Droplet no tiene acceso a S3, así que sigue usando el modelo y una copia de oro descargados con `scripts/exportar_para_api.py`. Ver [arquitectura.md](../arquitectura/arquitectura.md).

Las pruebas y los permisos de arriba quedan como registro de lo que se intentó.

## Token para el CI

GitHub Actions necesita un token para hablar con el workspace. La documentación de [tokens personales](https://docs.databricks.com/aws/en/dev-tools/auth/pat) no menciona restricciones en Free Edition. Pasos:

1. Clic en el usuario, arriba a la derecha.
2. **Settings**, luego **Developer**.
3. Junto a **Access tokens**, clic en **Manage** y luego **Generate new token**.
4. Ponerle un nombre como `github-actions-proyecto-final` y una vigencia en días.
5. Copiar el token. Solo se muestra una vez.
6. Guardarlo en GitHub como secreto `DATABRICKS_TOKEN`, en Settings, Secrets and variables, Actions.

Notas:

1. Si la opción no aparece, un administrador debe habilitar los tokens en la configuración del workspace.
2. Un token sin uso por 90 días se revoca solo.
3. El token queda ligado a la persona que lo creó. Si esa persona pierde acceso, el CI deja de funcionar.
4. Para uso local, cada desarrollador se autentica con OAuth en lugar de un token: `databricks auth login --host <url_del_workspace>`.
