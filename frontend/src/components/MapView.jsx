import React, { memo, useEffect, useMemo } from 'react';
import L from 'leaflet';
import { Circle, MapContainer, Marker, Polyline, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import { Navigation, Star } from 'lucide-react';
import { formatDistance, sliceRouteProgressPolylines } from '../utils/geo';

const TILE_THEMES = {
  light: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  dark: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  terrain: {
    url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution:
      'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
  },
};

function createPinIcon(color, label) {
  return L.divIcon({
    className: 'custom-pin-icon',
    html: `
      <div style="display:flex;flex-direction:column;align-items:center;transform:translate(-50%,-100%);">
        <div style="width:30px;height:30px;border-radius:9999px;background:${color};border:2.5px solid #ffffff;box-shadow:0 3px 10px rgba(0,0,0,0.32);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:12px;">
          ${label}
        </div>
        <div style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:8px solid ${color};margin-top:-2px;"></div>
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
    popupAnchor: [0, -34],
  });
}

function createGpsIcon(heading) {
  const hasHeading = typeof heading === 'number' && !Number.isNaN(heading);
  const arrowHtml = hasHeading
    ? `<div style="position:absolute;top:-11px;left:50%;transform:translateX(-50%) rotate(${heading}deg);transform-origin:50% 21px;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:11px solid #1a73e8;filter:drop-shadow(0 1px 2px rgba(0,0,0,0.35));"></div>`
    : '';

  return L.divIcon({
    className: 'gps-live-marker',
    html: `
      <div style="position:relative;width:22px;height:22px;transform:translate(-50%,-50%);">
        <div class="gps-pulse-ring" style="position:absolute;inset:0;border-radius:9999px;background:rgba(26,115,232,0.35);"></div>
        ${arrowHtml}
        <div style="position:relative;width:18px;height:18px;margin:2px;border-radius:9999px;background:#1a73e8;border:3px solid #ffffff;box-shadow:0 2px 8px rgba(26,115,232,0.6);"></div>
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

function createNearbyIcon(color) {
  return L.divIcon({
    className: 'nearby-place-pin',
    html: `
      <div style="width:22px;height:22px;border-radius:9999px;background:${color};border:2px solid #ffffff;box-shadow:0 2px 6px rgba(0,0,0,0.28);transform:translate(-50%,-50%);display:flex;align-items:center;justify-content:center;">
        <div style="width:6px;height:6px;border-radius:9999px;background:#ffffff;"></div>
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
    popupAnchor: [0, -14],
  });
}

function createIncidentIcon(isClosure) {
  const bg = isClosure ? '#7f1d1d' : '#dc2626';
  const symbol = isClosure ? '⛔' : '!';
  return L.divIcon({
    className: 'traffic-incident-pin',
    html: `
      <div style="width:24px;height:24px;border-radius:9999px;background:${bg};border:2px solid #ffffff;box-shadow:0 2px 8px rgba(0,0,0,0.4);transform:translate(-50%,-50%);display:flex;align-items:center;justify-content:center;color:#ffffff;font-weight:800;font-size:12px;">
        ${symbol}
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
    popupAnchor: [0, -14],
  });
}

const ORIGIN_ICON = createPinIcon('#16a34a', 'A');
const DESTINATION_ICON = createPinIcon('#dc2626', 'B');
const SELECTED_PLACE_ICON = createPinIcon('#2563eb', '•');
const NEARBY_ICON = createNearbyIcon('#f97316');
const INCIDENT_ICON = createIncidentIcon(false);
const CLOSURE_ICON = createIncidentIcon(true);

function MapController({ centerTarget, fitBoundsCoords, followGps, gpsPosition, onUserPan }) {
  const map = useMap();

  useMapEvents({
    dragstart: () => {
      onUserPan?.();
    },
  });

  useEffect(() => {
    if (centerTarget && typeof centerTarget.lat === 'number' && typeof centerTarget.lng === 'number') {
      map.flyTo([centerTarget.lat, centerTarget.lng], centerTarget.zoom ?? Math.max(map.getZoom(), 15), {
        duration: 0.7,
      });
    }
  }, [map, centerTarget]);

  useEffect(() => {
    if (Array.isArray(fitBoundsCoords) && fitBoundsCoords.length >= 2) {
      const bounds = L.latLngBounds(fitBoundsCoords);
      if (bounds.isValid()) {
        map.fitBounds(bounds, {
          paddingTopLeft: [40, 90],
          paddingBottomRight: [40, 140],
          maxZoom: 16,
        });
      }
    }
  }, [map, fitBoundsCoords]);

  useEffect(() => {
    if (followGps && gpsPosition && typeof gpsPosition.lat === 'number' && typeof gpsPosition.lng === 'number') {
      map.panTo([gpsPosition.lat, gpsPosition.lng], { animate: true, duration: 0.5 });
    }
  }, [map, followGps, gpsPosition]);

  return null;
}

function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick?.({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

const MapView = memo(function MapView({
  mapTheme,
  gpsPosition,
  followGps,
  centerTarget,
  fitBoundsCoords,
  origin,
  destination,
  selectedPlace,
  routes,
  selectedRouteIndex,
  onSelectRoute,
  isNavigating,
  nearbyPlaces,
  onSelectNearbyAsDestination,
  onSaveFavorite,
  onMapClick,
  onUserPan,
  onMapReady,
}) {
  const tileConfig = TILE_THEMES[mapTheme] || TILE_THEMES.light;

  const gpsIcon = useMemo(
    () => createGpsIcon(gpsPosition?.heading ?? null),
    [gpsPosition?.heading]
  );

  const sortedRoutes = useMemo(() => {
    if (!Array.isArray(routes)) return [];
    return routes
      .map((route, idx) => ({ route, idx }))
      .sort((a, b) => {
        if (a.idx === selectedRouteIndex) return 1;
        if (b.idx === selectedRouteIndex) return -1;
        return 0;
      });
  }, [routes, selectedRouteIndex]);

  const activeRoute = routes?.[selectedRouteIndex] || null;

  const routeProgressSlices = useMemo(() => {
    if (!isNavigating || !gpsPosition || !activeRoute?.geometry_latlng) {
      return null;
    }
    return sliceRouteProgressPolylines(gpsPosition.lat, gpsPosition.lng, activeRoute.geometry_latlng);
  }, [isNavigating, gpsPosition, activeRoute]);

  const activeTrafficSegments = activeRoute?.traffic?.segments || [];
  const activeIncidents = activeRoute?.traffic?.incidents || [];

  return (
    <MapContainer
      center={[20.5937, 78.9629]}
      zoom={3}
      zoomControl={false}
      className={`h-full w-full ${mapTheme === 'dark' ? 'dark-map-tiles' : ''}`}
      whenReady={(ctx) => onMapReady?.(ctx.target)}
    >
      <TileLayer url={tileConfig.url} attribution={tileConfig.attribution} />

      <MapController
        centerTarget={centerTarget}
        fitBoundsCoords={fitBoundsCoords}
        followGps={followGps}
        gpsPosition={gpsPosition}
        onUserPan={onUserPan}
      />
      <MapClickHandler onMapClick={onMapClick} />

      {/* All up to 5 alternative routes rendered with distinct colors */}
      {sortedRoutes.map(({ route, idx }) => {
        const isActive = idx === selectedRouteIndex;
        const positions = route.geometry_latlng || [];
        if (positions.length < 2) return null;
        const routeColor = route.color || (isActive ? '#1a73e8' : '#64748b');

        if (isActive && routeProgressSlices) {
          return (
            <React.Fragment key={`active-progress-${route.route_id || idx}`}>
              {routeProgressSlices.traveledCoords.length >= 2 && (
                <Polyline
                  positions={routeProgressSlices.traveledCoords}
                  pathOptions={{
                    color: '#94a3b8',
                    weight: 6,
                    opacity: 0.65,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                />
              )}
              {routeProgressSlices.remainingCoords.length >= 2 && (
                <>
                  <Polyline
                    positions={routeProgressSlices.remainingCoords}
                    pathOptions={{
                      color: '#0f172a',
                      weight: 10,
                      opacity: 0.28,
                      lineCap: 'round',
                      lineJoin: 'round',
                    }}
                  />
                  <Polyline
                    positions={routeProgressSlices.remainingCoords}
                    pathOptions={{
                      color: routeColor,
                      weight: 6.5,
                      opacity: 0.95,
                      lineCap: 'round',
                      lineJoin: 'round',
                    }}
                  />
                </>
              )}
            </React.Fragment>
          );
        }

        return (
          <React.Fragment key={`route-${route.route_id || idx}`}>
            {isActive && (
              <Polyline
                positions={positions}
                pathOptions={{
                  color: '#0f172a',
                  weight: 10,
                  opacity: 0.25,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
            )}
            <Polyline
              positions={positions}
              pathOptions={{
                color: routeColor,
                weight: isActive ? 6.5 : 4.5,
                opacity: isActive ? 0.95 : 0.65,
                dashArray: isActive ? undefined : '7 7',
                lineCap: 'round',
                lineJoin: 'round',
              }}
              eventHandlers={{
                click: () => onSelectRoute?.(idx),
              }}
            />
          </React.Fragment>
        );
      })}

      {/* Traffic-colored road segments along the selected route when provider supplies them */}
      {activeTrafficSegments.map((seg, idx) =>
        Array.isArray(seg.coords_latlng) && seg.coords_latlng.length >= 2 ? (
          <Polyline
            key={`traffic-seg-${activeRoute?.route_id}-${idx}`}
            positions={seg.coords_latlng}
            pathOptions={{
              color: seg.color || '#16a34a',
              weight: 7,
              opacity: 0.9,
              lineCap: 'round',
              lineJoin: 'round',
            }}
          />
        ) : null
      )}

      {/* Traffic Incident & Road Closure Markers */}
      {activeIncidents.map((inc) => (
        <Marker
          key={`inc-${inc.id}`}
          position={[inc.lat, inc.lng]}
          icon={inc.is_road_closure ? CLOSURE_ICON : INCIDENT_ICON}
          zIndexOffset={900}
        >
          <Popup>
            <div className="text-xs max-w-[210px] space-y-1">
              <p className="font-bold text-red-700">
                {inc.is_road_closure ? 'Road Closure' : 'Traffic Incident'}
              </p>
              <p className="text-slate-700">{inc.description}</p>
              {inc.road_name && <p className="text-slate-500">Road: {inc.road_name}</p>}
              {typeof inc.delay_seconds === 'number' && inc.delay_seconds > 0 && (
                <p className="text-red-600 font-medium">
                  Delay: ~{Math.round(inc.delay_seconds / 60)} min
                </p>
              )}
            </div>
          </Popup>
        </Marker>
      ))}

      {/* Real GPS accuracy circle + live marker */}
      {gpsPosition && (
        <>
          {typeof gpsPosition.accuracy === 'number' && gpsPosition.accuracy > 0 && (
            <Circle
              center={[gpsPosition.lat, gpsPosition.lng]}
              radius={Math.min(gpsPosition.accuracy, 2000)}
              pathOptions={{
                color: '#1a73e8',
                weight: 1,
                fillColor: '#1a73e8',
                fillOpacity: 0.14,
              }}
            />
          )}
          <Marker position={[gpsPosition.lat, gpsPosition.lng]} icon={gpsIcon} zIndexOffset={1000}>
            <Popup>
              <div className="text-xs space-y-1">
                <p className="font-semibold text-slate-900">Your Live GPS Position</p>
                <p className="text-slate-600">
                  {gpsPosition.lat.toFixed(6)}, {gpsPosition.lng.toFixed(6)}
                </p>
                {gpsPosition.accuracy !== null && (
                  <p className="text-slate-600">Accuracy: ±{Math.round(gpsPosition.accuracy)} m</p>
                )}
              </div>
            </Popup>
          </Marker>
        </>
      )}

      {/* Origin Marker */}
      {origin && typeof origin.lat === 'number' && typeof origin.lng === 'number' && (
        <Marker position={[origin.lat, origin.lng]} icon={ORIGIN_ICON}>
          <Popup>
            <div className="text-xs max-w-[200px]">
              <p className="font-semibold text-emerald-700">Origin</p>
              <p className="text-slate-700 mt-0.5">
                {origin.label || `${origin.lat.toFixed(5)}, ${origin.lng.toFixed(5)}`}
              </p>
            </div>
          </Popup>
        </Marker>
      )}

      {/* Destination Marker */}
      {destination && typeof destination.lat === 'number' && typeof destination.lng === 'number' && (
        <Marker position={[destination.lat, destination.lng]} icon={DESTINATION_ICON}>
          <Popup>
            <div className="text-xs max-w-[220px] space-y-2">
              <div>
                <p className="font-semibold text-red-600">Destination</p>
                <p className="text-slate-700 mt-0.5">
                  {destination.label || `${destination.lat.toFixed(5)}, ${destination.lng.toFixed(5)}`}
                </p>
              </div>
              {onSaveFavorite && (
                <button
                  type="button"
                  onClick={() => onSaveFavorite(destination)}
                  className="inline-flex items-center gap-1 text-blue-600 hover:underline font-medium"
                >
                  <Star className="w-3.5 h-3.5" /> Save place
                </button>
              )}
            </div>
          </Popup>
        </Marker>
      )}

      {/* Selected Search Place (before directions) */}
      {selectedPlace && !destination && (
        <Marker position={[selectedPlace.lat, selectedPlace.lng]} icon={SELECTED_PLACE_ICON}>
          <Popup>
            <div className="text-xs max-w-[220px] space-y-2">
              <p className="font-semibold text-slate-900">{selectedPlace.label}</p>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => onSelectNearbyAsDestination?.(selectedPlace)}
                  className="inline-flex items-center gap-1 text-blue-600 hover:underline font-medium"
                >
                  <Navigation className="w-3.5 h-3.5" /> Directions
                </button>
                {onSaveFavorite && (
                  <button
                    type="button"
                    onClick={() => onSaveFavorite(selectedPlace)}
                    className="inline-flex items-center gap-1 text-amber-600 hover:underline font-medium"
                  >
                    <Star className="w-3.5 h-3.5" /> Save
                  </button>
                )}
              </div>
            </div>
          </Popup>
        </Marker>
      )}

      {/* Nearby Places Markers */}
      {Array.isArray(nearbyPlaces) &&
        nearbyPlaces.map((place) => (
          <Marker key={place.id} position={[place.lat, place.lng]} icon={NEARBY_ICON}>
            <Popup>
              <div className="text-xs max-w-[220px] space-y-1.5">
                <p className="font-semibold text-slate-900">{place.name}</p>
                <p className="text-slate-500 capitalize">
                  {place.category.replace('_', ' ')}
                  {typeof place.distance_meters === 'number' && ` • ${formatDistance(place.distance_meters)}`}
                </p>
                {place.address && <p className="text-slate-600">{place.address}</p>}
                <div className="flex items-center gap-3 pt-1">
                  <button
                    type="button"
                    onClick={() =>
                      onSelectNearbyAsDestination?.({
                        lat: place.lat,
                        lng: place.lng,
                        label: place.name,
                      })
                    }
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline font-medium"
                  >
                    <Navigation className="w-3.5 h-3.5" /> Route here
                  </button>
                  {onSaveFavorite && (
                    <button
                      type="button"
                      onClick={() =>
                        onSaveFavorite({
                          lat: place.lat,
                          lng: place.lng,
                          label: place.name,
                          category: place.category,
                        })
                      }
                      className="inline-flex items-center gap-1 text-amber-600 hover:underline font-medium"
                    >
                      <Star className="w-3.5 h-3.5" /> Save
                    </button>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
    </MapContainer>
  );
});

export default MapView;
