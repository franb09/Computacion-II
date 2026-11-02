# Trabajo Práctico Nº 2: Plataforma de Tareas Distribuidas

**Alumno:** Franco Luciano Berardo
**- Materia:** Computación II 
---

## 1. Descripción General
Este proyecto es una plataforma de tareas distribuidas que recibe trabajos por HTTP, los encola y los procesa de forma concurrente usando un único hilo con `asyncio`. La API está expuesta con FastAPI y permite mandar a ejecutar tres tipos de tareas bien distintas: descargas de red (`descargar`), cálculo intensivo de hashes (`hashear`) y esperas simuladas (`esperar`). Además, permite consultar el estado de cada tarea en vivo, cancelarlas aunque ya estén corriendo, ver estadísticas del servidor y guardar el estado en un archivo JSON cuando el servicio se apaga.

El sistema está completamente dockerizado y no requiere pasos manuales adicionales. Desde la carpeta `TP2/`, hay que ejecutar:

```bash
docker compose up --build
```

La API va a estar disponible en `http://localhost:8000` (y su documentación interactiva OpenAPI/Swagger en `http://localhost:8000/docs`).

Para apagar el sistema de forma ordenada (disparando `SIGINT`/`SIGTERM`, esperando las tareas en curso y generando el volcado `estado_<timestamp>.json`), presionar `Ctrl+C` o ejecutar en otra terminal:

```bash
docker compose down
```

---


### Ejemplos de prueba con `curl`

**1. Encolar una tarea I/O simulada (`esperar`):**
```bash
curl -X POST http://localhost:8000/tareas \
     -H "Content-Type: application/json" \
     -d '{"tipo": "esperar", "segundos": 5, "prioridad": 3, "timeout": 10}'
```

**2. Encolar una tarea I/O-bound real (`descargar` múltiples URLs concurrentemente):**
```bash
curl -X POST http://localhost:8000/tareas \
     -H "Content-Type: application/json" \
     -d '{
           "tipo": "descargar",
           "urls": ["https://example.com", "https://www.python.org", "https://httpbin.org/get"],
           "prioridad": 5,
           "max_reintentos": 2
         }'
```

**3. Encolar una tarea CPU-bound (`hashear` con SHA-256 iterado):**
```bash
curl -X POST http://localhost:8000/tareas \
     -H "Content-Type: application/json" \
     -d '{"tipo": "hashear", "texto": "computacion2", "iteraciones": 3000000, "prioridad": 2}'
```

**4. Listar todas las tareas (o filtrar por estado):**
```bash
curl http://localhost:8000/tareas
curl "http://localhost:8000/tareas?estado=completada"
```

**5. Consultar el estado y resultado de una tarea específica:**
```bash
curl http://localhost:8000/tareas/1
```

**6. Cancelar una tarea encolada o en ejecución:**
```bash
curl -X DELETE http://localhost:8000/tareas/1
```

**7. Consultar estadísticas generales del sistema:**
```bash
curl http://localhost:8000/estadisticas
```

**8. Consultar métricas en formato Prometheus (Bonus):**
```bash
curl http://localhost:8000/metricas
```

**9. Ejecutar la suite de tests automatizados (`pytest-asyncio`) y los benchmarks:**
```bash
docker compose exec api python -m pytest -v
docker compose exec api python benchmarks.py
```

---


## 2. Diagrama de Arquitectura

La arquitectura separa la recepción de los pedidos HTTP de la ejecución real usando una cola en memoria y un pool de workers asíncronos, derivando el trabajo pesado de CPU a procesos aparte para no frenar el servidor.

```text
                             [Cliente HTTP / WS]
                                      │
┌─────────────────────────────────────▼─────────────────────────────────────┐
│                               API (FastAPI)                               │
│                                                                           │
│  POST /tareas  |  GET /tareas  |  DELETE /tareas/{id}  |  GET /metricas   │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │ (Encola sin bloquear)
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                   COLA DE TAREAS (asyncio.PriorityQueue)                  │
│                                                                           │
│  - Tuplas: (peso_con_aging, orden_llegada, tarea_id)                      │
│  - Límite de capacidad (maxsize=200) para control de flujo                │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │ (Consumen N corrutinas)
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         POOL DE WORKERS ASÍNCRONOS                        │
│                                                                           │
│  - Control de Timeouts (asyncio.timeout)                                  │
│  - Cancelación en vivo (sub_task.cancel) y Reintentos (Backoff)           │
└──┬──────────────────────────────────┬──────────────────────────────────┬──┘
   │                                  │                                  │
   ▼                                  ▼                                  ▼
[esperar]                        [descargar]                         [hashear]
(asyncio.sleep)            (httpx + asyncio.gather)            (ProcessPoolExecutor)
```

---

## 3. Decisiones de Diseño Argumentadas

¿Por qué asyncio.Queue y no queue.Queue?
Se optó por la cola de `asyncio` porque `queue.Queue` está pensada para threads comunes y bloquea a nivel de sistema operativo. Si un worker hiciera `queue.get()` cuando no hay tareas, dormiría al hilo entero donde corre el event loop y colgaría toda la API de FastAPI. Con `asyncio.PriorityQueue`, el `await cola.get()` solo pausa esa corrutina en particular y deja libre al loop para seguir atendiendo pedidos HTTP.

¿Por qué httpx y no requests para las descargas?
Porque `requests` es sincrónica. Si metemos un `requests.get()` adentro de una corrutina, hasta que el servidor externo no conteste, el event loop se queda clavado esperando el socket. En cambio, `httpx.AsyncClient` trabaja de forma asíncrona con `await`, y además creamos una sola instancia al arrancar el servidor para reutilizar las conexiones TCP (keep-alive) en vez de abrir y cerrar un cliente por cada URL.

¿Cómo evitás que una tarea CPU-bound congele la API?
El event loop corre en un solo hilo y recién cambia de tarea cuando choca con un `await`. La tarea `hashear` hace millones de pasadas de SHA-256 seguidas sin hacer I/O, así que no cede nunca el control. Para que no congele todo, la sacamos del loop usando `loop.run_in_executor()` con un `ProcessPoolExecutor`. Usamos procesos en lugar de threads (`to_thread`) porque en Python el GIL impide que varios threads ejecuten bytecode de CPU al mismo tiempo; con procesos separados sí logramos paralelismo real en distintos núcleos.

¿Cómo implementaste la cancelación, y qué pasa con los recursos a medio usar?
Si la tarea todavía está `pendiente` en la cola, simplemente le cambiamos el estado a `cancelada` en el diccionario; cuando a un worker le toque sacarla, ve que ya está cancelada y la saltea. 
El tema es cuando ya está `ejecutando`. Para no cancelar al worker entero (porque perderíamos un worker del pool), el worker lanza cada trabajo adentro de una sub-tarea (`asyncio.create_task`) y guarda la referencia en un diccionario `tareas_activas`. Al pegarle a `DELETE /tareas/{id}`, buscamos esa sub-tarea y le tiramos `.cancel()`. Eso inyecta un `CancelledError` en el próximo `await` (por ejemplo, a mitad de una descarga de `httpx`). Los bloques `finally` internos de `httpx` cierran la conexión de red limpia sin dejar sockets colgados, y nuestro worker atrapa la excepción, marca la tarea como `cancelada` y sigue vivo para agarrar la siguiente.

¿Qué pasa si un worker lanza una excepción no capturada?
Si una tarea falla por cualquier motivo y no capturamos el error adentro del `while True` del worker, esa corrutina se muere en silencio y nos vamos quedando sin workers. Además, si se saltea el `cola.task_done()`, el contador de la cola queda mal y el apagado con `join()` se colgaría para siempre. Por eso envolvimos la ejecución en un `try/except Exception` que pasa la tarea al estado `fallida` guardando el motivo del error, y pusimos el `cola.task_done()` y el descuento de `workers_ocupados` adentro de un `finally` que corre siempre pase lo que pase.

¿Por qué el pool de workers no necesita un Lock?
A diferencia de cuando trabajábamos con threads en la primera parte de la materia, acá todas las corrutinas corren en el mismo hilo. El cambio de contexto no pasa en cualquier instrucción del procesador, sino únicamente donde hay un `await`. Como cuando leemos o modificamos el diccionario `self.tareas` o sumamos `self.workers_ocupados += 1` no hay ningún `await` en el medio, nadie nos puede pisar los datos a mitad de camino.

---

## 4. Mediciones Obligatorias

Para no estimar a ojo, armé el script `benchmarks.py` que le pega directo a la API corriendo en Docker y toma los tiempos reales en mi máquina.

### 1. Concurrencia I/O (20 descargas secuenciales vs 20 concurrentes)
Se probaron 20 descargas contra `https://example.com`, primero mandándolas una por una esperando a que termine la anterior, y después mandando las 20 juntas en una sola tarea que por dentro usa `asyncio.gather`.

| Prueba | Tiempo Total | Speedup |
|---|---|---|
| 20 descargas secuenciales | 4.27210 s | 1.0x |
| 20 descargas concurrentes (`gather`) | 0.62857 s (percibido: 0.64425 s) | **6.80x** |

En el caso secuencial (que sería como poner un `await` adentro de un `for`), los tiempos de red se suman uno atrás del otro y se va a más de 4 segundos. Con `gather`, las 20 peticiones salen juntas y se quedan esperando la red al mismo tiempo, por lo que el lote entero tarda prácticamente lo mismo que la descarga más lenta (0.62 s), casi 7 veces más rápido.

### 2. El Event Loop Bloqueado (CPU-bound sin executor vs con executor)
Lancé una tarea `hashear` pesada con 4.000.000 de iteraciones de SHA-256 (que tarda unos 2.28 segundos de CPU) y en el medio tiré un `GET /tareas` para medir cuánto tardaba en contestar la API.

| Modo de ejecución de `hashear` | Tiempo del cálculo CPU | Tiempo de respuesta de `GET /tareas` |
|---|---|---|
| Sin `run_in_executor` (en el loop) | 2.28413 s | **2265.62 ms** (congelado) |
| Con `ProcessPoolExecutor` | 2.27373 s | **6.60 ms** (libre) |

Acá se ve clarísimo el punto central de la materia. Cuando corrés el hash directo en la corrutina, como no hay ningún `await`, el servidor entero se clava durante los 2.28 segundos que dura el bucle: el simple `GET /tareas` tarda 2265 ms porque tuvo que esperar a que termine todo el hash para poder entrar. Cuando lo mandamos al `ProcessPoolExecutor`, el cálculo tarda lo mismo (2.27 s), pero corre en otro proceso; el event loop queda libre y contesta el `GET /tareas` en 6.6 ms (unas 343 veces más rápido).

### 3. Techo del Pool
Subí de a poco la cantidad de tareas mandadas de golpe para ver dónde empiezan a degradarse los tiempos, tanto en I/O (con un pool de 4 workers) como en CPU (con un pool de 2 procesos).

**Tareas I/O (`esperar` de 0.5s cada una, con 4 workers):**

| Cantidad de tareas | Tiempo total | Promedio por tarea en el lote |
|---|---|---|
| 2 | 0.52085 s | 0.26042 s |
| 4 | 0.53291 s | 0.13323 s |
| 8 | 1.03396 s | 0.12924 s |
| 16 | 2.04155 s | 0.12760 s |
| 32 | 4.03720 s | 0.12616 s |

**Tareas CPU-bound (`hashear` de 1.500.000 iteraciones, con 2 procesos):**

| Cantidad de tareas | Tiempo total | Tiempo por tarea |
|---|---|---|
| 1 | 0.84665 s | 0.84665 s |
| 2 | 0.93782 s | 0.46891 s |
| 4 | 1.79069 s | 0.44767 s |
| 8 | 3.61230 s | 0.45154 s |

En las tareas de espera se ve que el techo lo pone la cantidad de workers configurados (4). Hasta 4 tareas tardan medio segundo en total porque entran todas juntas. Cuando mandás 8, 16 o 32, como hay 4 workers, se arman tandas y el tiempo sube en escalones clavados de a 0.5s (1s, 2s, 4s).
En las de CPU, por más que haya 4 workers asíncronos, el techo real lo ponen los 2 procesos del `ProcessPoolExecutor`. Pasar de 1 a 2 tareas casi no sube el tiempo total (de 0.84s a 0.93s) porque trabajan dos núcleos en paralelo, pero con 4 y 8 tareas los dos procesos quedan al tope y el tiempo se duplica linealmente.

---

## 5. Conceptos del Curso Aplicados

Productor-Consumidor y Colas (Clase 11 y 21): El pool de workers consume de una cola compartida igual que hacíamos con threads en la clase 11, pero usando corrutinas. Además se configuró `maxsize=200` en la cola para aplicar backpressure: si un cliente manda miles de tareas de golpe y llena la cola, el productor se frena en vez de comer toda la memoria RAM.

Multiplexing, Corrutinas y Event Loop (Clase 17, 18 y 20): Se aplicó la idea de que un solo hilo vigilando eventos puede manejar decenas de conexiones concurrentes sin el gasto de memoria de crear un thread por cliente. También se aplicó la diferencia entre usar `time.sleep()` (que es un bug en async porque duerme al hilo del sistema operativo) y `asyncio.sleep()` (que suspende solo la corrutina).

Procesos vs Threads y el GIL (Clase 8, 9, 10 y 21): Para las tareas `hashear` se aplicó un pool de procesos en lugar de hilos para esquivar el GIL de Python. También se protegió el punto de entrada en `main.py` con `if __name__ == '__main__':` para evitar bucles de reimportación en sistemas que usan `spawn`.

Señales y Apagado Ordenado (Clase 6, 20 y 21): Al recibir `SIGINT` o `SIGTERM`, el servidor deja de aceptar tareas nuevas y usa el patrón del objeto centinela (`CENTINELA = object()`) visto en la clase 21. Se mete un centinela por cada worker en la cola para que terminen la tarea que tenían en curso antes de apagarse, y recién ahí se vuelca todo el estado al archivo `estado_<timestamp>.json`.

---

## 6. Extensiones Opcionales (Bonus)

Una vez que anduvo la base obligatoria, agregué 6 de los bonus propuestos:

1. **Prioridades y cómo evitar la inanición:** La cola usa `asyncio.PriorityQueue` con prioridades del 1 (más baja) al 5 (más alta). Para que no dé `TypeError` al desempatar tareas con la misma prioridad, se guardan tuplas `(peso, contador_fifo, id)`. El problema de las colas con prioridad es la inanición: si entran tareas de prioridad 5 todo el tiempo, una de prioridad 1 no sale nunca. Lo resolví agregando envejecimiento (aging) al calcular el peso: `peso = -prioridad - (tiempo_espera * 0.05)`. Como `PriorityQueue` saca primero el número más negativo, a medida que pasan los segundos las tareas viejas de prioridad baja van sumando peso negativo y terminan pasando adelante de las nuevas.
2. **Reintentos con backoff exponencial:** Al crear una tarea se le puede pasar `max_reintentos`. Si falla o da timeout, el worker no la descarta de una, sino que espera `0.5 * (2 ** (intento - 1))` segundos con `asyncio.sleep` y vuelve a probar. Si la tarea fue cancelada con `DELETE`, no se reintenta.
3. **WebSocket `/eventos`:** Permite conectarse por WebSocket y recibir un JSON en vivo cada vez que una tarea se encola, arranca, reintenta, termina o se cancela.
4. **Rate limiting:** Tiene un filtro por IP con una ventana de tiempo en memoria (`deque`). Si un mismo cliente manda más tareas por minuto del límite permitido, le devuelve `429 Too Many Requests`.
5. **Métricas en formato Prometheus:** En `GET /metricas` devuelve el texto plano con el formato estándar de Prometheus (`# HELP` y `# TYPE gauge`) con los totales por estado, workers ocupados y tamaño de la cola.
6. **Tests con `pytest-asyncio`:** En `tests/test_tp2.py` armé 6 tests automáticos que prueban el ciclo completo de una tarea, la cancelación cuando está a mitad de ejecución, el corte por timeout, los reintentos con backoff, el orden de prioridades y el rate limiting.

---

## 7. Limitaciones Conocidas

Volcado JSON solo informativo al reiniciar: Cuando el servidor se apaga guarda todo el estado en `estado_<timestamp>.json` y cuando vuelve a arrancar detecta el archivo y avisa por consola cuántas tareas había, pero no vuelve a meter en la cola las que habían quedado pendientes (ya que por consigna el estado vive en memoria sin base de datos).

Cancelación de un hash que ya entró al proceso hijo: Si cancelás una tarea `esperar` o `descargar`, se corta al instante porque están pausadas en un `await`. Pero si cancelás un `hashear` pesado que ya se mandó al `ProcessPoolExecutor`, la API te la marca como `cancelada` enseguida y libera al worker, pero el proceso hijo de fondo termina de dar las vueltas del `for` de SHA-256 porque está corriendo código sincrónico en otro proceso.

---


## 8. Lo que aprendí en este TP

Hacer este trabajo me sirvió mucho para entender como funciona `asyncio` de verdad. Durante las clases entendía la idea del event loop y las corrutinas, pero recién cuando armé el pool de workers consumiendo de la cola y vi que con un solo hilo podía bajar 20 páginas web casi 7 veces más rápido que haciéndolo de forma secuencial me cayó la ficha de por qué no hace falta abrir 20 threads para esperar la red.

Lo que más me llamó la atención fue cuando corrí la segunda medición. Sabía por teoría que no había que meter cálculos pesados adentro de una función `async def`, pero ver en los números que poner a calcular un hash sin `run_in_executor` clavaba un simple `GET /tareas` durante más de 2 segundos fue re claro. Ahí terminé de conectar por qué `asyncio` sirve para I/O y por qué para CPU sí o sí hay que apoyarse en procesos aparte con `ProcessPoolExecutor` para esquivar el GIL.

También aprendí a tener cuidado con los detalles de limpieza cuando se trabaja con concurrencia: acordarse siempre del `cola.task_done()` adentro de un `finally` para no colgar la cola si algo falla, usar centinelas para apagar los workers sin dejar tareas por la mitad, y separar cada ejecución en una sub-tarea para poder cancelar un trabajo puntual sin matar al worker que lo está corriendo.

***