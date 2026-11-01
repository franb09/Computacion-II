#!/usr/bin/env python3
"""Script para ejecutar las 3 mediciones obligatorias del TP2 contra la API en vivo.

Uso (con el contenedor corriendo en otra terminal):
    docker compose exec api python benchmarks.py
"""
import asyncio
import time
import httpx

API_URL = 'http://localhost:8000'


async def esperar_completadas(cliente: httpx.AsyncClient, ids: list[int], intervalo: float = 0.05):
    """Consulta el estado de una lista de tareas hasta que todas terminen."""
    pendientes = set(ids)
    while pendientes:
        for tid in list(pendientes):
            r = await cliente.get(f'{API_URL}/tareas/{tid}')
            datos = r.json()
            if datos['estado'] in ('completada', 'fallida', 'cancelada'):
                pendientes.remove(tid)
        if pendientes:
            await asyncio.sleep(intervalo)


async def medicion_1_concurrencia_io(cliente: httpx.AsyncClient):
    """Medición 1: 20 descargas secuenciales vs 20 descargas concurrentes."""
    print('\n' + '=' * 70)
    print('MEDICIÓN 1: Concurrencia I/O (20 descargas secuenciales vs concurrentes)')
    print('=' * 70)

    # Usamos un endpoint real liviano (example.com) para medir I/O de red real
    urls = ['https://example.com' for _ in range(20)]

    # 1.A) 20 descargas secuenciales (una tras otra, esperando a que termine cada una)
    print('-> Ejecutando 20 descargas de forma SECUENCIAL...')
    t0 = time.perf_counter()
    for u in urls:
        r = await cliente.post(f'{API_URL}/tareas', json={'tipo': 'descargar', 'urls': [u]})
        tid = r.json()['id']
        await esperar_completadas(cliente, [tid], intervalo=0.02)
    t_secuencial = time.perf_counter() - t0
    print(f'   Tiempo total SECUENCIAL (20 descargas):  {t_secuencial:.5f} s')

    # 1.B) 20 descargas concurrentes (una tarea con las 20 URLs via asyncio.gather)
    print('-> Ejecutando 20 descargas de forma CONCURRENTE (gather)...')
    t0 = time.perf_counter()
    r = await cliente.post(f'{API_URL}/tareas', json={'tipo': 'descargar', 'urls': urls})
    tid = r.json()['id']
    await esperar_completadas(cliente, [tid], intervalo=0.02)
    r_final = await cliente.get(f'{API_URL}/tareas/{tid}')
    t_concurrente = r_final.json()['resultado']['tiempo_total_segundos']
    t_percibido = time.perf_counter() - t0

    speedup = t_secuencial / t_concurrente if t_concurrente > 0 else 0.0
    print(f'   Tiempo interno gather (20 descargas):    {t_concurrente:.5f} s (percibido: {t_percibido:.5f} s)')
    print(f'   SPEEDUP obtenido:                        {speedup:.5f}x')


async def medicion_2_event_loop_bloqueado(cliente: httpx.AsyncClient):
    """Medición 2: Latencia de GET /tareas durante tarea CPU-bound SIN vs CON run_in_executor."""
    print('\n' + '=' * 70)
    print('MEDICIÓN 2: El Event Loop Bloqueado (CPU-bound SIN vs CON executor)')
    print('=' * 70)

    iteraciones = 4_000_000  # ~2 a 4 segundos de CPU pura en SHA-256

    # 2.A) SIN run_in_executor (bloqueando el event loop intencionalmente)
    print(f'-> Lanzando hashear ({iteraciones:,} iteraciones) SIN run_in_executor...')
    r = await cliente.post(
        f'{API_URL}/tareas?bloquear_loop=true',
        json={'tipo': 'hashear', 'texto': 'computacion2', 'iteraciones': iteraciones},
    )
    tid_bloqueante = r.json()['id']

    # Damos 20 ms para que el worker tome la tarea de la cola y medimos cuánto tarda GET /tareas
    await asyncio.sleep(0.02)
    t0_get = time.perf_counter()
    await cliente.get(f'{API_URL}/tareas')
    latencia_sin_executor_ms = (time.perf_counter() - t0_get) * 1000
    await esperar_completadas(cliente, [tid_bloqueante])

    r_info = await cliente.get(f'{API_URL}/tareas/{tid_bloqueante}')
    dur_calculo_1 = r_info.json()['duracion']
    print(f'   Duración del cálculo CPU:                {dur_calculo_1:.5f} s')
    print(f'   Tiempo de respuesta de GET /tareas:      {latencia_sin_executor_ms:.5f} ms  <-- ¡LOOP CONGELADO!')

    # 2.B) CON ProcessPoolExecutor (comportamiento normal no bloqueante)
    print(f'\n-> Lanzando hashear ({iteraciones:,} iteraciones) CON ProcessPoolExecutor...')
    r = await cliente.post(
        f'{API_URL}/tareas?bloquear_loop=false',
        json={'tipo': 'hashear', 'texto': 'computacion2', 'iteraciones': iteraciones},
    )
    tid_executor = r.json()['id']

    await asyncio.sleep(0.05)
    t0_get = time.perf_counter()
    await cliente.get(f'{API_URL}/tareas')
    latencia_con_executor_ms = (time.perf_counter() - t0_get) * 1000
    await esperar_completadas(cliente, [tid_executor])

    r_info2 = await cliente.get(f'{API_URL}/tareas/{tid_executor}')
    dur_calculo_2 = r_info2.json()['duracion']
    print(f'   Duración del cálculo CPU:                {dur_calculo_2:.5f} s')
    print(f'   Tiempo de respuesta de GET /tareas:      {latencia_con_executor_ms:.5f} ms  <-- ¡LOOP LIBRE!')
    print(f'   Factor de mejora en latencia HTTP:       {latencia_sin_executor_ms / latencia_con_executor_ms:.5f}x')


async def medicion_3_techo_del_pool(cliente: httpx.AsyncClient):
    """Medición 3: Escalar cantidad de tareas concurrentes para ver el techo del pool de 4 workers."""
    print('\n' + '=' * 70)
    print('MEDICIÓN 3: Techo del Pool de Workers (escalando carga concurrente)')
    print('=' * 70)

    print('\n--- 3.A) Tareas I/O simuladas (esperar 0.5s cada una, con Pool de 4 Workers) ---')
    print(f'{"Cant. Tareas":<15} | {"Tiempo Total (s)":<18} | {"Promedio por lote (s)":<22}')
    print('-' * 60)

    for cantidad in (2, 4, 8, 16, 32):
        t0 = time.perf_counter()
        respuestas = await asyncio.gather(
            *(
                cliente.post(f'{API_URL}/tareas', json={'tipo': 'esperar', 'segundos': 0.5})
                for _ in range(cantidad)
            )
        )
        ids = [r.json()['id'] for r in respuestas]
        await esperar_completadas(cliente, ids, intervalo=0.02)
        dt = time.perf_counter() - t0
        print(f'{cantidad:<15} | {dt:<18.5f} | {dt / cantidad:<22.5f}')

    print('\n--- 3.B) Tareas CPU-bound (hashear 1,500,000 iteraciones, ProcessPool de 2 procesos) ---')
    print(f'{"Cant. Tareas":<15} | {"Tiempo Total (s)":<18} | {"Tiempo por tarea (s)":<22}')
    print('-' * 60)

    for cantidad in (1, 2, 4, 8):
        t0 = time.perf_counter()
        respuestas = await asyncio.gather(
            *(
                cliente.post(
                    f'{API_URL}/tareas',
                    json={'tipo': 'hashear', 'texto': f'test-{i}', 'iteraciones': 1_500_000},
                )
                for i in range(cantidad)
            )
        )
        ids = [r.json()['id'] for r in respuestas]
        await esperar_completadas(cliente, ids, intervalo=0.03)
        dt = time.perf_counter() - t0
        print(f'{cantidad:<15} | {dt:<18.5f} | {dt / cantidad:<22.5f}')


async def main():
    async with httpx.AsyncClient(timeout=60.0) as cliente:
        await medicion_1_concurrencia_io(cliente)
        await medicion_2_event_loop_bloqueado(cliente)
        await medicion_3_techo_del_pool(cliente)
    print('\n' + '=' * 70)
    print('Mediciones completadas.')


if __name__ == '__main__':
    asyncio.run(main())