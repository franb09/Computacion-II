import asyncio
import hashlib
import time
from concurrent.futures import ProcessPoolExecutor
import httpx


async def ejecutar_esperar(segundos: float) -> dict:
    """Tarea I/O simulada: cede el control al event loop durante N segundos."""
    t0 = time.perf_counter()
    await asyncio.sleep(segundos)
    duracion = round(time.perf_counter() - t0, 5)
    return {
        'segundos_esperados': segundos,
        'tiempo_real_segundos': duracion,
    }


async def _descargar_una_url(cliente: httpx.AsyncClient, url: str) -> dict:
    """Descarga una única URL de forma asíncrona midiendo su tiempo y tamaño."""
    t0 = time.perf_counter()
    respuesta = await cliente.get(url, follow_redirects=True)
    duracion = round(time.perf_counter() - t0, 5)
    return {
        'url': url,
        'codigo_estado': respuesta.status_code,
        'tamano_bytes': len(respuesta.content),
        'tiempo_segundos': duracion,
    }


async def ejecutar_descargar(urls: list[str], cliente: httpx.AsyncClient) -> dict:
    """Tarea I/O-bound: descarga múltiples URLs concurrentemente con asyncio.gather."""
    t0 = time.perf_counter()
    # Lanzamos todas las corrutinas en paralelo dentro del mismo event loop
    resultados = await asyncio.gather(
        *(_descargar_una_url(cliente, url) for url in urls)
    )
    duracion_total = round(time.perf_counter() - t0, 5)
    return {
        'cantidad_urls': len(urls),
        'tiempo_total_segundos': duracion_total,
        'descargas': resultados,
    }


def calcular_hash_sincrono(texto: str, iteraciones: int) -> dict:
    """Función CPU-bound pura (sincrónica).
    Debe estar a nivel de módulo para que ProcessPoolExecutor pueda serializarla con pickle.
    """
    t0 = time.perf_counter()
    datos = texto.encode('utf-8')
    for _ in range(iteraciones):
        datos = hashlib.sha256(datos).digest()
    duracion = round(time.perf_counter() - t0, 5)
    return {
        'hash_sha256': datos.hex(),
        'iteraciones': iteraciones,
        'tiempo_cpu_segundos': duracion,
    }


async def ejecutar_hashear(
    texto: str,
    iteraciones: int,
    pool: ProcessPoolExecutor | None = None,
    bloquear_loop_intencionalmente: bool = False,
) -> dict:
    """Tarea CPU-bound: delega el cálculo al ProcessPoolExecutor usando run_in_executor.
    El parámetro 'bloquear_loop_intencionalmente' solo se usa para la Medición 2 del informe.
    """
    if bloquear_loop_intencionalmente:
        # MAL A PROPÓSITO (solo para demostrar en el benchmark cómo se congela el loop)
        return calcular_hash_sincrono(texto, iteraciones)

    loop = asyncio.get_running_loop()
    # Delegamos al pool de procesos; el event loop queda libre esperando el Future
    return await loop.run_in_executor(pool, calcular_hash_sincrono, texto, iteraciones)