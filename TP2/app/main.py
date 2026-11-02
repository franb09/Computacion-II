from collections import defaultdict, deque
from contextlib import asynccontextmanager
import os
import time
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from app.models import (
    EstadoTarea,
    EstadisticasRespuesta,
    TareaNueva,
    TareaRespuesta,
)
from app.worker_manager import GestorTareas


class RateLimiterPorCliente:
    """Limita la cantidad de tareas creadas por IP en una ventana deslizante de tiempo."""

    def __init__(self, max_peticiones: int = 120, ventana_segundos: float = 60.0):
        self.max_peticiones = max_peticiones
        self.ventana_segundos = ventana_segundos
        self.historial: dict[str, deque[float]] = defaultdict(deque)

    def verificar(self, cliente_ip: str, limite_override: int | None = None) -> bool:
        ahora = time.monotonic()
        cola_tiempos = self.historial[cliente_ip]
        limite = limite_override if limite_override is not None else self.max_peticiones

        while cola_tiempos and (ahora - cola_tiempos[0]) > self.ventana_segundos:
            cola_tiempos.popleft()

        if len(cola_tiempos) >= limite:
            return False

        cola_tiempos.append(ahora)
        return True


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Inicializa el pool de workers al arrancar y ejecuta el apagado ordenado al recibir SIGINT/SIGTERM."""
    num_workers = int(os.getenv('NUM_WORKERS', '4'))
    max_cola = int(os.getenv('MAX_COLA', '200'))
    max_procesos_cpu = int(os.getenv('MAX_PROCESOS_CPU', '2'))
    directorio_estado = os.getenv('DIRECTORIO_ESTADO', '.')
    rate_limit_max = int(os.getenv('RATE_LIMIT_MAX', '120'))
    rate_limit_ventana = float(os.getenv('RATE_LIMIT_VENTANA', '60.0'))

    gestor = GestorTareas(
        num_workers=num_workers,
        max_cola=max_cola,
        max_procesos_cpu=max_procesos_cpu,
        directorio_estado=directorio_estado,
    )
    app.state.gestor = gestor
    app.state.rate_limiter = RateLimiterPorCliente(
        max_peticiones=rate_limit_max,
        ventana_segundos=rate_limit_ventana,
    )
    await gestor.iniciar()
    yield
    await gestor.apagar(timeout_espera=10.0)


app = FastAPI(
    title='Plataforma de Tareas Distribuidas - TP2',
    description='API HTTP asíncrona con PriorityQueue, Reintentos, WebSocket, Rate Limiting y Prometheus',
    lifespan=ciclo_de_vida,
)


@app.get('/')
async def raiz():
    return {
        'servicio': 'plataforma_tareas_tp2',
        'docs': '/docs',
        'metricas': '/metricas',
        'websocket': '/eventos',
    }


@app.post('/tareas', response_model=TareaRespuesta, status_code=201)
async def crear_tarea(
    nueva: TareaNueva,
    request: Request,
    bloquear_loop: bool = Query(
        default=False,
        description='Solo para Medición 2: si es True, ejecuta hashear sin run_in_executor',
    ),
):
    """Encola una tarea verificando primero el Rate Limit del cliente."""
    gestor: GestorTareas = request.app.state.gestor
    limiter: RateLimiterPorCliente = request.app.state.rate_limiter

    cliente_ip = request.client.host if request.client else 'desconocido'
    if not limiter.verificar(cliente_ip):
        raise HTTPException(
            status_code=429,
            detail='Rate limit excedido: demasiadas tareas enviadas desde este cliente.',
        )

    try:
        tarea = await gestor.encolar(nueva, bloquear_loop=bloquear_loop)
        return tarea
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get('/tareas', response_model=list[TareaRespuesta])
async def listar_tareas(
    request: Request,
    estado: EstadoTarea | None = Query(default=None, description='Filtrar por estado'),
):
    gestor: GestorTareas = request.app.state.gestor
    return gestor.listar_tareas(estado=estado)


@app.get('/tareas/{tarea_id}', response_model=TareaRespuesta)
async def obtener_tarea(tarea_id: int, request: Request):
    gestor: GestorTareas = request.app.state.gestor
    try:
        return gestor.obtener_tarea(tarea_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='No existe esa tarea')


@app.delete('/tareas/{tarea_id}')
async def cancelar_tarea(tarea_id: int, request: Request):
    gestor: GestorTareas = request.app.state.gestor
    try:
        resultado = await gestor.cancelar_tarea(tarea_id)
        return {
            'id': tarea_id,
            'estado': 'cancelada',
            'detalle': resultado,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail='No existe esa tarea')
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get('/estadisticas', response_model=EstadisticasRespuesta)
async def obtener_estadisticas(request: Request):
    gestor: GestorTareas = request.app.state.gestor
    return gestor.obtener_estadisticas()


@app.get('/metricas', response_class=PlainTextResponse)
async def obtener_metricas_prometheus(request: Request):
    """Bonus 5: Endpoint de métricas en formato Prometheus."""
    gestor: GestorTareas = request.app.state.gestor
    return gestor.generar_metricas_prometheus()


@app.websocket('/eventos')
async def websocket_eventos(ws: WebSocket):
    """Bonus 1: WebSocket para notificar cambios de estado de las tareas en tiempo real."""
    gestor: GestorTareas = ws.app.state.gestor
    await gestor.conectar_ws(ws)
    try:
        while True:
            # Mantenemos la conexión abierta esperando mensajes o desconexión del cliente
            await ws.receive_text()
    except WebSocketDisconnect:
        gestor.desconectar_ws(ws)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)