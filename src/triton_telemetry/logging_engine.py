# src/triton_telemetry/logging_engine.py
"""Módulo de telemetría y formateo de logs estructurados en JSON.

Integrante 3 (AsyncJSONFormatter): formateo JSON forense, serialización
recursiva de excepciones (incluyendo ExceptionGroup, causas encadenadas,
notas de add_note() y detalles reales de httpx) y captura de metadatos
dinámicos vía taskName/process/threadName/extra.
"""

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
 main
import json
import logging
import logging.config
import logging.handle
integrante3
import queue
import os
import gzip
==
import os
import queue
 main
import shutil
from datetime import datetime, timezone
from typing import Any, Dict
import httpx

# Necesario para reconocer los tipos de excepción propios de httpx
# (HTTPStatusError, RequestError) dentro de _serialize_exception.
import httpx


# ---------------------------------------------------------------------------
# Callbacks de compresión en caliente para el RotatingFileHandler
# ---------------------------------------------------------------------------


# --- Callbacks de compresión en caliente para el RotatingFileHandler -----
def gzip_namer(name: str) -> str:
    """Modifica el nombre del archivo de backup agregando la extensión .gz."""
    return name + ".gz"

def gzip_rotator(source: str, dest: str) -> None:
    """Comprime el archivo rotado a formato .gz de forma atómica y elimina el original."""
    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)
def gzip_rotator(source: str, dest: str) -> None:

    with open(source, "rb") as f_in:
        with gzip.open(dest, "wb", compresslevel=9) as f_out:
 main
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)

# ---------------------------------------------------------------------------
# Formateador JSON (responsabilidad del Integrante 3)
# ---------------------------------------------------------------------------

# --- Formateador JSON forense --------------------------------------------

 main
class AsyncJSONFormatter(logging.Formatter):
    """Formateador JSON forense para telemetría asíncrona.

    Responsable del Integrante 3: estandarización de logs, captura de tareas
    asíncronas y serialización jerárquica avanzada de ExceptionGroups,
    causas encadenadas, notas dinámicas y detalles reales de httpx.
    """
    def _serialize_exception(self, exc: BaseException) -> Dict[str, Any]:
        # Estructura base de la excepción capturada
        exc_data: Dict[str, Any] = {
            "class": exc.__class__.__name__,
            "message": str(exc),
            "notes": getattr(exc, "__notes__", [])
        }
        # Datos reales de la API httpx que colapsó: si la excepción (en
        # cualquier nivel de la recursión) es del "árbol genealógico" de
        # httpx, rescatamos la URL, el método y el código de estado real.
        if isinstance(exc, httpx.HTTPStatusError):
            # La petición llegó al servidor, pero la respuesta fue un error
            # (4xx/5xx). httpx guarda automáticamente request y response.
            exc_data["httpx_details"] = {
                "url": str(exc.request.url),
                "method": exc.request.method,
                "status_code": exc.response.status_code,
            }
        elif isinstance(exc, httpx.RequestError):
            # La petición ni siquiera llegó a tener respuesta (timeout,
            # DNS caído, sin conexión). Cubre también TimeoutException,
            # ConnectError, etc., porque todos heredan de RequestError.
            exc_data["httpx_details"] = {
                "url": str(exc.request.url) if exc.request else None,
                "method": exc.request.method if exc.request else None,
            }
        # Soporte para ExceptionGroup (Python 3.11+): recorrido de múltiples errores concurrentes
        if isinstance(exc, ExceptionGroup):
            exc_data["nested_exceptions"] = [
                self._serialize_exception(child) for child in exc.exceptions
            ]
        # Soporte para ExceptionGroup (Python 3.11+): recorrido de múltiples errores concurrentes
 main
        if isinstance(exc, ExceptionGroup):
            exc_data["nested_exceptions"] = [
                self._serialize_exception(nested_err)
                for nested_err in exc.exceptions
            ]
        # Soporte para encadenamiento explícito de errores ('raise ... from')
        elif exc.__cause__:
            exc_data["cause"] = self._serialize_exception(exc.__cause__)
integrante3


        # Soporte para encadenamiento explícito de errores ('raise ... from')
        elif exc.__cause__:
            exc_data["cause"] = self._serialize_exception(exc.__cause__)
 main
        return exc_data

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp ISO 8601 UTC estricto
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
 integrante3

=======
        # Generación de marca de tiempo estricta en formato ISO 8601 UTC (terminada en 'Z')
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
        # Payload principal estructurado en formato JSON con metadatos del sistema y tareas async
 main
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
            "process": record.process,
            "thread_name": record.threadName,
            "filename": record.filename,
            "line": record.lineno,
        }
 integrante3

        # Serialización del árbol de excepciones

        # Integración del árbol de excepciones si el registro contiene información de error
 main
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_value:
                log_payload["exception_tree"] = self._serialize_exception(exc_value)
 integrante3
                log_payload["stack_trace"] = self.formatException(record.exc_info)

        # Captura dinámica de metadatos inyectados vía 'extra'

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
 main
        reserved_fields = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName", "asctime",
        }
integrante3
        for key, value in record.__dict__.items():
            if key not in reserved_fields and not key.startswith('_'):
                log_payload[key] = value

        return json.dumps(log_payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# QueueHandler "seguro": el QueueHandler estándar de Python, antes de meter
# el LogRecord en la cola, lo aplana a texto plano y BORRA record.exc_info
# (lo deja en None) — ver logging.handlers.QueueHandler.prepare(). Esto
# rompería silenciosamente todo el árbol de excepciones que arma
# AsyncJSONFormatter, porque para cuando el formateador JSON procesa el
# record (en el QueueListener), record.exc_info ya no existe. Por eso acá
# se sobreescribe prepare() para que el record llegue intacto.
# ---------------------------------------------------------------------------
class PreservingQueueHandler(logging.handlers.QueueHandler):

        # Inyección dinámica de metadatos personalizados provistos mediante el parámetro 'extra'
        for key, value in record.__dict__.items():
            if key not in reserved_fields and not key.startswith('_'):
                log_payload[key] = value
        for key, value in record.__dict__.items():
            if key not in reserved_fields and not key.startswith('_'):
                log_payload[key] = value

        # Serialización final del diccionario a una cadena de texto JSON válida
        return json.dumps(log_payload, ensure_ascii=False)


# QueueHandler que preserva el exc_info real
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


integrante3
# ---------------------------------------------------------------------------
# Configuración del pipeline de logging (rotación + compresión + cola async)
# ---------------------------------------------------------------------------
def setup_triton_logging(log_filename: str = "triton_services.log") -> logging.Logger:
    """Configura el pipeline de logging declarativo dictConfig y acopla el listener asíncrono."""

def wire_non_blocking_pipeline(
    app_logger: logging.Logger,
) -> logging.handlers.QueueListener:
    
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
integrante3
    logging.config.dictConfig(logging_schema)
    app_logger = logging.getLogger("triton_monitor")

    # Inyección de las retrollamadas de compresión GZIP
    file_handler = next(
        (h for h in app_logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
        None,
    )
    if file_handler:
        file_handler.namer = gzip_namer
        file_handler.rotator = gzip_rotator

    # Desacoplamiento no bloqueante: QueueHandler + QueueListener
    log_queue = queue.Queue(-1)
    queue_handler = PreservingQueueHandler(log_queue)

    real_handlers = app_logger.handlers
    listener = logging.handlers.QueueListener(log_queue, *real_handlers, respect_handler_level=True)

    app_logger.handlers = [queue_handler]
    listener.start()
    app_logger.listener = listener

    return app_logger
  

    logging.config.dictConfig(logging_schema)
    app_logger = logging.getLogger("triton_monitor")

    wire_non_blocking_pipeline(app_logger)

    return app_logger
 main
