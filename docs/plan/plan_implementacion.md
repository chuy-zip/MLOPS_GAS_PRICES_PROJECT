# Plan de implementación

Documento vivo. Aquí se registran las decisiones, las tareas y los avances. El detalle técnico de cada tema está en los demás documentos de `docs/`.

## Objetivo

Un usuario ingresa el precio de la gasolina de hoy (y, si da tiempo, una foto del dispensador). El sistema responde si es un buen precio y si se espera que suba o baje en el próximo cambio de referencia.

**Dentro del alcance:** pipeline por capas en Databricks, modelo registrado con MLflow, API en un Droplet de DigitalOcean, despliegue desde el repo y CI/CD.

**Fuera del alcance por ahora:** recomendar estación, monitoreo del modelo en producción y app móvil.

## Decisiones tomadas

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-11-11 | El Excel del MEM es la fuente principal de entrenamiento | Tiene datos diarios desde 2013. Las fotos no alcanzan para entrenar. Ver [fuentes_de_datos.md](../datos/fuentes_de_datos.md) |
| 2026-11-11 | El Excel se versiona en el repo, en `data/mem/` | La descarga automática desde la web del MEM no funcionó de forma confiable |
| 2026-11-11 | Raw es solo de lectura. Nuestros archivos aterrizan en bronce | La external location de raw tiene activado "Limit to read-only use" |
| 2026-11-11 | GitHub Actions solo valida y dispara. El procesamiento ocurre en Databricks | Procesar datos fuera de la plataforma rompe la trazabilidad y el linaje |
| 2026-11-11 | La exploración de las fotos es un job aparte, fuera del pipeline | Primero hay que conocer los datos para diseñar la carga |
| 2026-11-11 | El proyecto vive en su propio repo público, `chuy-zip/MLOPS_GAS_PRICES_PROJECT` | Separa el CI, los secretos y el historial del repo del curso. Al ser público, los notebooks pueden leer archivos del repo por URL |
| 2026-11-12 | Sin esquemas por persona. Las pruebas se hacen sobre los esquemas compartidos, con un responsable por tabla a la vez, y después de cada merge se vuelve a correr el pipeline | Cada persona trabaja en tareas distintas. Las escrituras con `MERGE` no duplican datos |
| 2026-11-12 | Cada desarrollador prueba en su propia carpeta Git de Databricks y sube los cambios con commit y push desde ahí | Es la única forma de probar contra los datos reales sin pasar por el CI en cada intento |
| 2026-11-12 | Ruleset en `main` que exige el check `plan` en verde para hacer merge. Sin aprobaciones obligatorias | Evita que un bundle roto llegue a `main` y rompa el despliegue, sin frenar al equipo con revisiones. Reemplaza la decisión anterior de no proteger `main` |
| 2026-11-11 | Primero se valida la infraestructura (bundle y CI) y después se explora el bucket | El job de exploración es la primera prueba de punta a punta del despliegue |
| 2026-11-11 | Catálogo `gas_price` con esquemas `bronze`, `silver` y `gold`. El catálogo ya está creado | La cuenta de Databricks es del equipo, así que se pudo crear sin pedir permiso |
| 2026-11-11 | Mientras no se pueda escribir en los buckets, las tablas usan el almacenamiento por defecto | `xloc-cusn` es de solo lectura. No se bloquea el proyecto esperando al catedrático |
| 2026-11-11 | "Buen precio" se resuelve comparando con la referencia oficial. La tendencia, con un modelo de clasificación | Ver [modelo.md](../modelo/modelo.md) |
| 2026-11-11 | El horizonte de la predicción es el próximo cambio de referencia, 7 días o menos | El precio oficial cambia una vez por semana. "Esperar" significa esperar a ese cambio |
| 2026-11-11 | No se exige que el modelo supere una línea base. Las métricas se reportan sin umbral mínimo | Decisión del equipo |
| 2026-11-11 | Un esquema por capa, cada uno con su bucket como ubicación administrada | Cumple el diagrama con tablas administradas normales. Requiere `CREATE MANAGED STORAGE`. Ver [databricks.md](../infraestructura/databricks.md) |
| 2026-11-11 | Los jobs y notebooks se despliegan con bundles de Databricks. No se usa Terraform | Sin cuentas externas y el estado vive en el workspace. Ver [ci_cd.md](../infraestructura/ci_cd.md) |
| 2026-11-11 | Un solo ambiente compartido. Solo el CI despliega, y solo desde `main` | Evita que cada persona tenga una versión distinta desplegada |
| 2026-11-11 | El catálogo y los esquemas se crean una sola vez con un script SQL versionado | Son pocos objetos y no cambian |
| 2026-11-12 | El Excel del MEM no se edita a mano. Los duplicados y los precios en 0 se resuelven en plata | El archivo queda igual a la publicación original y las reglas quedan versionadas en `src/gas_price/mem.py` |
| 2026-11-12 | Fechas repetidas: si son idénticas se deja una fila, si difieren el pipeline falla | Las 3 fechas repetidas actuales son copias exactas |
| 2026-11-12 | Primero se arma el pipeline completo del Excel hasta el modelo. Las tareas de fotos siguen vacías | El curso evalúa la ingeniería del pipeline. Las fotos se conectan después sin cambiar el resto |
| 2026-11-12 | Se agregan los precios internacionales de la EIA como segunda fuente, versionados en `data/eia/` | Sin ese dato el modelo no supera a la regla de repetir la semana pasada. Con él sí. Ver [modelo.md](../modelo/modelo.md) |
| 2026-11-12 | Las tablas se definen en `databricks/sql/tablas.sql`. Las crea el job `gas_price_setup`, que el CI corre después de cada despliegue | Los bundles no tienen un recurso para tablas. Así los tipos quedan versionados, una tarea no puede cambiar una tabla en silencio y la estructura se aplica al hacer merge, separada del procesamiento de datos |
| 2026-11-11 | El Droplet no se administra desde el proyecto. Una persona del equipo tiene acceso por ssh con sudo | El Droplet lo provee el curso |

## Decisiones pendientes

| Decisión | Recomendación | Dónde se discute |
|---|---|---|
| Cómo se aprovechan las fotos más allá del EXIF | Tema abierto. Lo decide quien trabaje las fotos | [fuentes_de_datos.md](../datos/fuentes_de_datos.md) |

## Fases y tareas

| Fase | Tarea | Responsable | Estado |
|---|---|---|---|
| 0 | Revisar permisos de las external locations | Ricardo | Hecho |
| 0 | Crear el repo propio y mover la documentación | Ricardo | Hecho |
| 0 | Pedir al catedrático desactivar "Limit to read-only use" en bronce y plata, y otorgar `CREATE MANAGED STORAGE` en bronce, plata y oro | | Pendiente |
| 1 | Bundle con el job de exploración y el job del pipeline con tareas vacías | Ricardo | Hecho |
| 1 | Workflows de plan con comentario desplegable y de despliegue en `main` | Ricardo | Hecho |
| 1 | Generar el token de Databricks y guardar `DATABRICKS_HOST` y `DATABRICKS_TOKEN` en GitHub | Ricardo | Hecho |
| 1 | Primer pull request: revisar el comentario con el plan | Ricardo | Hecho |
| 1 | Crear el ruleset de `main` con el check `plan` obligatorio | Ricardo | Hecho |
| 1 | Merge a `main`: confirmar que los dos jobs aparecen en el workspace | Ricardo | Hecho |
| 1 | Correr el job `gas_price_exploracion` y documentar cuántas fotos hay, de qué fechas y de qué lugares | Ricardo | Hecho. Ver [fuentes_de_datos.md](../datos/fuentes_de_datos.md) |
| 1 | Prueba de permisos: crear el catálogo `gas_price` | Ricardo | Hecho |
| 1 | Prueba de permisos: esquema con ubicación en el bucket de bronce | Ricardo | Hecho: falló, `xloc-cusn` es de solo lectura |
| 1 | Revisar si `xloc-ag` y `xloc-au` también son de solo lectura | Ricardo | Hecho: plata es de solo lectura, oro permite escritura |
| 1 | Prueba de permisos: esquema con ubicación en el bucket de oro | Ricardo | Hecho: falló, falta `CREATE MANAGED STORAGE` |
| 1 | Script SQL que crea el catálogo, los esquemas y el volumen | Ricardo | Hecho. Falta correrlo en el SQL Editor |
| 1 | Paquete `gas_price` con el lector del Excel del MEM | Ricardo | Hecho |
| 2 | Test de "no empeorar" el Excel del MEM y workflow `tests.yml` | Ricardo | Hecho |
| 2 | Agregar el check `tests` al ruleset de `main` | | Pendiente |
| 2 | Tarea de ingesta del Excel a bronce | Ricardo | Escrita, falta probar en Databricks |
| 2 | Lector de los archivos de la EIA y sus tests | Ricardo | Hecho |
| 2 | Tarea de ingesta de la EIA a bronce | Ricardo | Escrita, falta probar en Databricks |
| 2 | Tarea de ingesta de fotos a bronce con Auto Loader | | Pendiente |
| 3 | Tarea del Excel a plata | Ricardo | Escrita, falta probar en Databricks |
| 3 | Tarea de la EIA a plata | Ricardo | Escrita, falta probar en Databricks |
| 3 | Tarea de EXIF a plata | | Pendiente |
| 3 | Definir cómo se aprovechan las fotos más allá del EXIF | | Pendiente |
| 4 | Tarea de plata a oro, incluyendo la definición de la semana y del próximo cambio | Ricardo | Escrita, falta probar en Databricks |
| 5 | Tarea de entrenamiento y registro en MLflow | Ricardo | Escrita, falta probar en Databricks |
| 5 | Script de evaluación local del modelo | Ricardo | Hecho |
| 5 | Tarea que publica la referencia actual para la API | | Pendiente |
| 6 | API con FastAPI y Docker en el Droplet | | Pendiente |
| 6 | Frontend simple con entrada de precio | | Pendiente |
| 7 | Entrada por foto en la API | | Opcional |

## Riesgos

1. Puede que el catedrático no otorgue `CREATE MANAGED STORAGE`. En ese caso las tablas quedan en el almacenamiento por defecto y el código no cambia.
2. Free Edition tiene cuotas de uso y un máximo de 5 tareas de job a la vez. Con varios desarrolladores probando al mismo tiempo, el cómputo puede apagarse el resto del día.

## Bitácora

| Fecha | Avance |
|---|---|
| 2026-11-11 | Se ubicó el código previo, se analizó el Excel del MEM y se armó la documentación inicial |
| 2026-11-11 | Se revisaron los permisos de las 4 external locations y se reorganizó la documentación por tipo |
| 2026-11-11 | Se definió el horizonte del modelo, el almacenamiento por esquema y la recomendación de usar bundles |
| 2026-11-11 | Se adoptaron los bundles con un solo ambiente compartido y se descartó Terraform |
| 2026-11-11 | Se creó el repo propio, se movió la documentación y se armaron el bundle y los workflows de plan y despliegue |
| 2026-11-12 | Primer despliegue por CI: los dos jobs quedaron en el workspace. Se corrió la exploración: 110 fotos de diciembre 2022 a noviembre 2026 |
| 2026-11-12 | Se armó el paquete `gas_price` con el lector del Excel, los tests y el workflow de tests. Se encontró que los precios en 0 significan días sin publicación |
| 2026-11-12 | Prueba local del modelo: con solo el MEM no supera a repetir la semana pasada. Se agregó la EIA como segunda fuente y con ella sí la supera |
| 2026-11-12 | Se confirmó que las fotos del bucket son las originales. Los colores raros venían del modo oscuro de Databricks, que invierte las salidas de `displayHTML`. Se documentó en las lecciones aprendidas |
