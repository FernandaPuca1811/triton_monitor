import argparse
import asyncio

from triton_telemetry import (
    setup_triton_logging,
    scan_all_providers,
    parse_timeout,
    parse_cluster_id,
    ProviderTimeoutError,
    NetworkPeeringError,
    CorruptedPayloadError,
    TritonError


 )

def build_cli_parser():

    parser = argparse.ArgumentParser(
        prog="TritonMonitor",
        description="Consola de Telemetría Multicloud y Observabilidad Asíncrona",
    )

    # Proveedores
    parser.add_argument(
        "proveedores",
        nargs="+",
        choices=["AWS", "Azure", "GCP"],
        help="Lista de proveedores cloud a monitorear",
    )

    # Cluster
    parser.add_argument(
        "-c",
        "--cluster-id",
        type=parse_cluster_id,
        required=True,
        help="ID del clúster de Kubernetes a monitorear",
    )

    # Timeout
    parser.add_argument(
        "-t",
        "--timeout",
        type=parse_timeout,
        default=2.5,
        help="Tiempo de espera en segundos para las solicitudes",
    )

    # Chaos
    parser.add_argument(
        "--chaos",
        action="store_true",
        help="Forzar inyección de caos real para pruebas",
    )

    # Mode
    parser.add_argument(
        "-m",
        "--mode",
        choices=["nominal", "debug", "emergency"],
        default="nominal",
        help="Modo de operación del despachador de telemetría",
    )

    return parser