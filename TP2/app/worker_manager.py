import asyncio
from concurrent.futures import ProcessPoolExecutor
import glob
import itertools
import json
import logging
import os
import time
from fastapi import WebSocket
import httpx

from app.models import TareaNueva
from app.tasks import ejecutar_descargar, ejecutar_esperar, ejecutar_hashear

logger = logging.getLogger('plataforma_tareas')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)

CENTINELA = object()


class GestorTareas:
    def __init__(
        self,
        num_workers: int = 4,
        max_cola: int = 100,
        max_procesos_cpu: int = 2,
        directorio_estado: str = '.',
        factor_aging: float = 0.05,
        backoff_base: float = 0.5,
    ):
        self.num_workers = num_workers
        self.max_cola = max_cola
        self.max_procesos_cpu = max_procesos_cpu
        self.directorio_estado = directorio_estado
        self.factor_aging = factor_aging
        self.backoff_base = backoff_base
        self.t0_servidor = time.monotonic()

        self._contador_fifo = itertools.count()

        self.tareas: dict[int, dict] = {}
        self.proximo_id: int = 0
        self.workers_ocupados: int = 0
        self.cerrando: bool = False

        self.tareas_activas: dict[int, asyncio.Task] = {}
        self.clientes_ws: set[WebSocket] = set()

        self.cola: asyncio.PriorityQueue | None = None
        self.workers: list[asyncio.Task] = []
        self.pool_procesos: ProcessPoolExecutor | None = None
        self.cliente_http: httpx.AsyncClient | None = None

    def _calcular_item_cola(self, prioridad: int, item: object) -> tuple[float, int, object]:
        edad = time.monotonic() - self.t0_servidor
        peso = -float(prioridad) - (edad * self.factor_aging)
        return (peso, next(self._contador_fifo), item)

    async def conectar_ws(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clientes_ws.add(ws)

    def desconectar_ws(self, ws: WebSocket) -> None:
        self.clientes_ws.discard(ws)

    async def notificar_evento(self, evento: str, registro: dict, extra: str | None = None) -> None:
        if not self.clientes_ws:
            return
        mensaje = {
            'evento': evento,
            'timestamp': round(time.time(), 5),
            'tarea_id': registro['id'],
            'tipo': registro['tipo'],
            'estado': registro['estado'],
            'prioridad': registro['prioridad'],
            'intentos_realizados': registro['intentos_realizados'],
        }
        if extra:
            mensaje['detalle'] = extra

        desconectados = []
        for ws in list(self.clientes_ws):
            try:
                await ws.send_json(mensaje)
            except Exception:
                desconectados.append(ws)
        for ws in desconectados:
            self.clientes_ws.discard(ws)

    def reportar_volcado_previo(self) -> None:
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
        self.reportar_volcado_previo()
        self.cerrando = False
        self.cola = asyncio.PriorityQueue(maxsize=self.max_cola)
        self.pool_procesos = ProcessPoolExecutor(max_workers=self.max_procesos_cpu)
        self.cliente_http = httpx.AsyncClient(timeout=30.0)

        self.workers = [
            asyncio.create_task(self._worker(wid), name=f'worker-{wid}')
            for wid in range(self.num_workers)
        ]
        logger.info(
            f'Gestor iniciado: {self.num_workers} workers async, '
            f'PriorityQueue(maxsize={self.max_cola}), ProcessPoolExecutor({self.max_procesos_cpu}).'
        )

    async def encolar(self, nueva: TareaNueva, bloquear_loop: bool = False) -> dict:
        if self.cerrando:
            raise RuntimeError('El servidor se está apagando y no acepta tareas nuevas.')

        self.proximo_id += 1
        tarea_id = self.proximo_id

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
            'prioridad': nueva.prioridad,
            'intentos_realizados': 0,
            'max_reintentos': nueva.max_reintentos,
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
        item_cola = self._calcular_item_cola(nueva.prioridad, tarea_id)
        await self.cola.put(item_cola)
        await self.notificar_evento('tarea_encolada', registro)
        return self._limpiar_registro(registro)

    async def _ejecutar_segun_tipo(self, registro: dict) -> dict:
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

    async def _ejecutar_con_reintentos(self, registro: dict) -> dict:
        max_intentos = 1 + registro['max_reintentos']
        ultimo_error: Exception | None = None

        for intento in range(1, max_intentos + 1):
            registro['intentos_realizados'] = intento
            try:
                async with asyncio.timeout(registro['timeout']):
                    return await self._ejecutar_segun_tipo(registro)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                ultimo_error = exc
                if intento < max_intentos:
                    demora_backoff = round(self.backoff_base * (2 ** (intento - 1)), 5)
                    motivo = (
                        f"Timeout ({registro['timeout']}s)"
                        if isinstance(exc, TimeoutError)
                        else f'{type(exc).__name__}: {exc}'
                    )
                    logger.warning(
                        f"Tarea {registro['id']} falló en intento {intento}/{max_intentos} ({motivo}). "
                        f'Reintentando en {demora_backoff}s (backoff exponencial)...'
                    )
                    await self.notificar_evento(
                        'tarea_reintentando',
                        registro,
                        extra=f'Intento {intento} falló ({motivo}). Backoff: {demora_backoff}s',
                    )
                    await asyncio.sleep(demora_backoff)
                else:
                    raise ultimo_error

    async def _worker(self, wid: int) -> None:
        while True:
            _, _, item = await self.cola.get()
            if item is CENTINELA:
                self.cola.task_done()
                logger.info(f'Worker {wid} recibió centinela y se retira ordenadamente.')
                return

            tarea_id: int = item
            registro = self.tareas.get(tarea_id)

            try:
                if not registro or registro['estado'] == 'cancelada':
                    continue

                registro['estado'] = 'ejecutando'
                registro['iniciada_en'] = round(time.time(), 5)
                self.workers_ocupados += 1
                await self.notificar_evento('tarea_ejecutando', registro)
                t0 = time.perf_counter()

                sub_task = asyncio.create_task(self._ejecutar_con_reintentos(registro))
                self.tareas_activas[tarea_id] = sub_task

                try:
                    resultado = await sub_task
                    registro['resultado'] = resultado
                    registro['estado'] = 'completada'
                    registro['error'] = None
                    await self.notificar_evento('tarea_completada', registro)

                except TimeoutError:
                    registro['estado'] = 'fallida'
                    registro['error'] = f"Timeout excedido ({registro['timeout']}s)"
                    logger.warning(f'Tarea {tarea_id} falló definitivamente por timeout.')
                    await self.notificar_evento('tarea_fallida', registro, extra=registro['error'])

                except asyncio.CancelledError:
                    registro['estado'] = 'cancelada'
                    registro['error'] = 'Tarea cancelada por el usuario o apagado del servidor'
                    logger.info(f'Tarea {tarea_id} cancelada limpiamente.')
                    await self.notificar_evento('tarea_cancelada', registro)
                    current = asyncio.current_task()
                    if current and current.cancelled():
                        raise

                except Exception as exc:
                    registro['estado'] = 'fallida'
                    registro['error'] = f'{type(exc).__name__}: {exc}'
                    logger.error(f'Error definitivo en tarea {tarea_id}: {exc}')
                    await self.notificar_evento('tarea_fallida', registro, extra=registro['error'])

                finally:
                    t_fin = time.perf_counter()
                    registro['finalizada_en'] = round(time.time(), 5)
                    registro['duracion'] = round(t_fin - t0, 5)
                    self.tareas_activas.pop(tarea_id, None)
                    self.workers_ocupados -= 1

            finally:
                self.cola.task_done()

    async def cancelar_tarea(self, tarea_id: int) -> str:
        if tarea_id not in self.tareas:
            raise KeyError('No existe esa tarea')

        registro = self.tareas[tarea_id]
        estado_actual = registro['estado']

        if estado_actual in ('completada', 'fallida', 'cancelada'):
            raise ValueError(f"No se puede cancelar una tarea en estado '{estado_actual}'")

        if estado_actual == 'pendiente':
            registro['estado'] = 'cancelada'
            registro['finalizada_en'] = round(time.time(), 5)
            registro['duracion'] = 0.0
            registro['error'] = 'Cancelada mientras estaba en cola (pendiente)'
            await self.notificar_evento('tarea_cancelada', registro)
            return 'cancelada_en_cola'

        if estado_actual == 'ejecutando':
            sub_task = self.tareas_activas.get(tarea_id)
            if sub_task and not sub_task.done():
                sub_task.cancel()
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

    def generar_metricas_prometheus(self) -> str:
        stats = self.obtener_estadisticas()
        totales = stats['totales_por_estado']
        lineas = [
            '# HELP tareas_total Cantidad total de tareas por estado.',
            '# TYPE tareas_total gauge',
        ]
        for estado, cant in totales.items():
            lineas.append(f'tareas_total{{estado="{estado}"}} {cant}')

        lineas.extend([
            '# HELP tareas_tiempo_promedio_segundos Tiempo promedio de ejecucion de tareas completadas.',
            '# TYPE tareas_tiempo_promedio_segundos gauge',
            f"tareas_tiempo_promedio_segundos {stats['tiempo_promedio_ejecucion']}",
            '# HELP workers_totales Cantidad total de corrutinas workers en el pool.',
            '# TYPE workers_totales gauge',
            f"workers_totales {stats['workers_totales']}",
            '# HELP workers_ocupados Cantidad de workers ejecutando tareas actualmente.',
            '# TYPE workers_ocupados gauge',
            f"workers_ocupados {stats['workers_ocupados']}",
            '# HELP tareas_en_cola Cantidad de tareas esperando en la PriorityQueue.',
            '# TYPE tareas_en_cola gauge',
            f"tareas_en_cola {stats['tareas_en_cola']}",
        ])
        return '\n'.join(lineas) + '\n'

    def volcar_estado_json(self) -> str:
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
        if self.cerrando:
            return
        self.cerrando = True
        logger.info('Iniciando apagado ordenado: ya no se aceptan tareas nuevas.')
        for _ in range(self.num_workers):
            await self.cola.put((float('inf'), next(self._contador_fifo), CENTINELA))

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

        if self.cliente_http:
            await self.cliente_http.aclose()
        if self.pool_procesos:
            self.pool_procesos.shutdown(wait=False, cancel_futures=True)

        self.volcar_estado_json()

    @staticmethod
    def _limpiar_registro(registro: dict) -> dict:
        return {k: v for k, v in registro.items() if not k.startswith('_')}