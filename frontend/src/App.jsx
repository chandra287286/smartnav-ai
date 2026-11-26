import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layers, Minus, Moon, Plus, Sun, User } from 'lucide-react';
import AuthModal from './components/AuthModal';
import GpsStatusBadge from './components/GpsStatusBadge';
import MapView from './components/MapView';
import NavigationHUD from './components/NavigationHUD';
import NearbyPlacesBar from './components/NearbyPlacesBar';
import ProfileDrawer from './components/ProfileDrawer';
import SearchPanel from './components/SearchPanel';
import TrafficNotificationBanner from './components/TrafficNotificationBanner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { useGeolocation } from './hooks/useGeolocation';
import { useVoiceNavigation } from './hooks/useVoiceNavigation';
import { api } from './services/api';
import {
  computeRouteProgress,
  getEffectiveRouteDuration,
  haversineDistanceMeters,
} from './utils/geo';

const DEVIATION_THRESHOLD_METERS = 65;
const CONSECUTIVE_DEVIATIONS_REQUIRED = 2;
const REROUTE_COOLDOWN_MS = 12000;
const BACKEND_UPDATE_MIN_INTERVAL_MS = 5000;
const BACKEND_UPDATE_MIN_DISTANCE_METERS = 25;

const DEFAULT_PREFERENCES = {
  auto_reroute: false,
  manual_confirmation: true,
  avoid_tolls: false,
  route_preference: 'fastest',
  min_time_saving_seconds: 300,
  min_relative_improvement: 0.1,
  monitor_interval_seconds: 45,
  reroute_cooldown_seconds: 120,
};

function SmartNavWorkspace() {
  const { user, isAuthenticated, addFavorite, refreshUserData } = useAuth();
  const {
    position: gpsPosition,
    status: gpsStatus,
    error: gpsError,
    isTracking,
    locateOnce,
    startTracking,
    stopTracking,
  } = useGeolocation();
  const voice = useVoiceNavigation();

  // Map & Theme State
  const [mapTheme, setMapTheme] = useState('light');
  const [mapInstance, setMapInstance] = useState(null);
  const [centerTarget, setCenterTarget] = useState(null);
  const [fitBoundsCoords, setFitBoundsCoords] = useState(null);
  const [followGps, setFollowGps] = useState(false);

  // Search & Directions State
  const [directionsOpen, setDirectionsOpen] = useState(false);
  const [origin, setOrigin] = useState(null);
  const [originText, setOriginText] = useState('');
  const [destination, setDestination] = useState(null);
  const [destinationText, setDestinationText] = useState('');
  const [selectedPlace, setSelectedPlace] = useState(null);
  const [travelMode, setTravelMode] = useState('driving');

  // Multi-Route & Traffic State
  const [routes, setRoutes] = useState([]);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState('');
  const [trafficAvailable, setTrafficAvailable] = useState(false);
  const [trafficProvider, setTrafficProvider] = useState('none');
  const [availabilityNote, setAvailabilityNote] = useState(null);
  const [refreshingTraffic, setRefreshingTraffic] = useState(false);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);

  // Nearby Places State
  const [nearbyCategory, setNearbyCategory] = useState(null);
  const [nearbyPlaces, setNearbyPlaces] = useState([]);
  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [nearbyError, setNearbyError] = useState('');

  // Live Navigation & Traffic Monitoring State
  const [isNavigating, setIsNavigating] = useState(false);
  const [navSessionId, setNavSessionId] = useState(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [distanceToNextStepMeters, setDistanceToNextStepMeters] = useState(null);
  const [remainingDistanceMeters, setRemainingDistanceMeters] = useState(null);
  const [remainingDurationSeconds, setRemainingDurationSeconds] = useState(null);
  const [deviationMeters, setDeviationMeters] = useState(0);
  const [isRerouting, setIsRerouting] = useState(false);
  const [lastTrafficCheckIso, setLastTrafficCheckIso] = useState(null);
  const [switchNotification, setSwitchNotification] = useState(null);

  // UI Modals & Toast
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [toast, setToast] = useState(null);

  // Refs for cancellation, throttling & deviation hysteresis
  const hasCenteredInitialGpsRef = useRef(false);
  const consecutiveDeviationsRef = useRef(0);
  const lastRerouteAtRef = useRef(0);
  const lastTrafficSwitchAtRef = useRef(0);
  const lastBackendSyncRef = useRef({ time: 0, lat: null, lng: null });
  const routeAbortRef = useRef(null);
  const trafficMonitorAbortRef = useRef(null);

  const showToast = useCallback((message, tone = 'info') => {
    setToast({ message, tone });
    setTimeout(() => {
      setToast((prev) => (prev?.message === message ? null : prev));
    }, 4500);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', mapTheme === 'dark');
  }, [mapTheme]);

  // Center map smoothly on the user's very first real GPS fix
  useEffect(() => {
    if (gpsPosition && !hasCenteredInitialGpsRef.current && !destination && !selectedPlace) {
      hasCenteredInitialGpsRef.current = true;
      setCenterTarget({ lat: gpsPosition.lat, lng: gpsPosition.lng, zoom: 15, ts: Date.now() });
    }
  }, [gpsPosition, destination, selectedPlace]);

  const activeRoute = useMemo(() => routes[selectedRouteIndex] || null, [routes, selectedRouteIndex]);

  const updatePreferences = useCallback((patch) => {
    setPreferences((prev) => ({ ...prev, ...patch }));
  }, []);

  const handleCalculateRoutes = useCallback(
    async (customOrigin = null, customDestination = null, customMode = null, customPrefs = null) => {
      const orig = customOrigin || origin;
      const dest = customDestination || destination;
      const mode = customMode || travelMode;
      const prefs = customPrefs || preferences;

      if (!orig || typeof orig.lat !== 'number' || typeof orig.lng !== 'number') {
        setRouteError('Please select a valid starting location or tap the GPS icon.');
        return null;
      }
      if (!dest || typeof dest.lat !== 'number' || typeof dest.lng !== 'number') {
        setRouteError('Please select a valid destination.');
        return null;
      }

      if (routeAbortRef.current) {
        routeAbortRef.current.abort();
      }
      const controller = new AbortController();
      routeAbortRef.current = controller;

      setRouteLoading(true);
      setRouteError('');
      try {
        const res = await api.calculateAlternativeRoutes(
          { lat: orig.lat, lng: orig.lng, label: orig.label },
          { lat: dest.lat, lng: dest.lng, label: dest.label },
          {
            profile: mode,
            maxRoutes: 5,
            avoidTolls: prefs.avoid_tolls,
            preference: prefs.route_preference,
          },
          controller.signal
        );
        const fetchedRoutes = res?.routes || [];
        if (fetchedRoutes.length === 0) {
          setRouteError('No valid road route was found between these points.');
          setRoutes([]);
          return null;
        }
        setRoutes(fetchedRoutes);
        setSelectedRouteIndex(0);
        setTrafficAvailable(Boolean(res?.traffic_available));
        setTrafficProvider(res?.traffic_provider || 'none');
        setAvailabilityNote(res?.availability_note || null);

        const primary = fetchedRoutes[0];
        if (primary.geometry_latlng?.length >= 2) {
          setFitBoundsCoords(primary.geometry_latlng);
        }
        if (isAuthenticated) {
          refreshUserData();
        }
        return fetchedRoutes;
      } catch (err) {
        if (err.name !== 'AbortError') {
          setRouteError(err.message || 'Failed to calculate alternative routes.');
          setRoutes([]);
        }
        return null;
      } finally {
        setRouteLoading(false);
      }
    },
    [origin, destination, travelMode, preferences, isAuthenticated, refreshUserData]
  );

  const handleRefreshTraffic = useCallback(async () => {
    if (!routes.length) return;
    setRefreshingTraffic(true);
    try {
      await handleCalculateRoutes();
    } finally {
      setRefreshingTraffic(false);
    }
  }, [routes.length, handleCalculateRoutes]);

  const handleUseCurrentLocationAsOrigin = useCallback(async () => {
    try {
      const pos = gpsPosition || (await locateOnce());
      const nextOrigin = {
        lat: pos.lat,
        lng: pos.lng,
        label: 'My Current GPS Location',
      };
      setOrigin(nextOrigin);
      setOriginText('My Current GPS Location');
      setCenterTarget({ lat: pos.lat, lng: pos.lng, zoom: 15, ts: Date.now() });
      return nextOrigin;
    } catch {
      showToast('Could not obtain real GPS location. Check browser location permissions.', 'warning');
      return null;
    }
  }, [gpsPosition, locateOnce, showToast]);

  const handleSelectSearchPlace = useCallback((place) => {
    setSelectedPlace(place);
    setCenterTarget({ lat: place.lat, lng: place.lng, zoom: 15, ts: Date.now() });
  }, []);

  const handleRouteToPlace = useCallback(
    async (place) => {
      setSelectedPlace(null);
      setDestination(place);
      setDestinationText(place.shortName || place.label);
      setDirectionsOpen(true);

      let activeOrigin = origin;
      if (!activeOrigin && gpsPosition) {
        activeOrigin = {
          lat: gpsPosition.lat,
          lng: gpsPosition.lng,
          label: 'My Current GPS Location',
        };
        setOrigin(activeOrigin);
        setOriginText('My Current GPS Location');
      } else if (!activeOrigin) {
        // Attempt real GPS acquisition automatically if user hasn't picked an origin yet
        try {
          const pos = await locateOnce();
          activeOrigin = {
            lat: pos.lat,
            lng: pos.lng,
            label: 'My Current GPS Location',
          };
          setOrigin(activeOrigin);
          setOriginText('My Current GPS Location');
        } catch {
          // User can still choose origin manually
        }
      }

      if (activeOrigin) {
        await handleCalculateRoutes(activeOrigin, place, travelMode);
      } else {
        setCenterTarget({ lat: place.lat, lng: place.lng, zoom: 15, ts: Date.now() });
      }
    },
    [origin, gpsPosition, locateOnce, travelMode, handleCalculateRoutes]
  );

  const handleSwapLocations = useCallback(() => {
    setOrigin(destination);
    setDestination(origin);
    setOriginText(destinationText);
    setDestinationText(originText);
    setRoutes([]);
    setAvailabilityNote(null);
  }, [origin, destination, originText, destinationText]);

  const handleClearRoute = useCallback(() => {
    setRoutes([]);
    setRouteError('');
    setAvailabilityNote(null);
    setDestination(null);
    setDestinationText('');
  }, []);

  // Nearby Places lookup
  const handleSelectNearbyCategory = useCallback(
    async (categoryId) => {
      setNearbyCategory(categoryId);
      setNearbyLoading(true);
      setNearbyError('');

      let centerLatLng = gpsPosition ? { lat: gpsPosition.lat, lng: gpsPosition.lng } : null;
      if (!centerLatLng && mapInstance) {
        const c = mapInstance.getCenter();
        centerLatLng = { lat: c.lat, lng: c.lng };
      }
      if (!centerLatLng) {
        setNearbyLoading(false);
        setNearbyError('Move the map or enable GPS to search nearby places.');
        return;
      }

      try {
        const res = await api.getNearbyPlaces(centerLatLng.lat, centerLatLng.lng, categoryId, 2000);
        setNearbyPlaces(res?.places || []);
      } catch (err) {
        setNearbyError(err.message || 'Failed to load nearby places.');
        setNearbyPlaces([]);
      } finally {
        setNearbyLoading(false);
      }
    },
    [gpsPosition, mapInstance]
  );

  const handleClearNearby = useCallback(() => {
    setNearbyCategory(null);
    setNearbyPlaces([]);
    setNearbyError('');
  }, []);

  const handleSaveFavorite = useCallback(
    async (place) => {
      if (!isAuthenticated) {
        showToast('Sign in to save favorite places to your account.', 'info');
        setAuthModalOpen(true);
        return;
      }
      try {
        await addFavorite({
          label: place.shortName || place.label || 'Saved Location',
          address: place.label || null,
          lat: place.lat,
          lng: place.lng,
          category: place.category || 'favorite',
        });
        showToast('Saved to your favorites!', 'success');
      } catch (err) {
        showToast(err.message || 'Could not save favorite.', 'warning');
      }
    },
    [isAuthenticated, addFavorite, showToast]
  );

  const applyNewActiveRoute = useCallback(
    (newRoute, allCandidateRoutes = null) => {
      if (!newRoute) return;
      if (Array.isArray(allCandidateRoutes) && allCandidateRoutes.length > 0) {
        setRoutes(allCandidateRoutes);
        const matchIdx = allCandidateRoutes.findIndex((r) => r.route_id === newRoute.route_id);
        setSelectedRouteIndex(matchIdx >= 0 ? matchIdx : 0);
      } else {
        setRoutes([newRoute]);
        setSelectedRouteIndex(0);
      }
      setCurrentStepIndex(0);
      setRemainingDistanceMeters(newRoute.distance_meters);
      setRemainingDurationSeconds(getEffectiveRouteDuration(newRoute));
      setSwitchNotification(null);
      lastTrafficSwitchAtRef.current = Date.now();
      voice.resetHistory();
      if (newRoute.steps?.[0]?.instruction) {
        voice.speak(newRoute.steps[0].instruction, `switched-step-0-${Date.now()}`);
      }
    },
    [voice]
  );

  // Start Live Navigation Workflow
  const handleStartNavigation = useCallback(async () => {
    if (!activeRoute || !destination) {
      showToast('Calculate a route first before starting navigation.', 'warning');
      return;
    }

    let currentPos = gpsPosition;
    if (!currentPos) {
      try {
        currentPos = await locateOnce();
      } catch {
        showToast('Real GPS permission is required to start live navigation.', 'warning');
        return;
      }
    }

    startTracking();
    voice.resetHistory();
    consecutiveDeviationsRef.current = 0;
    lastRerouteAtRef.current = 0;
    lastTrafficSwitchAtRef.current = 0;
    lastBackendSyncRef.current = { time: Date.now(), lat: currentPos.lat, lng: currentPos.lng };
    setSwitchNotification(null);

    const initialEta = getEffectiveRouteDuration(activeRoute);
    setIsNavigating(true);
    setFollowGps(true);
    setCurrentStepIndex(0);
    setRemainingDistanceMeters(activeRoute.distance_meters);
    setRemainingDurationSeconds(initialEta);
    setDeviationMeters(0);
    setCenterTarget({ lat: currentPos.lat, lng: currentPos.lng, zoom: 17, ts: Date.now() });

    const firstStep = activeRoute.steps?.[0];
    if (firstStep?.instruction) {
      voice.speak(`Starting navigation. ${firstStep.instruction}`, 'nav-start');
    }

    try {
      const res = await api.startNavigation({
        origin_lat: currentPos.lat,
        origin_lng: currentPos.lng,
        dest_lat: destination.lat,
        dest_lng: destination.lng,
        origin_label: origin?.label || 'Current GPS Location',
        destination_label: destination.label || destinationText,
        profile: travelMode,
        route_distance_meters: activeRoute.distance_meters,
        route_duration_seconds: initialEta,
        selected_route_id: activeRoute.route_id,
      });
      setNavSessionId(res.session_id);
    } catch {
      setNavSessionId(null);
    }
  }, [
    activeRoute,
    destination,
    destinationText,
    gpsPosition,
    locateOnce,
    origin,
    showToast,
    startTracking,
    travelMode,
    voice,
  ]);

  const handleStopNavigation = useCallback(async () => {
    if (trafficMonitorAbortRef.current) {
      trafficMonitorAbortRef.current.abort();
    }
    setIsNavigating(false);
    setFollowGps(false);
    setIsRerouting(false);
    setSwitchNotification(null);
    voice.cancelSpeech();

    if (navSessionId) {
      try {
        await api.stopNavigation({ session_id: navSessionId, status: 'completed' });
        if (isAuthenticated) refreshUserData();
      } catch {
        // Ignore network errors when closing session
      }
      setNavSessionId(null);
    }
  }, [navSessionId, isAuthenticated, refreshUserData, voice]);

  // Dynamic Traffic Monitoring & Route Optimization Check
  const runTrafficMonitorAndOptimize = useCallback(
    async (forceRefresh = false) => {
      if (!isNavigating || !gpsPosition || !destination || !activeRoute) return;

      if (trafficMonitorAbortRef.current) {
        trafficMonitorAbortRef.current.abort();
      }
      const controller = new AbortController();
      trafficMonitorAbortRef.current = controller;

      setRefreshingTraffic(true);
      try {
        const monitorRes = await api.updateNavigationTraffic(
          {
            session_id: navSessionId,
            current_lat: gpsPosition.lat,
            current_lng: gpsPosition.lng,
            dest_lat: destination.lat,
            dest_lng: destination.lng,
            profile: travelMode,
            current_route_id: activeRoute.route_id,
            current_remaining_duration_seconds: remainingDurationSeconds,
            avoid_tolls: preferences.avoid_tolls,
            monitor_interval_seconds: preferences.monitor_interval_seconds,
            force_refresh: forceRefresh,
          },
          controller.signal
        );

        setLastTrafficCheckIso(monitorRes.checked_at_iso);
        setTrafficAvailable(Boolean(monitorRes.traffic_available));
        setTrafficProvider(monitorRes.traffic_provider || 'none');

        const candidateRoutes = monitorRes.routes || [];
        if (candidateRoutes.length === 0) return;

        const optRes = await api.optimizeNavigationRoute(
          {
            session_id: navSessionId,
            current_lat: gpsPosition.lat,
            current_lng: gpsPosition.lng,
            dest_lat: destination.lat,
            dest_lng: destination.lng,
            profile: travelMode,
            current_route_id: activeRoute.route_id,
            current_route_remaining_seconds: remainingDurationSeconds,
            current_route_has_closure: Boolean(activeRoute.traffic?.has_road_closure),
            last_reroute_timestamp_ms: lastTrafficSwitchAtRef.current || null,
            preferences,
            candidate_routes: candidateRoutes,
          },
          controller.signal
        );

        if (optRes.decision === 'auto_switch' && optRes.notification?.recommended_route) {
          applyNewActiveRoute(optRes.notification.recommended_route, candidateRoutes);
          voice.speak(optRes.notification.message, `auto-switch-${Date.now()}`);
          showToast(optRes.notification.message, 'info');
        } else if (optRes.decision === 'recommend_switch' && optRes.notification) {
          setSwitchNotification(optRes.notification);
          voice.speak(optRes.notification.message, `recommend-switch-${optRes.notification.recommended_route.route_id}`);
        } else if (monitorRes.refreshed) {
          // Update traffic visuals on alternative routes without interrupting active polyline
          setRoutes((prev) =>
            prev.map((r) => {
              const updated = candidateRoutes.find((c) => c.route_id === r.route_id);
              return updated ? { ...r, traffic: updated.traffic } : r;
            })
          );
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          // Keep current route intact if traffic update fails
        }
      } finally {
        setRefreshingTraffic(false);
      }
    },
    [
      isNavigating,
      gpsPosition,
      destination,
      activeRoute,
      navSessionId,
      travelMode,
      remainingDurationSeconds,
      preferences,
      applyNewActiveRoute,
      voice,
      showToast,
    ]
  );

  // Periodic background traffic monitoring while navigation is active
  useEffect(() => {
    if (!isNavigating) return undefined;
    const intervalMs = Math.max(15000, (preferences.monitor_interval_seconds || 45) * 1000);
    const id = setInterval(() => {
      runTrafficMonitorAndOptimize(false);
    }, intervalMs);

    return () => {
      clearInterval(id);
      if (trafficMonitorAbortRef.current) {
        trafficMonitorAbortRef.current.abort();
      }
    };
  }, [isNavigating, preferences.monitor_interval_seconds, runTrafficMonitorAndOptimize]);

  // Continuous live GPS tracking updates during active navigation
  useEffect(() => {
    if (!isNavigating || !gpsPosition || !activeRoute) return;

    const polyline = activeRoute.geometry_latlng || [];
    if (polyline.length < 2) return;

    const progress = computeRouteProgress(gpsPosition.lat, gpsPosition.lng, polyline);
    setDeviationMeters(progress.distanceToRouteMeters);

    const effectiveTotalDuration = getEffectiveRouteDuration(activeRoute);
    const ratio =
      progress.totalPolylineMeters > 0
        ? progress.remainingDistanceMeters / progress.totalPolylineMeters
        : 1;
    setRemainingDistanceMeters(progress.remainingDistanceMeters);
    setRemainingDurationSeconds(Math.max(10, Math.round(effectiveTotalDuration * ratio)));

    // Find upcoming maneuver step
    const steps = activeRoute.steps || [];
    if (steps.length > 0) {
      let bestStepIdx = currentStepIndex;
      let minManeuverDist = Infinity;
      for (let i = currentStepIndex; i < steps.length; i++) {
        const step = steps[i];
        if (typeof step.lat === 'number' && typeof step.lng === 'number') {
          const d = haversineDistanceMeters(gpsPosition.lat, gpsPosition.lng, step.lat, step.lng);
          if (d < minManeuverDist) {
            minManeuverDist = d;
            bestStepIdx = i;
          }
          if (d < 30 && i + 1 < steps.length) {
            bestStepIdx = i + 1;
          }
        }
      }

      if (bestStepIdx !== currentStepIndex) {
        setCurrentStepIndex(bestStepIdx);
      }

      const activeStep = steps[bestStepIdx];
      if (activeStep && typeof activeStep.lat === 'number' && typeof activeStep.lng === 'number') {
        const distToStep = haversineDistanceMeters(
          gpsPosition.lat,
          gpsPosition.lng,
          activeStep.lat,
          activeStep.lng
        );
        setDistanceToNextStepMeters(distToStep);

        if (activeStep.instruction) {
          if (distToStep <= 250 && distToStep > 60) {
            voice.speak(
              `In ${Math.round(distToStep / 10) * 10} meters, ${activeStep.instruction}`,
              `step-${bestStepIdx}-200`
            );
          } else if (distToStep <= 50) {
            voice.speak(activeStep.instruction, `step-${bestStepIdx}-now`);
          }
        }
      }
    }

    // Arrival check
    if (destination) {
      const distToDest = haversineDistanceMeters(
        gpsPosition.lat,
        gpsPosition.lng,
        destination.lat,
        destination.lng
      );
      if (distToDest <= 30) {
        voice.speak('You have arrived at your destination.', 'arrived');
        showToast('You have arrived at your destination!', 'success');
        handleStopNavigation();
        return;
      }
    }

    // Throttled backend telemetry update
    const now = Date.now();
    const movedMeters =
      lastBackendSyncRef.current.lat !== null
        ? haversineDistanceMeters(
            lastBackendSyncRef.current.lat,
            lastBackendSyncRef.current.lng,
            gpsPosition.lat,
            gpsPosition.lng
          )
        : Infinity;

    if (
      navSessionId &&
      (now - lastBackendSyncRef.current.time >= BACKEND_UPDATE_MIN_INTERVAL_MS ||
        movedMeters >= BACKEND_UPDATE_MIN_DISTANCE_METERS)
    ) {
      lastBackendSyncRef.current = { time: now, lat: gpsPosition.lat, lng: gpsPosition.lng };
      api
        .updateNavigation({
          session_id: navSessionId,
          lat: gpsPosition.lat,
          lng: gpsPosition.lng,
          accuracy_meters: gpsPosition.accuracy,
          speed_mps: gpsPosition.speed,
          heading_deg: gpsPosition.heading,
          remaining_distance_meters: progress.remainingDistanceMeters,
        })
        .catch(() => {});
    }

    // Route deviation & automatic rerouting (ignores noisy GPS fixes > 60m accuracy)
    const accuracyAcceptable = gpsPosition.accuracy === null || gpsPosition.accuracy <= 60;
    if (accuracyAcceptable && progress.distanceToRouteMeters > DEVIATION_THRESHOLD_METERS) {
      consecutiveDeviationsRef.current += 1;
    } else {
      consecutiveDeviationsRef.current = 0;
    }

    if (
      !isRerouting &&
      consecutiveDeviationsRef.current >= CONSECUTIVE_DEVIATIONS_REQUIRED &&
      now - lastRerouteAtRef.current >= REROUTE_COOLDOWN_MS &&
      destination
    ) {
      consecutiveDeviationsRef.current = 0;
      lastRerouteAtRef.current = now;
      setIsRerouting(true);
      voice.speak('Off route. Recalculating route.', `reroute-${now}`);

      api
        .rerouteNavigation({
          session_id: navSessionId,
          current_lat: gpsPosition.lat,
          current_lng: gpsPosition.lng,
          dest_lat: destination.lat,
          dest_lng: destination.lng,
          profile: travelMode,
          avoid_tolls: preferences.avoid_tolls,
          reason: 'deviation',
        })
        .then((res) => {
          const newRoutes = res?.routes || [];
          if (newRoutes.length > 0) {
            setRoutes(newRoutes);
            setSelectedRouteIndex(0);
            setCurrentStepIndex(0);
            setTrafficAvailable(Boolean(res?.traffic_available));
            setTrafficProvider(res?.traffic_provider || 'none');
            voice.resetHistory();
            const firstInstr = newRoutes[0]?.steps?.[0]?.instruction;
            if (firstInstr) {
              voice.speak(firstInstr, `rerouted-step-0-${now}`);
            }
          }
        })
        .catch(() => {
          showToast('Reroute failed temporarily; retrying on next GPS update.', 'warning');
        })
        .finally(() => {
          setIsRerouting(false);
        });
    }
  }, [
    isNavigating,
    gpsPosition,
    activeRoute,
    currentStepIndex,
    destination,
    navSessionId,
    isRerouting,
    travelMode,
    preferences.avoid_tolls,
    voice,
    showToast,
    handleStopNavigation,
  ]);

  const handleMapClick = useCallback(
    (latlng) => {
      if (isNavigating) return;
      if (directionsOpen && !destination) {
        const picked = {
          lat: latlng.lat,
          lng: latlng.lng,
          label: `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`,
        };
        setDestination(picked);
        setDestinationText(picked.label);
      }
    },
    [isNavigating, directionsOpen, destination]
  );

  const cycleMapTheme = useCallback(() => {
    setMapTheme((prev) => (prev === 'light' ? 'dark' : prev === 'dark' ? 'terrain' : 'light'));
  }, []);

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-slate-100 dark:bg-slate-950 select-none">
      {/* Fullscreen Interactive Map */}
      <MapView
        mapTheme={mapTheme}
        gpsPosition={gpsPosition}
        followGps={followGps}
        centerTarget={centerTarget}
        fitBoundsCoords={fitBoundsCoords}
        origin={origin}
        destination={destination}
        selectedPlace={selectedPlace}
        routes={routes}
        selectedRouteIndex={selectedRouteIndex}
        onSelectRoute={setSelectedRouteIndex}
        isNavigating={isNavigating}
        nearbyPlaces={nearbyPlaces}
        onSelectNearbyAsDestination={handleRouteToPlace}
        onSaveFavorite={handleSaveFavorite}
        onMapClick={handleMapClick}
        onUserPan={() => setFollowGps(false)}
        onMapReady={setMapInstance}
      />

      {/* Top Overlay: Search Panel + Nearby Categories + Profile Button */}
      {!isNavigating && (
        <div className="fixed top-3 left-3 right-3 z-20 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3 pointer-events-none">
          <div className="flex flex-col sm:flex-row sm:items-start gap-3 flex-1 min-w-0">
            <div className="pointer-events-auto w-full sm:w-auto">
              <SearchPanel
                gpsPosition={gpsPosition}
                directionsOpen={directionsOpen}
                onToggleDirections={setDirectionsOpen}
                originText={originText}
                onOriginTextChange={(val) => {
                  setOriginText(val);
                  if (!val) setOrigin(null);
                }}
                destinationText={destinationText}
                onDestinationTextChange={(val) => {
                  setDestinationText(val);
                  if (!val) setDestination(null);
                }}
                onSelectOrigin={(place) => {
                  setOrigin(place);
                  setOriginText(place.shortName || place.label);
                }}
                onSelectDestination={(place) => {
                  setDestination(place);
                  setDestinationText(place.shortName || place.label);
                }}
                onSelectSearchPlace={handleSelectSearchPlace}
                onUseCurrentLocationAsOrigin={handleUseCurrentLocationAsOrigin}
                onSwapLocations={handleSwapLocations}
                travelMode={travelMode}
                onTravelModeChange={(mode) => {
                  setTravelMode(mode);
                  if (origin && destination) {
                    handleCalculateRoutes(origin, destination, mode);
                  }
                }}
                onCalculateRoutes={() => handleCalculateRoutes()}
                routes={routes}
                selectedRouteIndex={selectedRouteIndex}
                onSelectRoute={setSelectedRouteIndex}
                routeLoading={routeLoading}
                routeError={routeError}
                trafficAvailable={trafficAvailable}
                trafficProvider={trafficProvider}
                availabilityNote={availabilityNote}
                onRefreshTraffic={handleRefreshTraffic}
                refreshingTraffic={refreshingTraffic}
                preferences={preferences}
                onUpdatePreferences={(patch) => {
                  const next = { ...preferences, ...patch };
                  updatePreferences(patch);
                  if (
                    origin &&
                    destination &&
                    ('avoid_tolls' in patch || 'route_preference' in patch)
                  ) {
                    handleCalculateRoutes(origin, destination, travelMode, next);
                  }
                }}
                onStartNavigation={handleStartNavigation}
                isNavigating={isNavigating}
                selectedPlace={selectedPlace}
                onSaveFavorite={handleSaveFavorite}
                onClearRoute={handleClearRoute}
              />
            </div>

            <div className="flex-1 min-w-0">
              <NearbyPlacesBar
                activeCategory={nearbyCategory}
                onSelectCategory={handleSelectNearbyCategory}
                places={nearbyPlaces}
                loading={nearbyLoading}
                error={nearbyError}
                onClear={handleClearNearby}
                onSelectPlace={(place) =>
                  setCenterTarget({ lat: place.lat, lng: place.lng, zoom: 16, ts: Date.now() })
                }
                onRouteToPlace={handleRouteToPlace}
                onSaveFavorite={handleSaveFavorite}
                isNavigating={isNavigating}
              />
            </div>
          </div>

          {/* Top-right Map Theme & Account Controls */}
          <div className="pointer-events-auto flex items-center gap-2 self-end lg:self-start shrink-0">
            <button
              type="button"
              onClick={cycleMapTheme}
              title={`Map layer: ${mapTheme.toUpperCase()} (click to switch)`}
              aria-label="Switch map theme"
              className="h-10 px-3 rounded-full bg-white/95 dark:bg-slate-900/95 border border-slate-200 dark:border-slate-700 shadow-map text-xs font-medium text-slate-700 dark:text-slate-200 inline-flex items-center gap-1.5 hover:bg-slate-50 dark:hover:bg-slate-800 transition"
            >
              {mapTheme === 'dark' ? (
                <Moon className="w-4 h-4 text-indigo-400" />
              ) : mapTheme === 'terrain' ? (
                <Layers className="w-4 h-4 text-emerald-600" />
              ) : (
                <Sun className="w-4 h-4 text-amber-500" />
              )}
              <span className="hidden sm:inline capitalize">{mapTheme}</span>
            </button>

            <button
              type="button"
              onClick={() => setProfileOpen(true)}
              aria-label="Open user profile and saved places"
              className="h-10 px-3 rounded-full bg-white/95 dark:bg-slate-900/95 border border-slate-200 dark:border-slate-700 shadow-map text-xs font-semibold text-slate-800 dark:text-slate-100 inline-flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition"
            >
              <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-[11px]">
                {user ? user.full_name?.charAt(0)?.toUpperCase() || 'U' : <User className="w-3.5 h-3.5" />}
              </span>
              <span className="hidden sm:inline">{user ? user.full_name.split(' ')[0] : 'Sign In'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Bottom-right Zoom & Real GPS Controls */}
      <div className="fixed bottom-4 right-3 z-20 flex flex-col items-end gap-2.5 pointer-events-auto">
        {!isNavigating && mapInstance && (
          <div className="hidden sm:flex flex-col bg-white/95 dark:bg-slate-900/95 border border-slate-200 dark:border-slate-700 rounded-xl shadow-map overflow-hidden">
            <button
              type="button"
              onClick={() => mapInstance.zoomIn()}
              aria-label="Zoom in"
              className="p-2 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 border-b border-slate-100 dark:border-slate-800"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => mapInstance.zoomOut()}
              aria-label="Zoom out"
              className="p-2 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>
        )}

        <GpsStatusBadge
          position={gpsPosition}
          status={gpsStatus}
          error={gpsError}
          isTracking={isTracking}
          onLocateOnce={() => {
            locateOnce()
              .then((pos) => {
                setCenterTarget({ lat: pos.lat, lng: pos.lng, zoom: 16, ts: Date.now() });
              })
              .catch(() => {});
          }}
          onStartTracking={() => {
            if (startTracking()) {
              setFollowGps(true);
            }
          }}
          onStopTracking={() => {
            stopTracking();
            setFollowGps(false);
          }}
          onCenterOnGps={() => {
            if (gpsPosition) {
              setFollowGps(true);
              setCenterTarget({ lat: gpsPosition.lat, lng: gpsPosition.lng, zoom: 16, ts: Date.now() });
            }
          }}
          isNavigating={isNavigating}
        />
      </div>

      {/* Smart Faster-Route Recommendation Notification */}
      <TrafficNotificationBanner
        notification={switchNotification}
        onSwitchRoute={(recommended) => {
          applyNewActiveRoute(recommended, routes);
          showToast(`Switched to Route ${recommended.route_number}`, 'success');
        }}
        onContinueCurrent={() => {
          lastTrafficSwitchAtRef.current = Date.now();
          setSwitchNotification(null);
        }}
      />

      {/* Live Navigation HUD */}
      <NavigationHUD
        isNavigating={isNavigating}
        activeRoute={activeRoute}
        currentStep={activeRoute?.steps?.[currentStepIndex] || null}
        distanceToNextStepMeters={distanceToNextStepMeters}
        remainingDistanceMeters={remainingDistanceMeters}
        remainingDurationSeconds={remainingDurationSeconds}
        isRerouting={isRerouting}
        deviationMeters={deviationMeters}
        gpsPosition={gpsPosition}
        isVoiceMuted={voice.isMuted}
        isVoiceSupported={voice.isSupported}
        onToggleVoice={voice.toggleMute}
        onRecenter={() => {
          if (gpsPosition) {
            setFollowGps(true);
            setCenterTarget({ lat: gpsPosition.lat, lng: gpsPosition.lng, zoom: 17, ts: Date.now() });
          }
        }}
        onStopNavigation={handleStopNavigation}
        lastTrafficCheckIso={lastTrafficCheckIso}
        trafficRefreshing={refreshingTraffic}
        onManualTrafficCheck={() => runTrafficMonitorAndOptimize(true)}
        autoRerouteEnabled={preferences.auto_reroute}
        onToggleAutoReroute={() =>
          updatePreferences({
            auto_reroute: !preferences.auto_reroute,
            manual_confirmation: preferences.auto_reroute,
          })
        }
      />

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full bg-slate-900 text-white text-xs font-medium shadow-map-lg">
          {toast.message}
        </div>
      )}

      {/* Auth Modal & Profile Drawer */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <ProfileDrawer
        isOpen={profileOpen}
        onClose={() => setProfileOpen(false)}
        onOpenAuth={() => setAuthModalOpen(true)}
        onRouteToFavorite={handleRouteToPlace}
        onLoadHistoryRoute={async (rt) => {
          const orig = { lat: rt.origin_lat, lng: rt.origin_lng, label: rt.origin_label || 'Origin' };
          const dest = { lat: rt.dest_lat, lng: rt.dest_lng, label: rt.destination_label || 'Destination' };
          setOrigin(orig);
          setOriginText(orig.label);
          setDestination(dest);
          setDestinationText(dest.label);
          setTravelMode(rt.profile || 'driving');
          setDirectionsOpen(true);
          await handleCalculateRoutes(orig, dest, rt.profile || 'driving');
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <SmartNavWorkspace />
    </AuthProvider>
  );
}
