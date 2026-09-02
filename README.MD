# TP-1: Sistema de Telemetría Multicloud y Observabilidad Asíncrona (Proyecto Tritón)

## Descripción General del Proyecto
**Proyecto Tritón** es un monitor CLI de infraestructura cloud diseñado para evaluar en tiempo real la salud y el rendimiento de clústeres distribuidos en múltiples proveedores (**AWS, Azure y GCP**). El sistema implementa comunicación HTTP asíncrona, orquestación concurrente, manejo quirúrgico de excepciones con grupos (`ExceptionGroup` y `except*`), enriquecimiento forense con `add_note()`, y un pipeline de logging desacoplado y no bloqueante con rotación y compresión Gzip.

---

## Contribución Individual - Integrante 2: Ingeniero de Concurrencia y Telemetría Asíncrona

Como **Integrante 2**, asumí la responsabilidad del diseño, implementación y validación del motor central de red y concurrencia del proyecto, ubicado en el módulo [`src/triton_telemetry/core.py`](file:///c:/Users/ivang/OneDrive/Documentos/TP1-PROG2/src/triton_telemetry/core.py), su integración en [`src/triton_telemetry/__init__.py`](file:///c:/Users/ivang/OneDrive/Documentos/TP1-PROG2/src/triton_telemetry/__init__.py) y su suite de verificación automatizada en [`tests/test_core.py`](file:///c:/Users/ivang/OneDrive/Documentos/TP1-PROG2/tests/test_core.py).

A continuación, detallo en profundidad cada uno de los componentes y decisiones técnicas que desarrollé:

---

### 1. Consumo Asíncrono de APIs Reales (`httpx.AsyncClient`)
Para evitar simulaciones locales y apegarme a un escenario de producción real, implementé la corrutina `query_provider_telemetry(...)` utilizando la librería no bloqueante `httpx`.

* **Endpoints Nominales:** Configuré endpoints reales para verificar el estado de los tres proveedores cloud:
  * **AWS Status:** `https://jsonplaceholder.typicode.com/posts/1`
  * **Azure Status:** `https://jsonplaceholder.typicode.com/posts/2`
  * **GCP Status:** `https://jsonplaceholder.typicode.com/posts/3`
* **Métricas y Telemetría:**
  * Medí con alta precisión la latencia de respuesta en milisegundos empleando `time.perf_counter()`.
  * Extraje el código de estado HTTP (`response.status_code`), el cuerpo JSON deserializado (`payload`) y clasifiqué el estado operativo como `HEALTHY`.

---

### 2. Inyección de Caos y Manejo Forense de Errores de Red
Diseñé un sistema de tolerancia a fallos y resiliencia que captura excepciones nativas de transporte y las transforma en excepciones de dominio semánticas (diseñadas por el Integrante 1), garantizando **encadenamiento explícito (`raise ... from exc`)** para no perder el traceback original y **enriquecimiento forense con `add_note()`** (estándar moderno de Python 3.11+):

1. **Gatillo de Timeout Real (`ProviderTimeoutError`):**
   * Configuré el endpoint de retardo controlado `https://httpbin.org/delay/3` (3 segundos de delay).
   * Cuando se ejecuta con un timeout inferior (ej. `--timeout 1.0` o `0.5s`), `httpx` dispara de forma real un `httpx.TimeoutException`.
   * Capturé esta excepción, adjunté notas forenses (`exc.add_note(...)`) con el proveedor, tiempo límite y endpoint objetivo, y relancé la excepción como `ProviderTimeoutError` encadenada a la causa raíz.
2. **Gatillo de Estatus HTTP Erróneos (`CorruptedPayloadError`):**
   * Utilicé `response.raise_for_status()` para detectar respuestas HTTP no exitosas (códigos 4xx y 5xx).
   * Configuré endpoints de caos como `https://httpbin.org/status/504` (Gateway Timeout) y `https://httpbin.org/status/422` (Unprocessable Entity).
   * Al recibir un `httpx.HTTPStatusError`, adjunté una nota forense con el extracto de la respuesta del servidor y re-lancé un `CorruptedPayloadError` preservando la causa original con `from exc`.
3. **Fallo de Peering / DNS (`NetworkPeeringError`):**
   * Capturé errores de resolución de nombres y fallos de conexión (`httpx.ConnectError`, `httpx.NetworkError`), adjunté notas forenses descriptivas y los transformé en `NetworkPeeringError`.
4. **Captura Defensiva General (`TritonError`):**
   * Envolví cualquier otro error inesperado en `TritonError` con contexto forense para evitar fallos catastróficos no controlados.

---

### 3. Orquestación Concurrente con `asyncio.TaskGroup`
Implementé la función principal `scan_all_providers(...)` para orquestar la consulta simultánea de todos los proveedores configurados:

* **Gestor de Contexto Asíncrono:** Utilicé `async with httpx.AsyncClient() as client` y `async with asyncio.TaskGroup() as tg`.
* **Despacho de Tareas:** Creé dinámicamente las tareas con `tg.create_task(...)`, asignándoles nombres identificatorios (`name=f"task-telemetry-{provider.lower()}"`) para facilitar su trazabilidad y serialización en los logs estructurados (aprovechando `taskName` en Python 3.12+).
* **Propagación Quirúrgica:** Si una o varias tareas fallan, `TaskGroup` agrupa automáticamente todas las excepciones en un `ExceptionGroup` que viaja intacto hacia `app_operator.py` para su captura quirúrgica mediante bloques `except*`.

---

### 4. Empaquetado y Suite de Pruebas Automatizadas
* **Exposición en API Pública:** Actualicé [`src/triton_telemetry/__init__.py`](file:///c:/Users/ivang/OneDrive/Documentos/TP1-PROG2/src/triton_telemetry/__init__.py) exportando `query_provider_telemetry`, `scan_all_providers`, `NOMINAL_ENDPOINTS` y `CHAOS_ENDPOINTS` en `__all__`.
* **Suite de Pruebas (`tests/test_core.py`):**
  Desarrollé una suite de pruebas asíncrona automatizada que valida individualmente:
  1. Captura de `NetworkPeeringError` ante dominios inexistentes.
  2. Captura de `ProviderTimeoutError` con endpoint de delay y verificación de notas forenses (`__notes__`).
  3. Captura de `CorruptedPayloadError` ante respuestas HTTP 504.
  4. Escaneo concurrente exitoso de AWS, Azure y GCP en modo nominal con verificación de latencias y payloads.

---

## Ejecución de Pruebas

Para ejecutar las pruebas del módulo `core.py`:

```bash
python tests/test_core.py
```






### Integrante 5: Coordinador de Integración y Flujo CLI (app_operator.py)

Responsable de la unificación del sistema de telemetría, el diseño de la interfaz de consola de comandos, el inicio seguro del motor de logging declarativo y la gestión de la concurrencia asíncrona de red ante fallas múltiples.

#### 🛠️ Responsabilidades e Implementaciones Clave:
* **Punto de Entrada CLI Oficial (app_operator.py)**: Configuración de un analizador declarativo con argparse que inyecta directamente como tipos de datos los validadores del Integrante 1 (parse_cluster_id y parse_timeout). Esto asegura una validación en la frontera del sistema antes de iniciar el bucle de eventos. Cuenta con restricciones estrictas de dominio (choices) para los modos operativos (nominal, debug, emergency) y banderas opcionales de simulación de caos (--chaos).
* **Configuración Declarativa con dictConfig**: Diseño e inyección estructurada del esquema de configuración del pipeline de logging al arrancar la aplicación.
* **Captura Quirúrgica mediante except* (Python 3.11+)**: Implementación de la orquestación resiliente ante fallas simultáneas de red de los proveedores HTTP, procesando quirúrgicamente el ExceptionGroup propagado por el TaskGroup del Integrante 2:
    * except* ProviderTimeoutError as group: Captura los tiempos de espera agotados de los proveedores cloud de la API real y extrae dinámicamente las notas forenses inyectadas con .add_note().
    * except* NetworkPeeringError as group: Mitiga de manera segura pérdidas físicas de ruteo, DNS o transporte de red.
    * except* CorruptedPayloadError as group: Maneja formatos no serializables en JSON u otros errores lógicos sin tumbar la ejecución de la consola.
    * except* TritonError as group: Atrapa errores genéricos del ecosistema de telemetría no catalogados.
* **Cumplimiento de Estándares de Producción (PEP 765 / Python 3.14)**: Estructuración del bloque de limpieza finally para asegurar el apagado ordenado del listener de hilos del logger. Se eliminó estrictamente cualquier uso de directivas de control de flujo (return, break o continue) en finally para evitar silenciamientos ciegos de excepciones activas y la generación de advertencias del compilador.