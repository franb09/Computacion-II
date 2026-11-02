from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

EstadoTarea = Literal['pendiente', 'ejecutando', 'completada', 'fallida', 'cancelada']
TipoTarea = Literal['descargar', 'hashear', 'esperar']


class TareaNueva(BaseModel):
    tipo: TipoTarea
    prioridad: int = Field(
        default=1,
        ge=1,
        le=5,
        description='Prioridad de la tarea: 1 = más baja, 5 = más alta (estilo Clase 19)'
    )
    max_reintentos: int = Field(
        default=0,
        ge=0,
        le=5,
        description='Cantidad máxima de reintentos automáticos con backoff exponencial si falla'
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        description='Tiempo máximo de ejecución por intento en segundos'
    )
    urls: list[str] | None = Field(
        default=None,
        description='Lista de URLs para la tarea tipo descargar'
    )
    texto: str | None = Field(
        default=None,
        description='Texto base para la tarea tipo hashear'
    )
    iteraciones: int | None = Field(
        default=None,
        ge=1,
        description='Cantidad de iteraciones de SHA-256 para la tarea tipo hashear'
    )
    segundos: float | None = Field(
        default=None,
        gt=0,
        description='Segundos a dormir para la tarea tipo esperar'
    )

    @model_validator(mode='after')
    def validar_parametros_por_tipo(self) -> 'TareaNueva':
        if self.tipo == 'descargar' and not self.urls:
            raise ValueError("La tarea 'descargar' requiere una lista no vacía en 'urls'.")
        if self.tipo == 'hashear' and (self.texto is None or self.iteraciones is None):
            raise ValueError("La tarea 'hashear' requiere 'texto' e 'iteraciones'.")
        if self.tipo == 'esperar' and self.segundos is None:
            raise ValueError("La tarea 'esperar' requiere 'segundos'.")
        return self


class TareaRespuesta(BaseModel):
    id: int
    tipo: TipoTarea
    estado: EstadoTarea
    prioridad: int
    intentos_realizados: int
    max_reintentos: int
    timeout: float
    creada_en: float
    iniciada_en: float | None = None
    finalizada_en: float | None = None
    duracion: float | None = None
    resultado: Any = None
    error: str | None = None


class EstadisticasRespuesta(BaseModel):
    totales_por_estado: dict[EstadoTarea, int]
    tiempo_promedio_ejecucion: float
    workers_totales: int
    workers_ocupados: int
    tareas_en_cola: int