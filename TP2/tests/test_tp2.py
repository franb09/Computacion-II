import asyncio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app, RateLimiterPorCliente
from app.worker_manager import GestorTareas


@pytest_asyncio.fixture
async def cliente_async():
    gestor = GestorTareas(
        num_workers=2,
        max_cola=50,
        max_procesos_cpu=2,
        directorio_estado='/tmp',
        backoff_base=0.1,  # Backoff rápido para que los tests corran en milisegundos
    )
    app.state.gestor = gestor
    app.state.rate_limiter = RateLimiterPorCliente(max_peticiones=100, ventana_segundos=60.0)
    await gestor.iniciar()

    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url='http://test') as ac:
        yield ac

    await gestor.apagar(timeout_espera=2.0)


@pytest.mark.asyncio
async def test_crear_y_completar_esperar(cliente_async: AsyncClient):
    r = await cliente_async.post('/tareas', json={'tipo': 'esperar', 'segundos': 0.1})
    assert r.status_code == 201
    datos = r.json()
    assert datos['estado'] == 'pendiente'
    tid = datos['id']

    await asyncio.sleep(0.25)
    r2 = await cliente_async.get(f'/tareas/{tid}')
    assert r2.status_code == 200
    assert r2.json()['estado'] == 'completada'


@pytest.mark.asyncio
async def test_cancelar_tarea_en_ejecucion(cliente_async: AsyncClient):
    r = await cliente_async.post('/tareas', json={'tipo': 'esperar', 'segundos': 5.0})
    tid = r.json()['id']

    # Esperamos un instante 
    await asyncio.sleep(0.1)
    r_estado = await cliente_async.get(f'/tareas/{tid}')
    assert r_estado.json()['estado'] == 'ejecutando'

    # La cancelamos en vivo
    r_del = await cliente_async.delete(f'/tareas/{tid}')
    assert r_del.status_code == 200
    assert r_del.json()['estado'] == 'cancelada'

    # Verificamos que el estado final quedó como 'cancelada' y liberó al worker
    await asyncio.sleep(0.05)
    r_final = await cliente_async.get(f'/tareas/{tid}')
    assert r_final.json()['estado'] == 'cancelada'

    stats = (await cliente_async.get('/estadisticas')).json()
    assert stats['workers_ocupados'] == 0


@pytest.mark.asyncio
async def test_timeout_tarea(cliente_async: AsyncClient):
    r = await cliente_async.post(
        '/tareas',
        json={'tipo': 'esperar', 'segundos': 3.0, 'timeout': 0.15},
    )
    tid = r.json()['id']

    await asyncio.sleep(0.35)
    r_final = await cliente_async.get(f'/tareas/{tid}')
    datos = r_final.json()
    assert datos['estado'] == 'fallida'
    assert 'Timeout' in datos['error']


@pytest.mark.asyncio
async def test_reintentos_con_backoff_exponencial(cliente_async: AsyncClient):
    r = await cliente_async.post(
        '/tareas',
        json={
            'tipo': 'esperar',
            'segundos': 1.0,
            'timeout': 0.08,
            'max_reintentos': 2,  # 1 intento inicial + 2 reintentos = 3 intentos totales
        },
    )
    tid = r.json()['id']

    await asyncio.sleep(0.8)
    r_final = await cliente_async.get(f'/tareas/{tid}')
    datos = r_final.json()
    assert datos['estado'] == 'fallida'
    assert datos['intentos_realizados'] == 3


@pytest.mark.asyncio
async def test_cola_con_prioridades():
    gestor = GestorTareas(num_workers=1, max_cola=20, directorio_estado='/tmp')
    await gestor.iniciar()

    try:
        t1 = await gestor.encolar(
            app_model_helper(tipo='esperar', segundos=0.2, prioridad=3)
        )
        await asyncio.sleep(0.03)  # El worker 0 ya está ocupado con t1

        t_baja = await gestor.encolar(
            app_model_helper(tipo='esperar', segundos=0.05, prioridad=1)
        )
        t_alta = await gestor.encolar(
            app_model_helper(tipo='esperar', segundos=0.05, prioridad=5)
        )

        await asyncio.sleep(0.45)
        info_baja = gestor.obtener_tarea(t_baja['id'])
        info_alta = gestor.obtener_tarea(t_alta['id'])

        assert info_alta['iniciada_en'] < info_baja['iniciada_en']
    finally:
        await gestor.apagar(timeout_espera=1.0)


@pytest.mark.asyncio
async def test_rate_limiting_y_metricas_prometheus(cliente_async: AsyncClient):
    r_met = await cliente_async.get('/metricas')
    assert r_met.status_code == 200
    assert 'tareas_total{estado="pendiente"}' in r_met.text
    assert 'workers_totales' in r_met.text

    app.state.rate_limiter = RateLimiterPorCliente(max_peticiones=2, ventana_segundos=60.0)
    r1 = await cliente_async.post('/tareas', json={'tipo': 'esperar', 'segundos': 0.1})
    r2 = await cliente_async.post('/tareas', json={'tipo': 'esperar', 'segundos': 0.1})
    r3 = await cliente_async.post('/tareas', json={'tipo': 'esperar', 'segundos': 0.1})

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r3.status_code == 429


def app_model_helper(**kwargs):
    from app.models import TareaNueva
    return TareaNueva(**kwargs)