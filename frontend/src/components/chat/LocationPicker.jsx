import { useEffect, useRef, useState } from "react";

import { apiBlobRequest, apiRequest } from "../../api/client";

import "../../styles/theme.css";


export default function LocationPicker({
  onLocationSelect,
  onClose,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [address, setAddress] = useState("");
  const [coordinates, setCoordinates] = useState(null);
  const [mapUrl, setMapUrl] = useState(null);

  const hasSelected = useRef(false);
  const isMounted = useRef(true);
  const searchInputRef = useRef(null);

  useEffect(() => {
    isMounted.current = true;

    return () => {
      isMounted.current = false;
      setMapUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return null;
      });
    };
  }, []);

  const getAddressFromCoords = async (lat, lng) => {
    try {
      const params = new URLSearchParams({
        lat: String(lat),
        lng: String(lng),
      });

      const data = await apiRequest(
        `/maps/reverse?${params.toString()}`,
      );

      if (
        data?.display_name &&
        isMounted.current &&
        !hasSelected.current
      ) {
        setAddress(data.display_name);
      }
    } catch {
      if (isMounted.current) {
        setError(
          "No se pudo obtener la dirección exacta, pero puedes continuar.",
        );
        setAddress(`${lat}, ${lng}`);
      }
    }
  };

  const getCurrentLocation = () => {
    if (loading || hasSelected.current) {
      return;
    }

    setLoading(true);
    setError(null);

    if (!navigator.geolocation) {
      setError(
        "Tu navegador no soporta geolocalización.",
      );
      setLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        if (!isMounted.current) {
          return;
        }

        const { latitude, longitude } =
          position.coords;

        setCoordinates({
          lat: latitude,
          lng: longitude,
        });

        await getAddressFromCoords(
          latitude,
          longitude,
        );

        if (isMounted.current) {
          setLoading(false);
        }
      },
      (geolocationError) => {
        if (!isMounted.current) {
          return;
        }

        let errorMessage =
          "No se pudo obtener tu ubicación. ";

        switch (geolocationError.code) {
          case geolocationError.PERMISSION_DENIED:
            errorMessage +=
              "Permite el acceso a la ubicación.";
            break;

          case geolocationError.POSITION_UNAVAILABLE:
            errorMessage +=
              "La información de ubicación no está disponible.";
            break;

          case geolocationError.TIMEOUT:
            errorMessage +=
              "Se agotó el tiempo de espera.";
            break;

          default:
            errorMessage +=
              "Intenta nuevamente.";
        }

        setError(errorMessage);
        setLoading(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      },
    );
  };

  const searchAddress = async (searchText) => {
    const normalizedSearch = searchText.trim();

    if (
      !normalizedSearch ||
      loading ||
      hasSelected.current
    ) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        q: normalizedSearch,
      });

      const data = await apiRequest(
        `/maps/search?${params.toString()}`,
      );

      if (!isMounted.current) {
        return;
      }

      if (
        Number.isFinite(data?.lat) &&
        Number.isFinite(data?.lng) &&
        data?.display_name
      ) {
        setCoordinates({
          lat: data.lat,
          lng: data.lng,
        });
        setAddress(data.display_name);
      } else {
        setError(
          "No se encontró la dirección. Usa términos más específicos.",
        );
      }
    } catch (requestError) {
      if (isMounted.current) {
        setError(
          requestError?.message ||
          "Error al buscar la dirección. Intenta nuevamente.",
        );
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  };

  const handleConfirm = () => {
    if (hasSelected.current) {
      return;
    }

    if (!coordinates || !address) {
      setError(
        'Primero selecciona una ubicación mediante GPS o escribe una dirección.',
      );
      return;
    }

    hasSelected.current = true;

    onLocationSelect({
      lat: coordinates.lat,
      lng: coordinates.lng,
      direccion_completa: address,
      timestamp: new Date().toISOString(),
    });

    onClose();
  };

  const handleClose = () => {
    if (!loading && !hasSelected.current) {
      onClose();
    }
  };

  useEffect(() => {
    getCurrentLocation();
    // Solo debe solicitar la ubicación al montar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadStaticMap() {
      if (!coordinates) {
        setMapUrl((current) => {
          if (current) {
            URL.revokeObjectURL(current);
          }
          return null;
        });
        return;
      }

      const params = new URLSearchParams({
        lat: String(coordinates.lat),
        lng: String(coordinates.lng),
        zoom: "16",
        width: "400",
        height: "200",
      });

      try {
        const blob = await apiBlobRequest(
          `/maps/static?${params.toString()}`,
        );

        if (cancelled || !isMounted.current) {
          return;
        }

        const nextUrl = URL.createObjectURL(blob);

        setMapUrl((current) => {
          if (current) {
            URL.revokeObjectURL(current);
          }
          return nextUrl;
        });
      } catch {
        if (!cancelled && isMounted.current) {
          setMapUrl((current) => {
            if (current) {
              URL.revokeObjectURL(current);
            }
            return null;
          });
        }
      }
    }

    loadStaticMap();

    return () => {
      cancelled = true;
    };
  }, [coordinates]);

  return (
    <div
      className="p220-loc-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="location-picker-title"
    >
      <div className="p220-loc-modal">
        <div className="p220-loc-header">
          <span
            id="location-picker-title"
            className="p220-loc-title"
          >
            📍 Selecciona tu ubicación
          </span>

          <button
            type="button"
            className="p220-close-btn"
            onClick={handleClose}
            disabled={loading}
            aria-label="Cerrar selector de ubicación"
          >
            ✕
          </button>
        </div>

        <div className="p220-loc-body">
          <button
            type="button"
            className="p220-gps-btn"
            style={{
              opacity:
                loading || hasSelected.current
                  ? 0.5
                  : 1,
            }}
            onClick={getCurrentLocation}
            disabled={
              loading || hasSelected.current
            }
          >
            {loading
              ? "🔄 Obteniendo ubicación..."
              : "📍 Usar mi ubicación actual"}
          </button>

          <div className="p220-loc-search-row">
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Ejemplo: Calle Principal 123"
              className="p220-loc-search-input"
              autoComplete="street-address"
              style={{
                opacity:
                  loading || hasSelected.current
                    ? 0.5
                    : 1,
              }}
              disabled={
                loading || hasSelected.current
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !loading &&
                  !hasSelected.current
                ) {
                  event.preventDefault();
                  searchAddress(event.currentTarget.value);
                }
              }}
            />

            <button
              type="button"
              className="p220-search-btn"
              disabled={
                loading || hasSelected.current
              }
              aria-label="Buscar dirección"
              onClick={() => {
                const value =
                  searchInputRef.current?.value;

                if (value) {
                  searchAddress(value);
                }
              }}
            >
              🔍
            </button>
          </div>

          {error && (
            <div
              className="p220-loc-error"
              role="alert"
            >
              ⚠️ {error}
            </div>
          )}

          {address && (
            <div className="p220-loc-address-card">
              <p className="p220-loc-address-label">
                📍 Dirección seleccionada:
              </p>

              <p className="p220-loc-address-text">
                {address}
              </p>
            </div>
          )}

          {coordinates && (
            <div className="p220-loc-coords-card">
              📌 Coordenadas:{" "}
              {coordinates.lat.toFixed(6)},{" "}
              {coordinates.lng.toFixed(6)}
            </div>
          )}

          {mapUrl && (
            <img
              src={mapUrl}
              alt="Mapa de la ubicación seleccionada"
              className="p220-loc-map"
              onError={(event) => {
                event.currentTarget.style.display =
                  "none";
              }}
            />
          )}

          <button
            type="button"
            className={`p220-confirm-btn${
              hasSelected.current
                ? " is-done"
                : ""
            }`}
            style={
              !hasSelected.current
                ? {
                    opacity: !coordinates
                      ? 0.5
                      : 1,
                  }
                : undefined
            }
            onClick={handleConfirm}
            disabled={
              !coordinates ||
              hasSelected.current ||
              loading
            }
          >
            {hasSelected.current
              ? "✓ Ubicación confirmada"
              : "✅ Confirmar ubicación"}
          </button>
        </div>
      </div>
    </div>
  );
}