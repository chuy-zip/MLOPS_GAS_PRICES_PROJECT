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
2. **El bundle tiene un solo destino**, `prod`. Sus archivos y su estado viven en `/Workspace/Shared/.bundle/gas_price/prod`, visibles para todo el equipo. El grupo `users` tiene `CAN_MANAGE` sobre los jobs, declarado en `databricks.yml`. Solo se suben los notebooks, el código de `src/` y la configuración: `docs/`, `data/`, `.github/`, `tests/`, `infra/` y `scripts/` quedan fuera con `sync.exclude`.
3. **Los cambios llegan por pull request.** Un ruleset de GitHub sobre `main` exige que el check `plan` esté en verde para hacer merge. También exige el check `tests`. No exige aprobaciones.
4. **Un despliegue a la vez:** el workflow de despliegue usa `concurrency` de GitHub Actions para no correr dos despliegues juntos.
5. **Una corrida a la vez:** los jobs tienen `max_concurrent_runs: 1`. Si dos personas lanzan el mismo job, la segunda corrida espera. Ayuda también con el límite de 5 tareas de Free Edition.

No se usa el modo producción de los bundles. Según la [documentación de modos de despliegue](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes), ese modo exige que la rama actual coincida con `main`, y el plan de los pull requests corre en otra rama.

## Cómo prueba un cambio un desarrollador

**Configuración, una sola vez por persona:**

1. Ser colaborador del repo en GitHub, con permiso de escritura.
2. En Databricks: clic en el usuario, **Settings**, **Linked accounts**, **Add Git credential**, proveedor **GitHub**, **Link Git account**.
3. Clonar el repo en su carpeta: **Workspace**, su carpeta de usuario, **Create**, **Git folder**, URL `https://github.com/chuy-zip/MLOPS_GAS_PRICES_PROJECT.git`.

La app de Databricks en GitHub ya está instalada en el repo. Eso lo hace una sola vez el dueño del repo. Fuente: [credenciales de Git](https://docs.databricks.com/aws/en/repos/get-access-tokens-from-git-provider).

**Ciclo de trabajo:**

1. En el notebook, clic en el botón con el nombre de la rama y **Create Branch**.
2. Editar y correr de forma interactiva solo las celdas que se están probando.
3. Cuando funcione, en el mismo diálogo de Git: mensaje y **Commit & Push**.
4. Abrir el pull request en GitHub y revisar el plan que publica el CI.
5. Después del merge, correr el job del pipeline para que las tablas queden como las deja el código de `main`.

**Dónde se edita cada cosa:**

| Qué | Dónde | Por qué |
|---|---|---|
| Notebooks | Carpeta Git en Databricks, con commit y push desde ahí | Ahí se corren contra los datos reales |
| Documentación, `databricks.yml`, workflows, paquete de Python y tests | En la computadora, con git | No necesitan los datos para probarse |

Un mismo archivo no se edita en los dos lugares a la vez. Antes de empezar a editar, hacer pull de la rama: en Databricks con el diálogo de Git, en la computadora con `git pull`.

**No desplegar desde Databricks.** Al abrir un notebook de la carpeta Git aparece el aviso "This file is part of a bundle. Switch to associated bundle". La vista del bundle tiene un botón para desplegar. No se usa: el único destino es `prod`, y desplegar desde una rama pondría código sin revisar en el ambiente compartido.

**Tablas compartidas.** No hay esquemas por persona. Las pruebas escriben sobre los esquemas de `gas_price`, por eso cada tabla tiene un solo responsable a la vez, asignado en el plan. Los notebooks escriben con `MERGE` por llave, así que repetir una prueba no duplica datos.

## Workflows de GitHub Actions

| Workflow | Cuándo corre | Qué hace |
|---|---|---|
| `bundle-plan.yml` | Pull request a `main` | `bundle validate` y `bundle plan -t prod`. Publica el plan como comentario desplegable y lo actualiza en cada push. Ya existe |
| `bundle-deploy.yml` | Merge a `main`, o a mano | `bundle validate` y `bundle deploy -t prod`. Ya existe |
| `tests.yml` | Pull request a `main` | Tests del paquete `gas_price` y test de "no empeorar" los archivos de `data/` contra la versión de `main`. Ya existe |
| `run-pipeline.yml` | Merge a `main` que cambia algo en `data/` | Dispara el job del pipeline para cargar los datos nuevos. Fase 2 |
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
2. Si da tiempo de aceptar fotos como entrada, Tesseract sí se puede instalar dentro de la imagen de Docker.
3. Ambientes: uv para desarrollo local y Docker para el Droplet. La equivalencia con venv y conda se documenta como en el Taller 2.
