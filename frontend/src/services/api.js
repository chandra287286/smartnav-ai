const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const TOKEN_STORAGE_KEY = 'smartnav_jwt_token';

export function getStoredToken() {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token) {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignore storage restriction errors
  }
}

async function request(path, options = {}) {
  const { method = 'GET', body, headers = {}, timeoutMs = 20000, signal } = options;
  const token = getStoredToken();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  const finalHeaders = {
    Accept: 'application/json',
    ...headers,
  };
  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
  }
  if (token) {
    finalHeaders.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : null;

    if (!response.ok) {
      const detail =
        payload?.detail ||
        payload?.message ||
        `Request failed (${response.status} ${response.statusText})`;
      const error = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return payload;
  } catch (err) {
    if (err.name === 'AbortError') {
      const abortErr = new Error('Request cancelled or timed out.');
      abortErr.name = 'AbortError';
      throw abortErr;
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  // Auth
  register: (data) => request('/auth/register', { method: 'POST', body: data }),
  login: (data) => request('/auth/login', { method: 'POST', body: data }),
  getProfile: () => request('/auth/profile'),

  // Search & Geocoding
  searchPlaces: (query, near = null, signal = null) => {
    const params = new URLSearchParams({ q: query });
    if (near && typeof near.lat === 'number' && typeof near.lng === 'number') {
      params.set('lat', String(near.lat));
      params.set('lng', String(near.lng));
    }
    return request(`/search?${params.toString()}`, { signal });
  },

  // Routing & Multi-Route Traffic Alternatives
  calculateRoutes: (origin, destination, profile = 'driving') =>
    request('/routes', {
      method: 'POST',
      body: { origin, destination, profile, alternatives: true },
    }),

  calculateAlternativeRoutes: (
    origin,
    destination,
    { profile = 'driving', maxRoutes = 5, avoidTolls = false, preference = 'fastest' } = {},
    signal = null
  ) =>
    request('/routes/alternatives', {
      method: 'POST',
      timeoutMs: 25000,
      signal,
      body: {
        origin,
        destination,
        profile,
        max_routes: maxRoutes,
        avoid_tolls: avoidTolls,
        preference,
      },
    }),

  getRouteTraffic: (routeId, profile = 'driving', forceRefresh = false) => {
    const params = new URLSearchParams({ profile, force_refresh: String(forceRefresh) });
    return request(`/routes/${encodeURIComponent(routeId)}/traffic?${params.toString()}`);
  },

  // Nearby Places
  getNearbyPlaces: (lat, lng, category = 'restaurant', radius = 1500) => {
    const params = new URLSearchParams({
      lat: String(lat),
      lng: String(lng),
      category,
      radius: String(radius),
    });
    return request(`/places/nearby?${params.toString()}`, { timeoutMs: 20000 });
  },

  // Live Navigation & Dynamic Traffic Optimization
  startNavigation: (payload) => request('/navigation/start', { method: 'POST', body: payload }),
  updateNavigation: (payload) => request('/navigation/update', { method: 'POST', body: payload }),
  rerouteNavigation: (payload) => request('/navigation/reroute', { method: 'POST', body: payload }),
  stopNavigation: (payload) => request('/navigation/stop', { method: 'POST', body: payload }),

  updateNavigationTraffic: (payload, signal = null) =>
    request('/navigation/traffic/update', { method: 'POST', body: payload, signal, timeoutMs: 25000 }),

  compareNavigationRoutes: (payload) =>
    request('/navigation/compare-routes', { method: 'POST', body: payload, timeoutMs: 25000 }),

  optimizeNavigationRoute: (payload, signal = null) =>
    request('/navigation/optimize-route', { method: 'POST', body: payload, signal, timeoutMs: 25000 }),

  getNavigationStatus: (sessionId) =>
    request(`/navigation/status?session_id=${encodeURIComponent(sessionId)}`),

  getNavigationTrafficSummary: (sessionId) =>
    request(`/navigation/traffic-summary?session_id=${encodeURIComponent(sessionId)}`),

  // Saved Favorites & History
  getFavorites: () => request('/favorites'),
  addFavorite: (payload) => request('/favorites', { method: 'POST', body: payload }),
  deleteFavorite: (id) => request(`/favorites/${id}`, { method: 'DELETE' }),
  getHistory: () => request('/history'),
};
