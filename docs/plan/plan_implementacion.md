# Plan de implementación

Documento vivo. Aquí se registran las decisiones, las tareas y los avances. El detalle técnico de cada tema está en los demás documentos de `docs/`.

## Objetivo

Según el enunciado oficial, en `docs/contexto/`: un pipeline de punta a punta que monitorea el precio de los combustibles en Guatemala y predice si subirá o bajará la semana siguiente. La fuente principal son las fotos de precios del catedrático. El pipeline las guarda en S3, las convierte en datos con Databricks y la arquitectura medallón, y publica precios y predicciones en una API REST en un Droplet de DigitalOcean.

**Además:** CI/CD del bundle de Databricks, fuentes complementarias del MEM y la EIA para la historia del modelo, y la comparación del precio del usuario contra la referencia oficial.

**Fuera del alcance:** recomendar estación, monitoreo del modelo en producción y app móvil.

## Cumplimiento del enunciado

Puntos de la rúbrica y estado al 2026-11-13:

| Criterio | Puntos | Estado |
|---|---|---|
| Capa bronce: fotos por external location, carga incremental y auditoría | 10 | Pendiente. MEM y EIA ya están en bronce como fuentes complementarias |
| Capa plata: extracción de precios, 3 reglas de calidad, cuarentena y exactitud medida a mano | 15 | Pendiente |
| Capa oro: precio semanal, variación, etiqueta de dirección y comentarios | 10 | Parcial. Faltan `precio_semanal` y `variacion_semanal`, que dependen de las fotos |
| Modelo: validación temporal, comparación con la línea base y MLflow | 10 | Hecho. 0.55 contra 0.46 de la línea base |
| Clusters y job: cómputo, job encadenado, programación y alertas | 10 | Hecho, salvo confirmar con el catedrático la equivalencia con serverless |
| API en el Droplet | 20 | Pendiente. Faltan las credenciales de solo lectura para S3 |
| Repositorio y README | 10 | Parcial. Faltan el diagrama exportado, la presentación y commits de todos |
| Informe técnico | 5 | Pendiente |
| Presentación y demo | 10 | Pendiente |

## Decisiones tomadas

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-11-11 | El Excel del MEM es la fuente principal de entrenamiento. Reemplazada el 2026-11-13: ahora es complementaria | Tiene datos diarios desde 2013. Las fotos no alcanzan para entrenar. Ver [fuentes_de_datos.md](../datos/fuentes_de_datos.md) |
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
| 2026-11-13 | Se adopta el enunciado oficial. Las fotos son la fuente principal. El MEM y la EIA quedan como fuentes complementarias | El enunciado lo define así y permite fuentes complementarias para la historia del modelo |
| 2026-11-13 | Nombres según la convención del enunciado: catálogo `equipo_01`, jobs `equipo-01-*`, repo `equipo-01-gasolina-gt` y prefijo `equipo-01/` en los buckets | El enunciado los pide como entregables con nombre fijo |
| 2026-11-13 | La etiqueta "igual" pasa a llamarse `se_mantiene` | Es el nombre del enunciado |
| 2026-11-13 | La API lee oro directamente. El job guarda la predicción en `gold.predicciones` y las métricas en `gold.metricas_modelo`. La tarea 50 deja de publicar un archivo y pasa a predecir | El enunciado pide que la API lea oro. Así la API no carga el modelo |
| 2026-11-13 | El job corre cada martes a las 8:00 y avisa por correo si falla | El enunciado pide programación o disparo por fotos, y una alerta. El MEM publica los martes |
| 2026-11-13 | El job mantiene una tarea por fuente y por paso, en lugar de 3 tareas | Sigue el orden bronce, plata y oro. Cada tarea se prueba por separado. Se confirma con el catedrático |

## Decisiones pendientes

| Decisión | Recomendación | Dónde se discute |
|---|---|---|
| Técnica para extraer el precio de las fotos | OCR o modelo de visión, a elección de quien trabaje las fotos. Tesseract no se puede instalar en serverless | [fuentes_de_datos.md](../datos/fuentes_de_datos.md) |
| Equivalencia entre los clusters del enunciado y serverless | Confirmar con el catedrático | [databricks.md](../infraestructura/databricks.md) |
| Credenciales de solo lectura para que la API lea oro desde S3 | Pedirlas al catedrático | [ci_cd.md](../infraestructura/ci_cd.md) |
| Ubicación de las fotos nuevas | El enunciado menciona `fotos/AAAA-MM-DD/` en el bucket de bronce. Las 110 actuales están en `xloc-raw`. Confirmar con el catedrático | [fuentes_de_datos.md](../datos/fuentes_de_datos.md) |

## Fases y tareas

Las fases siguen el calendario del enunciado. Las tareas hechas antes del 2026-11-13 están en la bitácora.

| Fase | Tarea | Responsable | Estado |
|---|---|---|---|
| 0 | Pedir al catedrático desactivar "Limit to read-only use" en bronce y plata, y otorgar `CREATE MANAGED STORAGE` en bronce, plata y oro | Ricardo | Pendiente |
| 0 | Mover las tablas a los buckets cuando lleguen los permisos | Ricardo | Pendiente |
| 1 | Acceso ssh al Droplet verificado | | Pendiente |
| 1 | `bronze.fotos_precios` con carga incremental y columnas de auditoría | | Pendiente |
| 2 | Extracción de precios y `silver.precios` con 3 reglas de calidad | | Pendiente |
| 2 | `silver.precios_rejected` con el motivo de cada rechazo | | Pendiente |
| 2 | Revisión manual de al menos 20 fotos y porcentaje de acierto | | Pendiente |
| 3 | MEM y EIA de bronce a oro, modelo, MLflow y job de punta a punta | Ricardo | Hecho |
| 3 | `gold.predicciones` y `gold.metricas_modelo` | Ricardo | Hecho |
| 3 | Programación semanal y alerta por correo | Ricardo | Hecho. La alerta se verá la primera vez que falle el job |
| 3 | Migración al catálogo `equipo_01` y borrado del catálogo `gas_price` | Ricardo | Hecho |
| 3 | `gold.precio_semanal` y `gold.variacion_semanal` desde las fotos | | Pendiente |
| 3 | Evidencia de al menos 2 corridas exitosas con fotos de semanas distintas | | Pendiente |
| 4 | API con los endpoints del enunciado en el puerto del equipo | | Pendiente |
| 4 | Pruebas de usuario final con `curl` o Postman | | Pendiente |
| 5 | Diagrama de arquitectura exportado y su fuente editable | | Pendiente |
| 5 | Informe técnico de máximo 5 páginas | | Pendiente |
| 5 | Presentación, resumen de una página y demo | | Pendiente |
| Extra | CI/CD hacia el Droplet o pruebas automatizadas de la API | | Opcional |

## Riesgos

1. Puede que el catedrático no otorgue `CREATE MANAGED STORAGE`. En ese caso las tablas quedan en el almacenamiento por defecto y el código no cambia.
2. Free Edition tiene cuotas de uso y un máximo de 5 tareas de job a la vez. Con varios desarrolladores probando al mismo tiempo, el cómputo puede apagarse el resto del día.
3. Bronce y plata de fotos valen 25 puntos y todavía no empiezan. Es la parte con más peso pendiente.
4. Sin credenciales de S3 para el Droplet, la API no puede leer oro como pide el enunciado.

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
| 2026-11-12 | El job completo corre en unos 2 minutos. Modelo registrado con balanced accuracy de 0.55 contra 0.46 de la línea base. Tablas definidas en un DDL versionado |
| 2026-11-13 | Se recibió el enunciado oficial. Se alinearon nombres, etiqueta, predicciones, métricas, programación, alertas y documentación |
| 2026-11-13 | El repo pasó a llamarse `equipo-01-gasolina-gt`. El job corrió completo en `equipo_01`: 0.551 contra 0.458 de la línea base. Se borró el catálogo `gas_price` |
