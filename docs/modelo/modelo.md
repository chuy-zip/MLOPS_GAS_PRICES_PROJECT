# Modelo

El caso de uso tiene dos preguntas distintas. Cada una se resuelve con el método que mejor le queda.

## "¿Es un buen precio?"

Se responde comparando el precio del usuario contra la referencia oficial del mismo día y combustible. El resultado es la diferencia en quetzales y si cae dentro del rango normal entre estaciones.

No necesita un modelo de ML porque la referencia oficial ya existe y es exacta. Entrenar un modelo para estimar algo que el MEM publica sería agregar error sin ganar nada.

El rango normal parte del análisis de negocio: de Q0.50 a Q1.00 por galón entre estaciones. Si las fotos llegan a dar precios por estación, el rango se puede calcular con esos datos.

## "¿Va a subir o a bajar?"

Se resuelve con un modelo de clasificación. Predice si el próximo cambio de precio será una subida, una baja o si el precio se mantendrá.

**Por qué no basta una línea de tendencia.** Una línea de tendencia solo extiende hacia adelante lo que pasó antes. Si el precio viene subiendo, siempre dirá que va a seguir subiendo. Los precios de combustible suben y bajan en saltos semanales que siguen al mercado internacional y al tipo de cambio. Un modelo de ML aprende de varias señales a la vez y puede anticipar cambios de dirección.

**Por qué clasificación.** La decisión del usuario es discreta: cargar hoy o esperar. Eso responde a los objetivos O1 y O2 del análisis de negocio. Además, el modelo entrega una probabilidad, por ejemplo "es probable que baje (70 %)".

## Horizonte: ¿esperar cuánto?

El precio de referencia del MEM cambia una vez por semana. En los datos, la mayoría de los cambios caen en lunes. Entre un cambio y el siguiente el precio no se mueve.

Por eso "esperar" significa **esperar al próximo cambio de referencia**, que llega en 7 días o menos. El modelo responde: "si esperas al próximo cambio, ¿el precio será más alto, más bajo o igual que hoy?".

| Día de la consulta | Próximo cambio | Respuesta del sistema |
|---|---|---|
| Martes 10 | Lunes 16 | Dirección del cambio del lunes 16, a 6 días |
| Domingo 15 | Lunes 16 | Dirección del cambio del lunes 16, a 1 día |

La API también devuelve cuántos días faltan para el próximo cambio. Así el usuario decide si puede esperar con el combustible que tiene.

Antes de entrenar hay que confirmar con los datos qué día de la semana se toma como cambio. Si hay semanas con dos cambios o sin cambio, la semana se cuenta igual: la etiqueta compara el precio al inicio de la semana siguiente contra el precio de hoy.

## Datos de entrenamiento

1. **Fuente:** `gold.features_semanales`, construida a partir del Excel del MEM.
2. **Granularidad:** una fila por semana y combustible.
3. **Etiqueta:** dirección del cambio entre esta semana y la siguiente. Un cambio menor a Q0.10 cuenta como "se mantiene". El umbral se revisa con los datos.
4. **Variables candidatas:** cambios de las 1 a 4 semanas anteriores, tendencia de 4 y 8 semanas, cambio del tipo de cambio, régimen fiscal y mes.

## Cómo se evalúa

1. **Partición temporal:** se entrena con el pasado y se evalúa con el futuro. Nunca partición aleatoria, porque filtraría información del futuro.
2. **Métricas reportadas:** F1 macro y balanced accuracy, porque las clases pueden estar desbalanceadas. Se reportan para conocer el desempeño, no son un requisito que el modelo deba cumplir.
3. **Candidatos:** regresión logística y Gradient Boosting, como en la Actividad 1.

## Registro

Igual que en el Ejercicio 5: MLflow con autolog, firma del modelo, registro en Unity Catalog como `modelo_tendencia_precio` en el esquema de oro y alias `champion` para la versión que usa la API.
