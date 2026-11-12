# Despliegue y CI/CD

## Qué queremos

1. Definir en el repo los jobs y los notebooks.
2. En cada pull request, ver como comentario desplegable qué cambiaría en Databricks.
3. Al hacer merge a `main`, aplicar esos cambios.
4. Que todo el equipo trabaje sobre la misma versión desplegada, sin diferencias entre personas.

## Herramienta: bundles de Databricks

Los bundles son la herramienta propia de Databricks para definir jobs, notebooks, esquemas, volúmenes y modelos en archivos YAML. Se llamaban Databricks Asset Bundles y ahora se llaman Declarative Automation Bundles. Se usan con la CLI de Databricks.

| Comando | Qué hace |
|---|---|
| `databricks bundle validate` | Revisa que la definición sea válida |
| `databricks bundle plan` | Muestra qué se crearía o cambiaría, sin tocar nada |
| `databricks bundle deploy` | Aplica los cambios en el workspace |
| `databricks bundle run <job>` | Corre un job desplegado |

Fuente: [documentación de comandos de bundles](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands). El estado de lo desplegado se guarda en el propio workspace, así que no hace falta S3 ni una cuenta externa.

**Por qué no Terraform.** Terraform necesita guardar su estado en un lugar compartido, como S3 o HCP Terraform. No tenemos S3 y HCP Terraform agregaría otra cuenta. Además, el Droplet no lo administramos nosotros, así que no hay nada fuera de Databricks que crear con código. Los bundles cubren lo que sí necesitamos.

**Lo que no hacen los bundles:** la documentación no confirma que manejen catálogos ni permisos. El catálogo, los esquemas y el volumen se crean una sola vez con el script `infra/sql/00_unity_catalog.sql`, que un administrador corre a mano. Así el token del CI no necesita permisos sobre las external locations.

## Un solo ambiente compartido

Para que nadie tenga una versión distinta desplegada:

1. **Solo el CI despliega**, y solo desde `main`. El workflow de despliegue solo corre al hacer merge a `main`. Nadie corre `databricks bundle deploy` desde su computadora.
2. **El bundle tiene un solo destino**, `prod`. Sus archivos y su estado viven en `/Workspace/Shared/.bundle/gas_price/prod`, visibles para todo el equipo.
3. **Los cambios llegan por pull request**, con el plan y los tests del CI a la vista. No se activa branch protection en GitHub: es un acuerdo del equipo.
4. **Un despliegue a la vez:** el workflow de despliegue usa `concurrency` de GitHub Actions para no correr dos despliegues juntos.
5. **Una corrida a la vez:** los jobs tienen `max_concurrent_runs: 1`. Si dos personas lanzan el mismo job, la segunda corrida espera. Ayuda también con el límite de 5 tareas de Free Edition.

No se usa el modo producción de los bundles. Según la [documentación de modos de despliegue](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes), ese modo exige que la rama actual coincida con `main`, y el plan de los pull requests corre en otra rama.

**Cómo prueba un cambio un desarrollador antes del merge:**

1. Clona el repo como Git folder en el workspace, en su rama. Si Free Edition no lo permite, importa el notebook de su rama a su carpeta personal.
2. Abre el notebook que está cambiando y lo corre de forma interactiva.
3. Corre `databricks bundle validate` y `databricks bundle plan` en su computadora. Ninguno de los dos cambia nada.
4. Abre el pull request y revisa el plan que publica el CI.

Los notebooks escriben con `MERGE` por llave. Si alguien corre un notebook de prueba sobre las tablas compartidas, no duplica datos.

## Workflows de GitHub Actions

| Workflow | Cuándo corre | Qué hace |
|---|---|---|
| `bundle-plan.yml` | Pull request a `main` | `bundle validate` y `bundle plan -t prod`. Publica el plan como comentario desplegable y lo actualiza en cada push. Ya existe |
| `bundle-deploy.yml` | Merge a `main`, o a mano | `bundle validate` y `bundle deploy -t prod`. Ya existe |
| `tests.yml` | Pull request | Tests del paquete y test de "no empeorar" el Excel. Fase 2 |
| `run-pipeline.yml` | Merge a `main` que cambia el Excel del MEM | Dispara el job del pipeline para cargar el Excel nuevo. Fase 2 |
| `build-api.yml` | Merge a `main` que toca `serving/` | Construye la imagen de la API y la publica. Fase 6 |

GitHub Actions no transforma datos. Solo valida, despliega y dispara jobs. El procesamiento ocurre en Databricks.

**Secretos de GitHub**, en Settings, Secrets and variables, Actions:

| Secreto | Valor |
|---|---|
| `DATABRICKS_HOST` | URL del workspace, por ejemplo `https://dbc-xxxx.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | Token personal de Databricks. Ver [databricks.md](databricks.md) |

## Uso local

Requisito: la CLI de Databricks. Cada desarrollador se autentica una vez con OAuth:

```
databricks auth login --host <url_del_workspace>
```

| Comando | Para qué |
|---|---|
| `databricks bundle validate` | Revisar que la definición sea válida |
| `databricks bundle plan -t prod` | Ver qué cambiaría su rama en el ambiente compartido |
| `databricks bundle summary -t prod` | Ver qué está desplegado |
| `databricks catalogs list` | Listar catálogos |
| `databricks schemas list <catálogo>` | Listar esquemas |
| `databricks external-locations list` | Listar external locations |
| `databricks jobs list` | Listar jobs |

## Despliegue de la API en el Droplet

El Droplet lo provee el curso. Una persona del equipo tiene acceso por ssh con sudo. El proyecto no lo crea ni lo configura con código.

**Propuesta:**

1. El CI construye la imagen de Docker de la API y la publica en GitHub Container Registry.
2. La imagen incluye el modelo `champion` y la referencia de precios vigente. El Droplet no consulta Databricks en cada request.
3. Para actualizar el Droplet hay dos opciones:
   1. La persona con acceso corre un script que baja la imagen nueva y reinicia el contenedor.
   2. Esa persona agrega una llave de despliegue para que el CI lo haga por ssh. Requiere guardar `DROPLET_HOST` y `DROPLET_SSH_KEY` como secretos.

Se decide en la fase 6.

**Otras notas:**

1. El Droplet es pequeño. La imagen no debe incluir librerías pesadas como torch.
2. Para la foto como entrada, Tesseract sí se puede instalar dentro de la imagen de Docker.
3. Ambientes: uv para desarrollo local y Docker para el Droplet. La equivalencia con venv y conda se documenta como en el Taller 2.
