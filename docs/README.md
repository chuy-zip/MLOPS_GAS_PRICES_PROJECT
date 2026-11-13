# Documentación del proyecto final

Monitoreo del precio de la gasolina en Guatemala. Toda la documentación del proyecto vive en esta carpeta, ordenada por tipo.

| Carpeta | Documento | Contenido |
|---|---|---|
| plan | [plan_implementacion.md](plan/plan_implementacion.md) | Fases, tareas, decisiones y bitácora. Es el punto de partida |
| contexto | [enunciado_proyecto_final.pdf](contexto/enunciado_proyecto_final.pdf) | **Enunciado oficial del proyecto**: requisitos, rúbrica, entregables y calendario |
| contexto | [caso_de_uso.md](contexto/caso_de_uso.md) | Caso de uso, análisis de negocio, diagrama original y código previo que se reutiliza |
| arquitectura | [arquitectura.md](arquitectura/arquitectura.md) | Componentes, pipeline, orquestación y servicio |
| datos | [fuentes_de_datos.md](datos/fuentes_de_datos.md) | Excel del MEM, precios internacionales de la EIA, fotos y cómo se actualizan |
| datos | [esquemas_medallion.md](datos/esquemas_medallion.md) | Qué va en cada capa y el esquema de cada tabla |
| modelo | [modelo.md](modelo/modelo.md) | Qué modelo se entrena y por qué |
| infraestructura | [databricks.md](infraestructura/databricks.md) | Workspace, external locations, permisos y token |
| infraestructura | [ci_cd.md](infraestructura/ci_cd.md) | Bundles de Databricks, workflows y despliegue de la API |

Archivos de apoyo en `contexto/`: el enunciado oficial (`enunciado_proyecto_final.pdf`), el diagrama entregado por el catedrático (`diagrama_original.png`) y el análisis de negocio hecho antes por el equipo (`analisis_negocio_gasolineras.pdf`). Si algo de esta documentación contradice el enunciado, manda el enunciado.
