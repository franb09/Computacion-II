import asyncio
from concurrent.futures import ProcessPoolExecutor
import glob
import json
import logging
import os
import time
import httpx

from app.models import TareaNueva
from app.tasks import ejecutar_descargar, ejecutar_esperar, ejecutar_hashear

logger = logging.getLogger('plataforma_tareas')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

# Marca única para apagar los workers ordenadamente (Clase 21 - cola.py)
CENTINELA = object()


class GestorTareas:
    """Administra la cola asíncrona, el pool de workers, el estado en memoria y la persistencia."""

    def __init__(
        self,
        num_workers: int = 4,
        max_cola: int = 100,
        max_procesos_cpu: int = 2,
        directorio_estado: str = '.',
    ):
        self.num_workers = num_workers
        self.max_cola = max_cola
        self.max_procesos_cpu = max_procesos_cpu
        self.directorio_estado = directorio_estado

        # Estado en memoria (no requiere Lock entre awaits si no cedemos el control en el medio)
        self.tareas: dict[int, dict] = {}
        self.proximo_id: int = 0
        self.workers_ocupados: int = 0
        self.cerrando: bool = False

        # Referencias a las asyncio.Task que están corriendo ahora mismo (para poder cancelarlas)
        self.tareas_activas: dict[int, asyncio.Task] = {}

        # Recursos que se inicializan al arrancar el event loop
        self.cola: asyncio.Queue | None = None
        self.workers: list[asyncio.Task] = []
        self.pool_procesos: ProcessPoolExecutor | None = None
        self.cliente_http: httpx.AsyncClient | None = None

    def reportar_volcado_previo(self) -> None:
        """Al arrancar, verifica si existen volcados estado_<timestamp>.json previos y los reporta por log."""
        patron = os.path.join(self.directorio_estado, 'estado_*.json')
        archivos = sorted(glob.glob(patron))
        if archivos:
            ultimo = archivos[-1]
            try:
                with open(ultimo, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                cantidad = len(datos.get('tareas', []))
                logger.info(
                    f"Se detectó un volcado previo: '{ultimo}' con {cantidad} tarea(s) registrada(s)."
                )
            except Exception as e:
                logger.warning(f"Se encontró un volcado previo '{ultimo}', pero no se pudo leer: {e}")
        else:
            logger.info('No se encontraron volcados de estado previos al arrancar.')

    async def iniciar(self) -> None:
        """Inicializa la cola, el cliente HTTP compartido, el ProcessPoolExecutor y lanza los workers."""
        self.reportar_volcado_previo()
        self.cerrando = False
        self.cola = asyncio.Queue(maxsize=self.max_cola)
        self.pool_procesos = ProcessPoolExecutor(max_workers=self.max_procesos_cpu)
        # El cliente HTTP se crea UNA vez para reutilizar conexiones keep-alive (Clase 20)
        self.cliente_http = httpx.AsyncClient(timeout=30.0)

        self.workers = [
            asyncio.create_task(self._worker(wid), name=f'worker-{wid}')
            for wid in range(self.num_workers)
        ]
        logger.info(
            f'Gestor iniciado: {self.num_workers} workers async, '
            f'ProcessPoolExecutor({self.max_procesos_cpu}), maxsize cola={self.max_cola}.'
        )

    async def encolar(self, nueva: TareaNueva, bloquear_loop: bool = False) -> dict:
        """Crea una tarea en estado pendiente y la mete en la asyncio.Queue inmediatamente."""
        if self.cerrando:
            raise RuntimeError('El servidor se está apagando y no acepta tareas nuevas.')

        self.proximo_id += 1
        tarea_id = self.proximo_id

        # Guardamos los parámetros originales para que el worker sepa qué ejecutar
        parametros = {
            'urls': nueva.urls,
            'texto': nueva.texto,
            'iteraciones': nueva.iteraciones,
            'segundos': nueva.segundos,
            'bloquear_loop': bloquear_loop,
        }

        registro = {
            'id': tarea_id,
            'tipo': nueva.tipo,
            'estado': 'pendiente',
            'timeout': nueva.timeout,
            'creada_en': round(time.time(), 5),
            'iniciada_en': None,
            'finalizada_en': None,
            'duracion': None,
            'resultado': None,
            'error': None,
            '_parametros': parametros,
        }

        self.tareas[tarea_id] = registro
        await self.cola.put(tarea_id)
        return self._limpiar_registro(registro)

    async def _ejecutar_segun_tipo(self, registro: dict) -> dict:
        """Despacha la tarea a la función correspondiente de tasks.py."""
        tipo = registro['tipo']
        params = registro['_parametros']

        if tipo == 'esperar':
            return await ejecutar_esperar(params['segundos'])
        elif tipo == 'descargar':
            return await ejecutar_descargar(params['urls'], self.cliente_http)
        elif tipo == 'hashear':
            return await ejecutar_hashear(
                texto=params['texto'],
                iteraciones=params['iteraciones'],
                pool=self.pool_procesos,
                bloquear_loop_intencionalmente=params.get('bloquear_loop', False),
            )
        else:
            raise ValueError(f'Tipo de tarea desconocido: {tipo}')

    async def _worker(self, wid: int) -> None:
        """Corrutina consumidora: toma IDs de la cola y los ejecuta con control de timeout y cancelación."""
        while True:
            item = await self.cola.get()
            if item is CENTINELA:
                self.cola.task_done()
                logger.info(f'Worker {wid} recibió centinela y se retira ordenadamente.')
                return

            tarea_id: int = item
            registro = self.tareas.get(tarea_id)

            try:
                # Si la tarea fue cancelada mientras estaba en la cola, no la ejecutamos
                if not registro or registro['estado'] == 'cancelada':
                    continue

                registro['estado'] = 'ejecutando'
                registro['iniciada_en'] = round(time.time(), 5)
                self.workers_ocupados += 1
                t0 = time.perf_counter()

                # Creamos una sub-Task para poder cancelarla específicamente desde DELETE /tareas/{id}
                sub_task = asyncio.create_task(self._ejecutar_segun_tipo(registro))
                self.tareas_activas[tarea_id] = sub_task

                try:
                    async with asyncio.timeout(registro['timeout']):
                        resultado = await sub_task
                    registro['resultado'] = resultado
                    registro['estado'] = 'completada'

                except TimeoutError:
                    # asyncio.timeout ya cancela la sub_task internamente al vencer
                    registro['estado'] = 'fallida'
                    registro['error'] = f"Timeout excedido ({registro['timeout']}s)"
                    logger.warning(f'Tarea {tarea_id} falló por timeout ({registro["timeout"]}s).')

                except asyncio.CancelledError:
                    # Si cancelaron la sub_task mediante DELETE /tareas/{id}
                    # o si están cancelando al propio worker en un cierre forzado
                    registro['estado'] = 'cancelada'
                    registro['error'] = 'Tarea cancelada por el usuario o apagado del servidor'
                    logger.info(f'Tarea {tarea_id} cancelada limpiamente.')
                    # Si el worker mismo fue cancelado desde afuera, relanzamos CancelledError (Clase 20)
                    current = asyncio.current_task()
                    if current and current.cancelled():
                        raise

                except Exception as exc:
                    # Si ocurre cualquier excepción no prevista, el worker NO muere:
                    # marca la tarea como fallida y sigue vivo para atender la siguiente.
                    registro['estado'] = 'fallida'
                    registro['error'] = f'{type(exc).__name__}: {exc}'
                    logger.error(f'Error ejecutando tarea {tarea_id}: {exc}')

                finally:
                    t_fin = time.perf_counter()
                    registro['finalizada_en'] = round(time.time(), 5)
                    registro['duracion'] = round(t_fin - t0, 5)
                    self.tareas_activas.pop(tarea_id, None)
                    self.workers_ocupados -= 1

            finally:
                # SIEMPRE avisar a la cola que este ítem terminó (Clase 21)
                self.cola.task_done()

    async def cancelar_tarea(self, tarea_id: int) -> str:
        """Cancela una tarea pendiente o en ejecución."""
        if tarea_id not in self.tareas:
            raise KeyError('No existe esa tarea')

        registro = self.tareas[tarea_id]
        estado_actual = registro['estado']

        if estado_actual in ('completada', 'fallida', 'cancelada'):
            raise ValueError(f"No se puede cancelar una tarea en estado '{estado_actual}'")

        if estado_actual == 'pendiente':
            # Está en la cola esperando; al marcarla 'cancelada', cuando un worker la saque la salteará
            registro['estado'] = 'cancelada'
            registro['finalizada_en'] = round(time.time(), 5)
            registro['duracion'] = 0.0
            registro['error'] = 'Cancelada mientras estaba en cola (pendiente)'
            return 'cancelada_en_cola'

        if estado_actual == 'ejecutando':
            sub_task = self.tareas_activas.get(tarea_id)
            if sub_task and not sub_task.done():
                sub_task.cancel()
                # Esperamos un instante a que la corrutina procese su CancelledError y limpie con finally
                await asyncio.sleep(0)
            return 'cancelada_en_ejecucion'

        return 'ignorado'

    def obtener_tarea(self, tarea_id: int) -> dict:
        if tarea_id not in self.tareas:
            raise KeyError('No existe esa tarea')
        return self._limpiar_registro(self.tareas[tarea_id])

    def listar_tareas(self, estado: str | None = None) -> list[dict]:
        items = [self._limpiar_registro(t) for t in self.tareas.values()]
        if estado:
            items = [t for t in items if t['estado'] == estado]
        return items

    def obtener_estadisticas(self) -> dict:
        totales = {
            'pendiente': 0,
            'ejecutando': 0,
            'completada': 0,
            'fallida': 0,
            'cancelada': 0,
        }
        duraciones = []
        for t in self.tareas.values():
            totales[t['estado']] += 1
            if t['estado'] == 'completada' and t['duracion'] is not None:
                duraciones.append(t['duracion'])

        promedio = round(sum(duraciones) / len(duraciones), 5) if duraciones else 0.0
        en_cola = self.cola.qsize() if self.cola else 0

        return {
            'totales_por_estado': totales,
            'tiempo_promedio_ejecucion': promedio,
            'workers_totales': self.num_workers,
            'workers_ocupados': self.workers_ocupados,
            'tareas_en_cola': en_cola,
        }

    def volcar_estado_json(self) -> str:
        """Vuelca el estado de todas las tareas en memoria a estado_<timestamp>.json."""
        timestamp = int(time.time())
        nombre_archivo = os.path.join(self.directorio_estado, f'estado_{timestamp}.json')
        datos = {
            'timestamp': timestamp,
            'estadisticas': self.obtener_estadisticas(),
            'tareas': self.listar_tareas(),
        }
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
        logger.info(f"Estado volcado exitosamente en '{nombre_archivo}'.")
        return nombre_archivo

    async def apagar(self, timeout_espera: float = 10.0) -> None:
        """Apagado ordenado ante SIGINT/SIGTERM:
        1. Deja de aceptar tareas nuevas.
        2. Envía centinelas para que los workers salgan al terminar lo que tienen en curso.
        3. Espera con límite (timeout_espera); si alguna tarea sigue colgada, la cancela.
        4. Cierra el cliente HTTP, el ProcessPoolExecutor y vuelca el estado a JSON.
        """
        if self.cerrando:
            return
        self.cerrando = True
        logger.info('Iniciando apagado ordenado: ya no se aceptan tareas nuevas.')

        # Mandamos un centinela por cada worker
        for _ in range(self.num_workers):
            await self.cola.put(CENTINELA)

        # Esperamos con límite a que los workers procesen lo que estaba en curso y lean su centinela
        try:
            async with asyncio.timeout(timeout_espera):
                await asyncio.gather(*self.workers, return_exceptions=True)
            logger.info('Todos los workers finalizaron sus tareas en curso ordenadamente.')
        except TimeoutError:
            logger.warning(
                f'Tiempo de espera agotado ({timeout_espera}s). Cancelando tareas aún en curso...'
            )
            for sub_task in list(self.tareas_activas.values()):
                sub_task.cancel()
            for w in self.workers:
                w.cancel()
            await asyncio.gather(*self.workers, return_exceptions=True)

        # Cerramos el cliente HTTP compartido y el pool de procesos
        if self.cliente_http:
            await self.cliente_http.aclose()
        if self.pool_procesos:
            self.pool_procesos.shutdown(wait=False, cancel_futures=True)

        # Volcamos el estado final a JSON
        self.volcar_estado_json()

    @staticmethod
    def _limpiar_registro(registro: dict) -> dict:
        """Devuelve una copia del diccionario sin los campos internos que empiezan con '_'."""
        return {k: v for k, v in registro.items() if not k.startswith('_')}