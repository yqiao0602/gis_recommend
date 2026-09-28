"""Export a deterministic QGIS Processing Registry snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _text_call(instance: object, *names: str, default: str = "unknown") -> str:
    for name in names:
        attribute = getattr(instance, name, None)
        if attribute is None:
            continue
        try:
            value = attribute() if callable(attribute) else attribute
        # Provider wrappers may raise arbitrary SIP/runtime errors for optional attributes.
        except Exception:  # noqa: BLE001, S112
            continue
        if value not in (None, ""):
            return str(value)
    return default


def _parameter_record(parameter: object, optional_flag: int) -> dict[str, Any]:
    try:
        flags = int(parameter.flags())
    except (AttributeError, TypeError, ValueError):
        flags = 0
    return {
        "name": _text_call(parameter, "name", default="<unnamed>"),
        "type": _text_call(parameter, "type", default="unknown"),
        "description": _text_call(parameter, "description", default=""),
        "optional": bool(flags & optional_flag),
    }


def _output_record(output: object) -> dict[str, Any]:
    return {
        "name": _text_call(output, "name", default="<unnamed>"),
        "type": _text_call(output, "type", default="unknown"),
        "description": _text_call(output, "description", default=""),
    }


def export_registry(
    output_path: Path,
    *,
    image_digest: str,
    exporter_sha256: str,
) -> dict[str, Any]:
    from processing.core.Processing import Processing
    from qgis.core import (
        Qgis,
        QgsApplication,
        QgsProcessingParameterDefinition,
    )

    application = QgsApplication([], False)
    application.initQgis()
    try:
        Processing.initialize()
        registry = QgsApplication.processingRegistry()
        optional_flag = int(QgsProcessingParameterDefinition.FlagOptional)
        providers: list[dict[str, Any]] = []
        provider_ids: set[str] = set()
        for provider in registry.providers():
            provider_id = _text_call(provider, "id", default="").lower()
            if not provider_id:
                continue
            provider_ids.add(provider_id)
            algorithms: list[dict[str, Any]] = []
            for algorithm in provider.algorithms():
                operator_id = _text_call(algorithm, "id", default="").lower()
                if not operator_id:
                    continue
                algorithms.append(
                    {
                        "operator_id": operator_id,
                        "display_name": _text_call(
                            algorithm, "displayName", "name", default=operator_id
                        ),
                        "parameters": sorted(
                            (
                                _parameter_record(parameter, optional_flag)
                                for parameter in algorithm.parameterDefinitions()
                            ),
                            key=lambda item: (item["name"], item["type"]),
                        ),
                        "outputs": sorted(
                            (
                                _output_record(output)
                                for output in algorithm.outputDefinitions()
                            ),
                            key=lambda item: (item["name"], item["type"]),
                        ),
                    }
                )
            providers.append(
                {
                    "provider_id": provider_id,
                    "name": _text_call(provider, "name", default=provider_id),
                    "active": bool(provider.isActive()),
                    "version": _text_call(
                        provider, "versionInfo", "version", default="builtin"
                    ),
                    "algorithms": sorted(
                        algorithms, key=lambda item: item["operator_id"]
                    ),
                }
            )

        for provider_id, name in (("grass7", "GRASS GIS 7"), ("saga", "SAGA")):
            if provider_id not in provider_ids:
                providers.append(
                    {
                        "provider_id": provider_id,
                        "name": name,
                        "active": False,
                        "version": "not_installed",
                        "algorithms": [],
                    }
                )

        payload = {
            "schema": "gis_recommend.qgis_registry_export.v1",
            "qgis_version": str(Qgis.QGIS_VERSION).split("-", 1)[0],
            "image_digest": image_digest,
            "exporter_sha256": exporter_sha256,
            "providers": sorted(
                providers, key=lambda item: item["provider_id"]
            ),
        }
        destination = Path(output_path)
        partial = destination.with_suffix(destination.suffix + ".partial")
        partial.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        partial.replace(destination)
        return payload
    finally:
        application.exitQgis()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--exporter-sha256", required=True)
    args = parser.parse_args()
    export_registry(
        args.output,
        image_digest=args.image_digest,
        exporter_sha256=args.exporter_sha256,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
