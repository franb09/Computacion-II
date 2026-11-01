from contextlib import asynccontextmanager
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request

from app.models import (
    EstadoTarea,
    EstadisticasRespuesta,
    TareaNueva,
    TareaRespuesta,
)
from app.worker_manager import GestorTareas


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Inicializa el pool de workers al arrancar y ejecuta el apagado ordenado al recibir SIGINT/SIGTERM."""
    num_workers = int(os.getenv('NUM_WORKERS', '4'))
    max_cola = int(os.getenv('MAX_COLA', '100'))
    max_procesos_cpu = int(os.getenv('MAX_PROCESOS_CPU', '2'))
    directorio_estado = os.getenv('DIRECTORIO_ESTADO', '.')

    gestor = GestorTareas(
        num_workers=num_workers,
        max_cola=max_cola,
        max_procesos_cpu=max_procesos_cpu,
        directorio_estado=directorio_estado,
    )
    app.state.gestor = gestor
    await gestor.iniciar()
    yield
    # Al recibir SIGINT o SIGTERM, Uvicorn sale del yield y ejecuta el apagado limpio:
    await gestor.apagar(timeout_espera=10.0)


app = FastAPI(
    title='Plataforma de Tareas Distribuidas - TP2',
    description='API HTTP asíncrona con pool de workers y ProcessPoolExecutor (Computación II)',
    lifespan=ciclo_de_vida,
)


@app.get('/')
async def raiz():
    """Endpoint informativo base (estilo Clase 19)."""
    return {'servicio': 'plataforma_tareas_tp2', 'docs': '/docs'}


@app.post('/tareas', response_model=TareaRespuesta, status_code=201)
async def crear_tarea(
    nueva: TareaNueva,
    request: Request,
    bloquear_loop: bool = Query(
        default=False,
        description='Solo para Medición 2: si es True, ejecuta hashear sin run_in_executor',
    ),
):
    """Encola una tarea y responde inmediatamente (201 Created) con su ID y estado inicial."""
    gestor: GestorTareas = request.app.state.gestor
    try:
        # Si la cola está llena, esperamos como máximo 1s antes de rechazar con 503 (backpressure)
        tarea = await gestor.encolar(nueva, bloquear_loop=bloquear_loop)
        return tarea
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get('/tareas', response_model=list[TareaRespuesta])
async def listar_tareas(
    request: Request,
    estado: EstadoTarea | None = Query(default=None, description='Filtrar por estado'),
):
    """Lista todas las tareas, con filtro opcional por estado."""
    gestor: GestorTareas = request.app.state.gestor
    return gestor.listar_tareas(estado=estado)


@app.get('/tareas/{tarea_id}', response_model=TareaRespuesta)
async def obtener_tarea(tarea_id: int, request: Request):
    """Devuelve el estado actual y el resultado (si terminó) de una tarea."""
    gestor: GestorTareas = request.app.state.gestor
    try:
        return gestor.obtener_tarea(tarea_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='No existe esa tarea')


@app.delete('/tareas/{tarea_id}')
async def cancelar_tarea(tarea_id: int, request: Request):
    """Cancela una tarea que esté encolada (pendiente) o en curso (ejecutando)."""
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
    """Devuelve totales por estado, tiempo promedio de ejecución y workers ocupados."""
    gestor: GestorTareas = request.app.state.gestor
    return gestor.obtener_estadisticas()


# Guarda obligatoria (Sección 4.1 de la consigna) para evitar bucle de reimportación con spawn
if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)