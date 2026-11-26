import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowUpDown,
  Bike,
  Car,
  ChevronDown,
  ChevronUp,
  Crosshair,
  Footprints,
  Loader2,
  MapPin,
  Navigation,
  Route,
  Search,
  SlidersHorizontal,
  Star,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import RouteComparisonPanel from './RouteComparisonPanel';

const TRAVEL_MODES = [
  { id: 'driving', label: 'Drive', icon: Car },
  { id: 'cycling', label: 'Cycle', icon: Bike },
  { id: 'walking', label: 'Walk', icon: Footprints },
];

function LocationAutocompleteInput({
  value,
  onChangeText,
  onSelectSuggestion,
  placeholder,
  gpsPosition,
  icon,
  rightAction,
  ariaLabel,
}) {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);
  const skipNextFetchRef = useRef(false);

  useEffect(() => {
    const handleOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  useEffect(() => {
    if (skipNextFetchRef.current) {
      skipNextFetchRef.current = false;
      return;
    }
    const trimmed = value.trim();
    if (trimmed.length < 2 || trimmed === 'My Current GPS Location') {
      setSuggestions([]);
      setError('');
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      setError('');
      try {
        const res = await api.searchPlaces(trimmed, gpsPosition, controller.signal);
        const results = res?.results || [];
        setSuggestions(results);
        setIsOpen(true);
        if (results.length === 0) {
          setError('No matching places found. Try a more specific address or city.');
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Search failed.');
          setSuggestions([]);
        }
      } finally {
        setLoading(false);
      }
    }, 350);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, gpsPosition]);

  return (
    <div ref={containerRef} className="relative flex-1 min-w-0">
      <div className="flex items-center gap-2 bg-slate-100/90 dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700 rounded-xl px-3 py-2 focus-within:ring-2 focus-within:ring-blue-500 focus-within:bg-white dark:focus-within:bg-slate-900 transition">
        <span className="shrink-0 text-slate-400">{icon}</span>
        <input
          type="text"
          value={value}
          aria-label={ariaLabel || placeholder}
          placeholder={placeholder}
          onFocus={() => {
            if (suggestions.length > 0 || error) setIsOpen(true);
          }}
          onChange={(e) => {
            onChangeText(e.target.value);
          }}
          className="w-full bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
        />
        {loading && <Loader2 className="w-4 h-4 text-blue-600 animate-spin shrink-0" />}
        {value && !loading && (
          <button
            type="button"
            aria-label="Clear input"
            onClick={() => {
              onChangeText('');
              setSuggestions([]);
              setError('');
              setIsOpen(false);
            }}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5"
          >
            <X className="w-4 h-4" />
          </button>
        )}
        {rightAction}
      </div>

      {isOpen && (suggestions.length > 0 || error) && (
        <div className="absolute left-0 right-0 mt-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-map-lg z-50 max-h-64 overflow-y-auto custom-scrollbar">
          {error && suggestions.length === 0 ? (
            <div className="px-3.5 py-2.5 text-xs text-amber-700 dark:text-amber-300 bg-amber-50/70 dark:bg-amber-950/40">
              {error}
            </div>
          ) : (
            suggestions.map((item) => (
              <button
                key={`${item.place_id || item.lat}-${item.lng}`}
                type="button"
                onClick={() => {
                  skipNextFetchRef.current = true;
                  setIsOpen(false);
                  setSuggestions([]);
                  onSelectSuggestion({
                    lat: item.lat,
                    lng: item.lng,
                    label: item.display_name,
                    shortName: item.name || item.display_name.split(',')[0],
                    type: item.type,
                  });
                }}
                className="w-full text-left px-3.5 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/80 border-b last:border-b-0 border-slate-100 dark:border-slate-800 flex items-start gap-2.5 transition"
              >
                <MapPin className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                    {item.name || item.display_name.split(',')[0]}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                    {item.display_name}
                  </p>
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function SearchPanel({
  gpsPosition,
  directionsOpen,
  onToggleDirections,
  originText,
  onOriginTextChange,
  destinationText,
  onDestinationTextChange,
  onSelectOrigin,
  onSelectDestination,
  onSelectSearchPlace,
  onUseCurrentLocationAsOrigin,
  onSwapLocations,
  travelMode,
  onTravelModeChange,
  onCalculateRoutes,
  routes,
  selectedRouteIndex,
  onSelectRoute,
  routeLoading,
  routeError,
  trafficAvailable,
  trafficProvider,
  availabilityNote,
  onRefreshTraffic,
  refreshingTraffic,
  preferences,
  onUpdatePreferences,
  onStartNavigation,
  isNavigating,
  selectedPlace,
  onSaveFavorite,
  onClearRoute,
}) {
  const [quickSearchText, setQuickSearchText] = useState('');
  const [collapsedMobile, setCollapsedMobile] = useState(false);
  const [showPreferences, setShowPreferences] = useState(false);

  if (isNavigating) {
    return null;
  }

  return (
    <div className="w-full sm:w-[420px] max-w-full bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-2xl shadow-map border border-slate-200/80 dark:border-slate-700/80 overflow-visible">
      {!directionsOpen ? (
        <div className="p-2.5 flex items-center gap-2">
          <LocationAutocompleteInput
            value={quickSearchText}
            onChangeText={setQuickSearchText}
            onSelectSuggestion={(place) => {
              setQuickSearchText(place.shortName || place.label);
              onSelectSearchPlace(place);
            }}
            placeholder="Search places, addresses, landmarks..."
            ariaLabel="Search location"
            gpsPosition={gpsPosition}
            icon={<Search className="w-4 h-4 text-blue-600" />}
          />
          <button
            type="button"
            onClick={() => onToggleDirections(true)}
            title="Directions"
            aria-label="Open directions"
            className="shrink-0 h-10 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs sm:text-sm inline-flex items-center gap-1.5 shadow-sm transition"
          >
            <Route className="w-4 h-4" />
            <span className="hidden sm:inline">Directions</span>
          </button>
        </div>
      ) : (
        <div className="p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {TRAVEL_MODES.map((mode) => {
                const Icon = mode.icon;
                const active = travelMode === mode.id;
                return (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => onTravelModeChange(mode.id)}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition ${
                      active
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {mode.label}
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setShowPreferences((prev) => !prev)}
                title="Routing & Traffic Preferences"
                aria-label="Routing preferences"
                className={`p-1.5 rounded-lg transition ${
                  showPreferences
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                    : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setCollapsedMobile((prev) => !prev)}
                className="sm:hidden p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                aria-label="Toggle route panel"
              >
                {collapsedMobile ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              </button>
              <button
                type="button"
                onClick={() => {
                  onClearRoute();
                  onToggleDirections(false);
                }}
                aria-label="Close directions"
                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {showPreferences && preferences && (
            <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 space-y-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-700 dark:text-slate-300">Priority</span>
                <div className="flex items-center gap-1">
                  {['fastest', 'shortest'].map((pref) => (
                    <button
                      key={pref}
                      type="button"
                      onClick={() => onUpdatePreferences({ route_preference: pref })}
                      className={`px-2 py-1 rounded-md capitalize font-semibold ${
                        preferences.route_preference === pref
                          ? 'bg-blue-600 text-white'
                          : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
                      }`}
                    >
                      {pref}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <label className="inline-flex items-center gap-2 text-slate-700 dark:text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(preferences.avoid_tolls)}
                    onChange={(e) => onUpdatePreferences({ avoid_tolls: e.target.checked })}
                    className="rounded border-slate-300 text-blue-600"
                  />
                  Avoid toll roads
                </label>
                <label className="inline-flex items-center gap-2 text-slate-700 dark:text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(preferences.auto_reroute)}
                    onChange={(e) =>
                      onUpdatePreferences({
                        auto_reroute: e.target.checked,
                        manual_confirmation: !e.target.checked,
                      })
                    }
                    className="rounded border-slate-300 text-blue-600"
                  />
                  Auto-reroute
                </label>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <label className="space-y-0.5">
                  <span className="text-[10px] text-slate-500 dark:text-slate-400">
                    Traffic poll (sec)
                  </span>
                  <input
                    type="number"
                    min={15}
                    max={300}
                    value={preferences.monitor_interval_seconds}
                    onChange={(e) =>
                      onUpdatePreferences({
                        monitor_interval_seconds: Math.max(15, Number(e.target.value) || 45),
                      })
                    }
                    className="w-full px-2 py-1 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                  />
                </label>
                <label className="space-y-0.5">
                  <span className="text-[10px] text-slate-500 dark:text-slate-400">
                    Min saving (min)
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={Math.round((preferences.min_time_saving_seconds || 300) / 60)}
                    onChange={(e) =>
                      onUpdatePreferences({
                        min_time_saving_seconds: Math.max(1, Number(e.target.value) || 5) * 60,
                      })
                    }
                    className="w-full px-2 py-1 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                  />
                </label>
              </div>
            </div>
          )}

          {!collapsedMobile && (
            <>
              <div className="flex items-center gap-2">
                <div className="flex-1 space-y-2 min-w-0">
                  <LocationAutocompleteInput
                    value={originText}
                    onChangeText={onOriginTextChange}
                    onSelectSuggestion={onSelectOrigin}
                    placeholder="Choose starting point (or GPS)"
                    ariaLabel="Origin location"
                    gpsPosition={gpsPosition}
                    icon={<span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />}
                    rightAction={
                      <button
                        type="button"
                        onClick={onUseCurrentLocationAsOrigin}
                        title="Use my current GPS location"
                        aria-label="Use current GPS location"
                        className="text-blue-600 hover:text-blue-700 dark:text-blue-400 p-1 rounded-md hover:bg-blue-50 dark:hover:bg-blue-950/50 transition shrink-0"
                      >
                        <Crosshair className="w-4 h-4" />
                      </button>
                    }
                  />

                  <LocationAutocompleteInput
                    value={destinationText}
                    onChangeText={onDestinationTextChange}
                    onSelectSuggestion={onSelectDestination}
                    placeholder="Choose destination"
                    ariaLabel="Destination location"
                    gpsPosition={gpsPosition}
                    icon={<MapPin className="w-4 h-4 text-red-500" />}
                  />
                </div>

                <button
                  type="button"
                  onClick={onSwapLocations}
                  title="Swap origin and destination"
                  aria-label="Swap origin and destination"
                  className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-800 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition shrink-0"
                >
                  <ArrowUpDown className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onCalculateRoutes}
                  disabled={routeLoading}
                  className="flex-1 py-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium inline-flex items-center justify-center gap-2 shadow-sm transition"
                >
                  {routeLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Finding up to 5 routes & traffic...
                    </>
                  ) : (
                    <>
                      <Route className="w-4 h-4" />
                      Find Best & Alternative Routes
                    </>
                  )}
                </button>
              </div>

              {routeError && (
                <div className="p-2.5 rounded-xl bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-900 text-xs text-red-700 dark:text-red-300">
                  {routeError}
                </div>
              )}

              {Array.isArray(routes) && routes.length > 0 && (
                <>
                  <RouteComparisonPanel
                    routes={routes}
                    selectedRouteIndex={selectedRouteIndex}
                    onSelectRoute={onSelectRoute}
                    trafficAvailable={trafficAvailable}
                    trafficProvider={trafficProvider}
                    availabilityNote={availabilityNote}
                    onRefreshTraffic={onRefreshTraffic}
                    refreshingTraffic={refreshingTraffic}
                  />

                  <button
                    type="button"
                    onClick={onStartNavigation}
                    className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm inline-flex items-center justify-center gap-2 shadow-sm transition"
                  >
                    <Navigation className="w-4 h-4" />
                    Start Live Navigation
                  </button>
                </>
              )}
            </>
          )}
        </div>
      )}

      {/* Selected place preview bar when not in directions mode */}
      {!directionsOpen && selectedPlace && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
              {selectedPlace.shortName || selectedPlace.label}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{selectedPlace.label}</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => onSaveFavorite(selectedPlace)}
              title="Save place"
              className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition"
            >
              <Star className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => {
                onSelectDestination(selectedPlace);
                onToggleDirections(true);
              }}
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold inline-flex items-center gap-1"
            >
              <Navigation className="w-3.5 h-3.5" /> Go
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
