# src/triton_telemetry/logging_engine.py
"""
El corazón de la observabilidad de Tritón.

- AsyncJSONFormatter: formateador JSON forense que expande recursivamente
  la jerarquía de un ExceptionGroup (excepciones anidadas, causas raíz
  encadenadas con `from` y notas dinámicas de add_note()).
- Pipeline no bloqueante: QueueHandler/QueueListener desacoplan la
  escritura física en disco del event loop de asyncio.
- Callbacks de rotación (namer/rotator) que comprimen a Gzip los
  históricos de log en caliente.
"""

import gzip
import json
import logging
import logging.config
import logging.handlers
import os
import queue
import shutil
from datetime import datetime, timezone
from typing import Any, Dict


# --- Callbacks de compresión en caliente para el RotatingFileHandler -----

def gzip_namer(name: str) -> str:
    """Modifica el nombre del archivo de backup agregando la extensión .gz."""
    return name + ".gz"


def gzip_rotator(source: str, dest: str) -> None:
    """Comprime el archivo rotado a formato .gz de forma atómica y elimina
    de forma segura el archivo plano residual del sistema operativo."""
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


# --- Formateador JSON forense --------------------------------------------

class AsyncJSONFormatter(logging.Formatter):
    """
    Formateador JSON personalizado para telemetría asíncrona.
    Responsabilidad del Integrante 3: Estandarización de logs, captura de tareas
    asíncronas y serialización jerárquica avanzada de excepciones.
    """
    def _serialize_exception(self, exc: BaseException) -> Dict[str, Any]:
        """
        Función auxiliar recursiva. Procesa la excepción actual, extrae notas dinámicas
        y desciende recursivamente si encuentra ExceptionGroups o causas raíz ('__cause__').
        """
        # Estructura base de la excepción capturada
        exc_data: Dict[str, Any] = {
            "class": exc.__class__.__name__,
            "message": str(exc),
            "notes": getattr(exc, "__notes__", [])
        }
        # Estructura base de la excepción capturada
        exc_data: Dict[str, Any] = {
            "class": exc.__class__.__name__,
            "message": str(exc),
            "notes": getattr(exc, "__notes__", [])
        }
        # Soporte para ExceptionGroup (Python 3.11+): recorrido de múltiples errores concurrentes
        if isinstance(exc, ExceptionGroup):
            exc_data["nested_exceptions"] = [
                self._serialize_exception(child) for child in exc.exceptions
            ]
        # Soporte para ExceptionGroup (Python 3.11+): recorrido de múltiples errores concurrentes
        if isinstance(exc, ExceptionGroup):
            exc_data["nested_exceptions"] = [
                self._serialize_exception(nested_err)
                for nested_err in exc.exceptions
            ]
        # Soporte para encadenamiento explícito de errores ('raise ... from')
        elif exc.__cause__:
            exc_data["cause"] = self._serialize_exception(exc.__cause__)
        # Soporte para encadenamiento explícito de errores ('raise ... from')
        elif exc.__cause__:
            exc_data["cause"] = self._serialize_exception(exc.__cause__)
        return exc_data

    def format(self, record: logging.LogRecord) -> str:
        # Generación de marca de tiempo estricta en formato ISO 8601 UTC (terminada en 'Z')
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # Generación de marca de tiempo estricta en formato ISO 8601 UTC (terminada en 'Z')
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # Payload principal estructurado en formato JSON con metadatos del sistema y tareas async
        log_payload: Dict[str, Any] = {
            "timestamp": dt_utc.isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            "async_task": getattr(record, "taskName", "None"),
            "thread_name": record.threadName,
            "filename": record.filename,
            "line": record.lineno
        }
            "async_task": getattr(record, "taskName", "None"),
            "thread_name": record.threadName,
            "filename": record.filename,
            "line": record.lineno
        }
        # Integración del árbol de excepciones si el registro contiene información de error
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_value:
                log_payload["exception_tree"] = self._serialize_exception(exc_value)
            # Volcado completo del stack trace tradicional para diagnóstico
            log_payload["stack_trace"] = self.formatException(record.exc_info)
        # Integración del árbol de excepciones si el registro contiene información de error
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_type and issubclass(exc_type, BaseException):
                log_payload["exception_tree"] = self._serialize_exception(exc_value)
            # Volcado completo del stack trace tradicional para diagnóstico
            log_payload["stack_trace"] = self.formatException(record.exc_info)
        # Listado de campos internos de Python para prevenir duplicaciones en el JSON
        reserved_fields = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName"
        }
        # Listado de campos internos de Python para prevenir duplicaciones en el JSON
        reserved_fields = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName"
        }
        # Inyección dinámica de metadatos personalizados provistos mediante el parámetro 'extra'
        for key, value in record.__dict__.items():
            if key not in reserved_fields and not key.startswith('_'):
                log_payload[key] = value
        for key, value in record.__dict__.items():
            if key not in reserved_fields and not key.startswith('_'):
                log_payload[key] = value

        # Serialización final del diccionario a una cadena de texto JSON válida
        return json.dumps(log_payload, ensure_ascii=False)


# --- QueueHandler que preserva el exc_info real -------------------------

class ForensicQueueHandler(logging.handlers.QueueHandler):
    """
    QueueHandler especializado para telemetría forense.

    El QueueHandler estándar de la librería, en su método `prepare()`,
    descarta `record.exc_info` y `record.exc_text` tras pre-formatearlos a
    texto plano. Esto es correcto cuando la cola puede cruzar procesos
    (multiprocessing.Queue) y el traceback no es picklable, pero en Tritón
    usamos una `queue.Queue` en memoria dentro del mismo proceso: no hay
    pickling de por medio, así que descartar exc_info le quita al
    AsyncJSONFormatter, corriendo en el hilo del QueueListener, el árbol de
    excepciones real (incluyendo la estructura anidada de ExceptionGroup)
    que necesita serializar recursivamente.
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


def wire_non_blocking_pipeline(
    app_logger: logging.Logger,
) -> logging.handlers.QueueListener:
    """
    Envuelve los handlers "reales" de un logger ya configurado (consola +
    archivo) en un pipeline no bloqueante QueueHandler/QueueListener, e
    inyecta los callbacks de compresión Gzip en el RotatingFileHandler.

    Responsabilidad exclusiva del Integrante 4 (Ingeniero de Almacenamiento
    y Desacoplamiento No Bloqueante). No depende de AsyncJSONFormatter ni
    de ningún detalle de qué formatea cada handler — solo le importa que
    existan handlers ya armados para desacoplarlos del hilo/loop principal.

    Devuelve el QueueListener ya arrancado, para que quien llama pueda
    detenerlo ordenadamente (logger.listener.stop()) al finalizar.
    """
    # 1) Compresión Gzip en caliente sobre el handler rotativo, si existe.
    file_handler = next(
        (h for h in app_logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
        None,
    )
    if file_handler is not None:
        file_handler.namer = gzip_namer
        file_handler.rotator = gzip_rotator

    # 2) Desacoplamiento no bloqueante: QueueHandler (productor, corre en el
    #    hilo/loop principal) + QueueListener (consumidor, hilo secundario).
    log_queue: "queue.Queue" = queue.Queue(-1)
    queue_handler = ForensicQueueHandler(log_queue)

    real_handlers = app_logger.handlers
    listener = logging.handlers.QueueListener(
        log_queue, *real_handlers, respect_handler_level=True
    )

    # A partir de aquí, el logger solo encola instantáneamente en memoria;
    # la escritura física queda delegada por completo al hilo del listener.
    app_logger.handlers = [queue_handler]

    listener.start()
    app_logger.listener = listener  # type: ignore[attr-defined]

    return listener


# --- Configuración declarativa (Integrante 3 / 5) -------------------------

def setup_triton_logging(log_filename: str = "triton_services.log") -> logging.Logger:
    """
    Configura el pipeline de logging mediante dictConfig (formatters y
    handlers "reales": consola + archivo rotativo) y luego delega en
    `wire_non_blocking_pipeline` el desacoplamiento no bloqueante
    (Integrante 4).
    """
    logging_schema = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json_structured": {"()": AsyncJSONFormatter},
            "console_clean": {
                "format": "%(asctime)s [%(levelname)s] (%(taskName)s) %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "stdout_console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "console_clean",
                "stream": "ext://sys.stdout",
            },
            "rotating_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "json_structured",
                "filename": log_filename,
                "maxBytes": 2 * 1024 * 1024,  # 2 MB por archivo
                "backupCount": 3,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "triton_monitor": {
                "level": "DEBUG",
                "handlers": ["stdout_console", "rotating_file"],
                "propagate": False,
            }
        },
    }

    logging.config.dictConfig(logging_schema)
    app_logger = logging.getLogger("triton_monitor")

    wire_non_blocking_pipeline(app_logger)

    return app_logger
