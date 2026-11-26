import { useCallback, useEffect, useRef, useState } from 'react';

export const GPS_STATUS = {
  IDLE: 'idle',
  REQUESTING: 'requesting',
  ACTIVE: 'active',
  DENIED: 'denied',
  UNAVAILABLE: 'unavailable',
  TIMEOUT: 'timeout',
  UNSUPPORTED: 'unsupported',
  INSECURE_CONTEXT: 'insecure_context',
};

const DEFAULT_GEO_OPTIONS = {
  enableHighAccuracy: true,
  maximumAge: 2000,
  timeout: 15000,
};

function mapGeolocationError(err) {
  if (!err) {
    return {
      status: GPS_STATUS.UNAVAILABLE,
      message: 'Unable to read GPS location.',
    };
  }
  switch (err.code) {
    case 1: // PERMISSION_DENIED
      return {
        status: GPS_STATUS.DENIED,
        message:
          'Location permission was denied. Enable location access in your browser settings to use live GPS.',
      };
    case 2: // POSITION_UNAVAILABLE
      return {
        status: GPS_STATUS.UNAVAILABLE,
        message:
          'GPS position is currently unavailable. Ensure device GPS/Location Services are turned on and you have signal.',
      };
    case 3: // TIMEOUT
      return {
        status: GPS_STATUS.TIMEOUT,
        message: 'GPS request timed out while waiting for a high-accuracy fix. Move near a window or retry.',
      };
    default:
      return {
        status: GPS_STATUS.UNAVAILABLE,
        message: err.message || 'Unknown GPS error occurred.',
      };
  }
}

/**
 * Real Browser Geolocation API hook.
 * Uses getCurrentPosition, watchPosition, and clearWatch strictly without any IP fallback or simulated coordinates.
 */
export function useGeolocation(options = {}) {
  const highAccuracy = options.enableHighAccuracy ?? DEFAULT_GEO_OPTIONS.enableHighAccuracy;
  const maximumAge = options.maximumAge ?? DEFAULT_GEO_OPTIONS.maximumAge;
  const timeout = options.timeout ?? DEFAULT_GEO_OPTIONS.timeout;

  const [position, setPosition] = useState(null);
  const [status, setStatus] = useState(() => {
    if (typeof window === 'undefined' || !('geolocation' in navigator)) {
      return GPS_STATUS.UNSUPPORTED;
    }
    if (window.isSecureContext === false) {
      return GPS_STATUS.INSECURE_CONTEXT;
    }
    return GPS_STATUS.IDLE;
  });
  const [permissionState, setPermissionState] = useState('prompt');
  const [error, setError] = useState(null);
  const [isTracking, setIsTracking] = useState(false);

  const watchIdRef = useRef(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    if (typeof navigator !== 'undefined' && navigator.permissions?.query) {
      navigator.permissions
        .query({ name: 'geolocation' })
        .then((perm) => {
          if (!isMountedRef.current) return;
          setPermissionState(perm.state);
          if (perm.state === 'denied') {
            setStatus(GPS_STATUS.DENIED);
          }
          perm.onchange = () => {
            if (!isMountedRef.current) return;
            setPermissionState(perm.state);
            if (perm.state === 'denied') {
              setStatus(GPS_STATUS.DENIED);
            }
          };
        })
        .catch(() => {
          // Permissions API may be unavailable on some mobile browsers (e.g. iOS Safari)
        });
    }

    return () => {
      isMountedRef.current = false;
      if (watchIdRef.current !== null && typeof navigator !== 'undefined' && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, []);

  const checkAvailability = useCallback(() => {
    if (typeof window === 'undefined' || !('geolocation' in navigator) || !navigator.geolocation) {
      setStatus(GPS_STATUS.UNSUPPORTED);
      setError('This browser does not support the Geolocation API.');
      return false;
    }
    if (window.isSecureContext === false) {
      setStatus(GPS_STATUS.INSECURE_CONTEXT);
      setError(
        'Mobile browsers block GPS over plain HTTP. Serve the app over HTTPS (or localhost) to access real GPS.'
      );
      return false;
    }
    return true;
  }, []);

  const handleSuccess = useCallback((geoPos) => {
    if (!isMountedRef.current) return;
    const { latitude, longitude, accuracy, speed, heading, altitude } = geoPos.coords;
    setPosition({
      lat: latitude,
      lng: longitude,
      accuracy: typeof accuracy === 'number' ? accuracy : null,
      speed: typeof speed === 'number' && speed >= 0 ? speed : null,
      heading: typeof heading === 'number' && !Number.isNaN(heading) ? heading : null,
      altitude: typeof altitude === 'number' ? altitude : null,
      timestamp: geoPos.timestamp || Date.now(),
    });
    setError(null);
    setStatus(GPS_STATUS.ACTIVE);
  }, []);

  const handleError = useCallback((geoErr) => {
    if (!isMountedRef.current) return;
    const mapped = mapGeolocationError(geoErr);
    setStatus(mapped.status);
    setError(mapped.message);
    if (mapped.status === GPS_STATUS.DENIED) {
      setIsTracking(false);
      if (watchIdRef.current !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    }
  }, []);

  const locateOnce = useCallback(() => {
    if (!checkAvailability()) {
      return Promise.reject(new Error('Geolocation unavailable'));
    }

    setStatus(GPS_STATUS.REQUESTING);
    setError(null);

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (geoPos) => {
          handleSuccess(geoPos);
          resolve({
            lat: geoPos.coords.latitude,
            lng: geoPos.coords.longitude,
            accuracy: geoPos.coords.accuracy ?? null,
            speed: geoPos.coords.speed ?? null,
            heading: geoPos.coords.heading ?? null,
            timestamp: geoPos.timestamp || Date.now(),
          });
        },
        (geoErr) => {
          handleError(geoErr);
          reject(geoErr);
        },
        { enableHighAccuracy: highAccuracy, maximumAge, timeout }
      );
    });
  }, [checkAvailability, handleSuccess, handleError, highAccuracy, maximumAge, timeout]);

  const stopTracking = useCallback(() => {
    if (watchIdRef.current !== null && typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
    setIsTracking(false);
    setStatus((prev) => (prev === GPS_STATUS.ACTIVE || prev === GPS_STATUS.REQUESTING ? GPS_STATUS.IDLE : prev));
  }, []);

  const startTracking = useCallback(() => {
    if (!checkAvailability()) return false;

    // Prevent multiple unnecessary watchers
    if (watchIdRef.current !== null) {
      return true;
    }

    setStatus(GPS_STATUS.REQUESTING);
    setError(null);
    setIsTracking(true);

    watchIdRef.current = navigator.geolocation.watchPosition(handleSuccess, handleError, {
      enableHighAccuracy: highAccuracy,
      maximumAge,
      timeout,
    });
    return true;
  }, [checkAvailability, handleSuccess, handleError, highAccuracy, maximumAge, timeout]);

  return {
    position,
    status,
    permissionState,
    error,
    isTracking,
    locateOnce,
    startTracking,
    stopTracking,
  };
}
