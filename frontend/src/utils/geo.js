const EARTH_RADIUS_METERS = 6371000;

export function toRadians(deg) {
  return (deg * Math.PI) / 180;
}

export function isValidCoordinate(lat, lng) {
  return (
    typeof lat === 'number' &&
    typeof lng === 'number' &&
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

/**
 * Great-circle distance between two coordinates in meters (Haversine).
 * Used ONLY for local GPS progress, deviation detection, and formatting—never as road distance.
 */
export function haversineDistanceMeters(lat1, lng1, lat2, lng2) {
  if (!isValidCoordinate(lat1, lng1) || !isValidCoordinate(lat2, lng2)) {
    return Infinity;
  }
  const dLat = toRadians(lat2 - lat1);
  const dLng = toRadians(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return EARTH_RADIUS_METERS * c;
}

/**
 * Equirectangular local projection distance from point P to segment AB in meters.
 * Accurate for route deviation and snap-to-route checks over road-segment scales.
 */
export function pointToSegmentDistanceMeters(pLat, pLng, aLat, aLng, bLat, bLng) {
  const refLat = toRadians(pLat);
  const metersPerDegLat = 111132.92;
  const metersPerDegLng = 111320 * Math.cos(refLat);

  const px = (pLng - aLng) * metersPerDegLng;
  const py = (pLat - aLat) * metersPerDegLat;
  const bx = (bLng - aLng) * metersPerDegLng;
  const by = (bLat - aLat) * metersPerDegLat;

  const lenSq = bx * bx + by * by;
  if (lenSq === 0) {
    return { distance: Math.hypot(px, py), t: 0 };
  }

  let t = (px * bx + py * by) / lenSq;
  t = Math.max(0, Math.min(1, t));

  const projX = t * bx;
  const projY = t * by;
  const distance = Math.hypot(px - projX, py - projY);

  return { distance, t };
}

/**
 * Computes distance from a GPS coordinate to a route polyline (array of [lat, lng]),
 * along with remaining distance along the polyline from the closest projected point.
 */
export function computeRouteProgress(lat, lng, polylineLatLngs) {
  if (!Array.isArray(polylineLatLngs) || polylineLatLngs.length < 2) {
    return {
      distanceToRouteMeters: Infinity,
      remainingDistanceMeters: 0,
      progressFraction: 0,
      closestSegmentIndex: 0,
      projectedPoint: null,
    };
  }

  const segmentLengths = [];
  let totalLength = 0;
  for (let i = 0; i < polylineLatLngs.length - 1; i++) {
    const [aLat, aLng] = polylineLatLngs[i];
    const [bLat, bLng] = polylineLatLngs[i + 1];
    const segLen = haversineDistanceMeters(aLat, aLng, bLat, bLng);
    segmentLengths.push(segLen);
    totalLength += segLen;
  }

  let minDistance = Infinity;
  let bestIndex = 0;
  let bestT = 0;

  for (let i = 0; i < polylineLatLngs.length - 1; i++) {
    const [aLat, aLng] = polylineLatLngs[i];
    const [bLat, bLng] = polylineLatLngs[i + 1];
    const { distance, t } = pointToSegmentDistanceMeters(lat, lng, aLat, aLng, bLat, bLng);
    if (distance < minDistance) {
      minDistance = distance;
      bestIndex = i;
      bestT = t;
    }
  }

  const [aLat, aLng] = polylineLatLngs[bestIndex];
  const [bLat, bLng] = polylineLatLngs[bestIndex + 1];
  const projectedPoint = [aLat + (bLat - aLat) * bestT, aLng + (bLng - aLng) * bestT];

  let remainingDistanceMeters = segmentLengths[bestIndex] * (1 - bestT);
  for (let i = bestIndex + 1; i < segmentLengths.length; i++) {
    remainingDistanceMeters += segmentLengths[i];
  }

  const traveled = Math.max(0, totalLength - remainingDistanceMeters);
  const progressFraction = totalLength > 0 ? Math.min(1, Math.max(0, traveled / totalLength)) : 0;

  return {
    distanceToRouteMeters: minDistance,
    remainingDistanceMeters,
    totalPolylineMeters: totalLength,
    progressFraction,
    closestSegmentIndex: bestIndex,
    projectedPoint,
  };
}

/**
 * Splits a route polyline into traveledCoords and remainingCoords relative to a GPS position.
 */
export function sliceRouteProgressPolylines(lat, lng, polylineLatLngs) {
  if (!Array.isArray(polylineLatLngs) || polylineLatLngs.length < 2 || !isValidCoordinate(lat, lng)) {
    return { traveledCoords: [], remainingCoords: polylineLatLngs || [] };
  }
  const progress = computeRouteProgress(lat, lng, polylineLatLngs);
  const idx = progress.closestSegmentIndex;
  const splitPt = progress.projectedPoint || polylineLatLngs[idx];

  const traveledCoords = [...polylineLatLngs.slice(0, idx + 1), splitPt];
  const remainingCoords = [splitPt, ...polylineLatLngs.slice(idx + 1)];
  return { traveledCoords, remainingCoords };
}

export function getEffectiveRouteDuration(route) {
  if (!route) return 0;
  if (typeof route.traffic?.traffic_adjusted_duration_seconds === 'number') {
    return route.traffic.traffic_adjusted_duration_seconds;
  }
  return route.duration_seconds || 0;
}

export const CONGESTION_META = {
  low: {
    label: 'Low traffic',
    shortLabel: 'LOW TRAFFIC',
    color: '#16a34a',
    badgeClass: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800',
  },
  moderate: {
    label: 'Moderate traffic',
    shortLabel: 'MODERATE',
    color: '#f97316',
    badgeClass: 'bg-orange-100 text-orange-800 dark:bg-orange-950/70 dark:text-orange-300 border-orange-300 dark:border-orange-800',
  },
  heavy: {
    label: 'Heavy traffic',
    shortLabel: 'HEAVY',
    color: '#dc2626',
    badgeClass: 'bg-red-100 text-red-800 dark:bg-red-950/70 dark:text-red-300 border-red-300 dark:border-red-800',
  },
  severe: {
    label: 'Severe congestion',
    shortLabel: 'SEVERE',
    color: '#7f1d1d',
    badgeClass: 'bg-rose-950 text-rose-100 dark:bg-rose-950 dark:text-rose-200 border-rose-800',
  },
  unknown: {
    label: 'Live traffic unavailable',
    shortLabel: 'NO LIVE DATA',
    color: '#64748b',
    badgeClass: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700',
  },
};

export function getCongestionMeta(level) {
  return CONGESTION_META[level] || CONGESTION_META.unknown;
}

export function formatDistance(meters) {
  if (typeof meters !== 'number' || !Number.isFinite(meters)) return '—';
  if (meters < 1000) {
    return `${Math.round(meters)} m`;
  }
  const km = meters / 1000;
  return km >= 100 ? `${Math.round(km)} km` : `${(Math.round(meters / 100) / 10).toFixed(1)} km`;
}

export function formatDuration(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return '—';
  const totalMinutes = Math.max(1, Math.round(seconds / 60));
  if (totalMinutes < 60) {
    return `${totalMinutes} min`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  return mins === 0 ? `${hours} hr` : `${hours} hr ${mins} min`;
}

export function formatEtaClock(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return '—';
  const eta = new Date(Date.now() + seconds * 1000);
  return eta.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function formatIsoClock(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function formatSpeedKmh(speedMetersPerSec) {
  if (typeof speedMetersPerSec !== 'number' || !Number.isFinite(speedMetersPerSec) || speedMetersPerSec < 0) {
    return null;
  }
  return Math.round(speedMetersPerSec * 3.6);
}
