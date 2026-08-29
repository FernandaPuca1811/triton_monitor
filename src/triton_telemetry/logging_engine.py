# src/triton_telemetry/logging_engine.py
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

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
        
        # Soporte para ExceptionGroup (Python 3.11+): recorrido de múltiples errores concurrentes
        if isinstance(exc, ExceptionGroup):
            exc_data["nested_exceptions"] = [
                self._serialize_exception(nested_err)
                for nested_err in exc.exceptions
            ]
        # Soporte para encadenamiento explícito de errores ('raise ... from')
        elif exc.__cause__:
            exc_data["cause"] = self._serialize_exception(exc.__cause__)
            
        return exc_data

    def format(self, record: logging.LogRecord) -> str:
        # Generación de marca de tiempo estricta en formato ISO 8601 UTC (terminada en 'Z')
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
        
        # Payload principal estructurado en formato JSON con metadatos del sistema y tareas async
        log_payload: Dict[str, Any] = {
            "timestamp": dt_utc.isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
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
                
        # Serialización final del diccionario a una cadena de texto JSON válida
        return json.dumps(log_payload, ensure_ascii=False)