import sys
import argparse
import asyncio

from triton_telemetry import { 
    setup_triton_logging,
    scan_todos_provedores,
    parse_timeout,
    parse_cluster_id,
    ProvTimeoutError,
    NetworkPeeringError,
    CorruptedPayLoadError,
    TritonError,


}

"""proveedores"""

def build_cli_parser():
    parser = argparse.ArgumentParser(
        prog="tTritonMonitor",
        description="Consola de Telemetría Multicloud y Observabilidad Asíncrona",
    )

    return parser


parser.add_argument(
    "proveedores",
    nargs="*",
    choices=["AWS", "GCP", "AZURE"],
)

"""cluester"""

parser.add_argument(
    "-c",
    "--cluster-id",
    type=parse_cluster_id,
    required=True,
    help="ID del clúster de Kubernetes a monitorear",
)

