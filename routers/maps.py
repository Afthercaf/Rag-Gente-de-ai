from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response


router = APIRouter(
    prefix="/maps",
    tags=["maps"],
)

LOCATIONIQ_API_KEY = os.getenv(
    "LOCATIONIQ_API_KEY",
)

REQUEST_TIMEOUT = (5, 15)


@router.get("/reverse")
def reverse_geocode(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> dict[str, Any]:
    response = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={
            "format": "json",
            "lat": lat,
            "lon": lng,
            "addressdetails": 1,
            "accept-language": "es",
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "Pizzeria220Backend/1.0",
        },
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "No fue posible consultar el servicio "
                "de geocodificación."
            ),
        )

    data = response.json()
    display_name = data.get("display_name")

    if not display_name:
        raise HTTPException(
            status_code=404,
            detail="No se encontró una dirección.",
        )

    return {
        "display_name": display_name,
        "lat": lat,
        "lng": lng,
    }


@router.get("/search")
def search_address(
    q: str = Query(
        min_length=3,
        max_length=200,
    ),
) -> dict[str, Any]:
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "format": "json",
            "q": q,
            "limit": 1,
            "accept-language": "es",
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "Pizzeria220Backend/1.0",
        },
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "No fue posible consultar el servicio "
                "de geocodificación."
            ),
        )

    results = response.json()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No se encontró la dirección.",
        )

    first = results[0]

    return {
        "display_name": first["display_name"],
        "lat": float(first["lat"]),
        "lng": float(first["lon"]),
    }


@router.get("/static")
def static_map(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    zoom: int = Query(default=16, ge=1, le=20),
    width: int = Query(default=400, ge=100, le=800),
    height: int = Query(default=200, ge=100, le=800),
) -> Response:
    if not LOCATIONIQ_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Servicio de mapas no configurado.",
        )

    response = requests.get(
        "https://maps.locationiq.com/v3/staticmap",
        params={
            "key": LOCATIONIQ_API_KEY,
            "center": f"{lat},{lng}",
            "zoom": zoom,
            "size": f"{width}x{height}",
            "markers": f"{lat},{lng}",
        },
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="No fue posible generar el mapa.",
        )

    content_type = response.headers.get(
        "content-type",
        "image/png",
    )

    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=502,
            detail="Respuesta de mapa inválida.",
        )

    return Response(
        content=response.content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=300",
        },
    )