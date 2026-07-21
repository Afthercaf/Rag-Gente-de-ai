import { useState, useEffect, useRef } from 'react';
import { s, CLS } from '../../styles/theme';

export default function LocationPicker({ onLocationSelect, onClose }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [address, setAddress] = useState('');
  const [coordinates, setCoordinates] = useState(null);
  const hasSelected = useRef(false);
  const isMounted = useRef(true);
  const searchInputRef = useRef(null);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  const getCurrentLocation = () => {
    if (loading) return;

    setLoading(true);
    setError(null);

    if (!navigator.geolocation) {
      setError('Tu navegador no soporta geolocalización');
      setLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        if (!isMounted.current) return;
        const { latitude, longitude } = position.coords;
        setCoordinates({ lat: latitude, lng: longitude });
        await getAddressFromCoords(latitude, longitude);
        setLoading(false);
      },
      (err) => {
        if (!isMounted.current) return;
        let errorMessage = 'No se pudo obtener tu ubicación. ';
        switch (err.code) {
          case err.PERMISSION_DENIED:
            errorMessage += 'Permite el acceso a la ubicación.'; break;
          case err.POSITION_UNAVAILABLE:
            errorMessage += 'Información de ubicación no disponible.'; break;
          case err.TIMEOUT:
            errorMessage += 'Tiempo de espera agotado.'; break;
          default:
            errorMessage += 'Intenta nuevamente.';
        }
        setError(errorMessage);
        setLoading(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  const getAddressFromCoords = async (lat, lng) => {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&addressdetails=1&accept-language=es`,
        { headers: { 'Accept': 'application/json', 'User-Agent': 'Pizzeria220App/1.0' } }
      );
      const data = await response.json();
      if (data.display_name && isMounted.current && !hasSelected.current) {
        setAddress(data.display_name);
      }
    } catch (err) {
      console.error('Error reverse geocoding:', err);
      if (isMounted.current) {
        setError('No se pudo obtener la dirección exacta, pero puedes continuar');
        setAddress(`${lat}, ${lng}`);
      }
    }
  };

  const searchAddress = async (searchText) => {
    if (!searchText.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchText)}&limit=1&accept-language=es`,
        { headers: { 'Accept': 'application/json', 'User-Agent': 'Pizzeria220App/1.0' } }
      );
      const results = await response.json();
      if (results.length > 0 && isMounted.current) {
        const first = results[0];
        setCoordinates({ lat: parseFloat(first.lat), lng: parseFloat(first.lon) });
        setAddress(first.display_name);
      } else if (isMounted.current) {
        setError('No se encontró la dirección. Intenta con términos más específicos.');
      }
    } catch (err) {
      console.error('Error buscando dirección:', err);
      if (isMounted.current) setError('Error al buscar la dirección. Intenta nuevamente.');
    } finally {
      if (isMounted.current) setLoading(false);
    }
  };

  const handleConfirm = () => {
    if (hasSelected.current) return;
    if (coordinates && address) {
      hasSelected.current = true;
      onLocationSelect({
        lat: coordinates.lat,
        lng: coordinates.lng,
        direccion_completa: address,
        timestamp: new Date().toISOString(),
      });
      onClose();
    } else {
      setError('Primero selecciona una ubicación (usa "Usar mi ubicación" o escribe una dirección)');
    }
  };

  useEffect(() => {
    getCurrentLocation();
  }, []);

  return (
    <div className="p220-loc-overlay" style={s.locOverlay}>
      <div className={CLS.locModal} style={s.locModal}>

        {/* Header */}
        <div style={s.locHeader}>
          <span style={s.locTitle}>📍 Selecciona tu ubicación</span>
          <button
            className={CLS.closeBtn}
            style={s.locCloseBtn}
            onClick={() => { if (!loading && !hasSelected.current) onClose(); }}
            disabled={loading}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={s.locBody}>

          {/* Botón GPS */}
          <button
            className={CLS.gpsBtn}
            style={{ ...s.locGpsBtn, opacity: loading || hasSelected.current ? 0.5 : 1 }}
            onClick={getCurrentLocation}
            disabled={loading || hasSelected.current}
          >
            {loading ? '🔄 Obteniendo ubicación...' : '📍 Usar mi ubicación actual'}
          </button>

          {/* Búsqueda manual */}
          <div style={s.locSearchRow}>
            <input
              ref={searchInputRef}
              type="text"
              placeholder="O escribe tu dirección (ej: Calle Principal 123)"
              style={{
                ...s.locSearchInput,
                opacity: loading || hasSelected.current ? 0.5 : 1,
              }}
              disabled={loading || hasSelected.current}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !loading && !hasSelected.current) {
                  searchAddress(e.target.value);
                }
              }}
            />
            <button
              className={CLS.searchBtn}
              style={s.locSearchBtn}
              disabled={loading || hasSelected.current}
              onClick={() => {
                if (searchInputRef.current?.value && !loading && !hasSelected.current) {
                  searchAddress(searchInputRef.current.value);
                }
              }}
            >
              🔍
            </button>
          </div>

          {/* Error */}
          {error && (
            <div style={s.locError}>⚠️ {error}</div>
          )}

          {/* Dirección seleccionada */}
          {address && (
            <div style={s.locAddressCard}>
              <p style={s.locAddressLabel}>📍 Dirección seleccionada:</p>
              <p style={s.locAddressText}>{address}</p>
            </div>
          )}

          {/* Coordenadas */}
          {coordinates && (
            <div style={s.locCoordsCard}>
              📌 Coordenadas: {coordinates.lat.toFixed(6)}, {coordinates.lng.toFixed(6)}
            </div>
          )}

          {/* Mapa estático */}
          {coordinates && (
            <img
              src={`https://maps.locationiq.com/v3/staticmap?key=pk.5879fbb593bcbb0fea2d04f86e8933b8&center=${coordinates.lat},${coordinates.lng}&zoom=16&size=400x200&markers=${coordinates.lat},${coordinates.lng}`}
              alt="Mapa de ubicación"
              style={s.locMap}
              onError={(e) => (e.target.style.display = 'none')}
            />
          )}

          {/* Confirmar */}
          <button
            className={CLS.confirmBtn}
            style={
              hasSelected.current
                ? s.locConfirmBtnDone
                : { ...s.locConfirmBtn, opacity: !coordinates ? 0.5 : 1 }
            }
            onClick={handleConfirm}
            disabled={!coordinates || hasSelected.current}
          >
            {hasSelected.current ? '✓ Ubicación confirmada' : '✅ Confirmar ubicación'}
          </button>

        </div>
      </div>
    </div>
  );
}