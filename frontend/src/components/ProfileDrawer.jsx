import React, { useState } from 'react';
import { Clock, LogOut, MapPin, Navigation, RefreshCw, Star, Trash2, User, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { formatDistance, formatDuration } from '../utils/geo';

export default function ProfileDrawer({
  isOpen,
  onClose,
  onOpenAuth,
  onRouteToFavorite,
  onLoadHistoryRoute,
}) {
  const { user, isAuthenticated, favorites, history, logout, removeFavorite, refreshUserData } = useAuth();
  const [tab, setTab] = useState('favorites');
  const [refreshing, setRefreshing] = useState(false);

  if (!isOpen) return null;

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshUserData();
    setRefreshing(false);
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-950/35 backdrop-blur-[2px]">
      <div className="w-full max-w-sm bg-white dark:bg-slate-900 h-full shadow-map-lg border-l border-slate-200 dark:border-slate-800 flex flex-col">
        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-blue-600 text-white flex items-center justify-center font-semibold text-sm">
              {user ? user.full_name?.charAt(0)?.toUpperCase() || 'U' : <User className="w-4 h-4" />}
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                {user ? user.full_name : 'Guest Navigator'}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {user ? user.email : 'Sign in to sync saved places'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {isAuthenticated && (
              <button
                type="button"
                onClick={handleRefresh}
                title="Refresh saved data"
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close profile panel"
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {!isAuthenticated ? (
          <div className="p-6 flex-1 flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-50 dark:bg-blue-950/50 text-blue-600 flex items-center justify-center">
              <Star className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Save Favorite Places & Trips
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Sign in or create a free account to persist favorite destinations, route history, and live GPS
                navigation logs in PostgreSQL/PostGIS.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenAuth();
              }}
              className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold shadow-sm transition"
            >
              Sign In / Register
            </button>
          </div>
        ) : (
          <>
            <div className="px-4 pt-3 flex items-center gap-2 border-b border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setTab('favorites')}
                className={`pb-2.5 px-2 text-xs font-semibold border-b-2 transition ${
                  tab === 'favorites'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                Favorites ({favorites.length})
              </button>
              <button
                type="button"
                onClick={() => setTab('history')}
                className={`pb-2.5 px-2 text-xs font-semibold border-b-2 transition ${
                  tab === 'history'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                History ({history.routes.length + history.sessions.length})
              </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3">
              {tab === 'favorites' ? (
                favorites.length === 0 ? (
                  <p className="text-xs text-slate-500 dark:text-slate-400 text-center py-8">
                    No saved favorites yet. Tap the star icon on any search result or destination to save it here.
                  </p>
                ) : (
                  favorites.map((fav) => (
                    <div
                      key={fav.id}
                      className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/50 flex items-center justify-between gap-2"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
                          {fav.label}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                          {fav.address || `${fav.lat.toFixed(4)}, ${fav.lng.toFixed(4)}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            onRouteToFavorite({ lat: fav.lat, lng: fav.lng, label: fav.label });
                            onClose();
                          }}
                          title="Navigate here"
                          className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40"
                        >
                          <Navigation className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeFavorite(fav.id)}
                          title="Remove favorite"
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))
                )
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Navigation Sessions
                    </p>
                    {history.sessions.length === 0 ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400">No completed navigation sessions.</p>
                    ) : (
                      <div className="space-y-2">
                        {history.sessions.map((sess) => (
                          <div
                            key={sess.id}
                            className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-slate-900 dark:text-slate-100 capitalize">
                                {sess.status} ({sess.reroute_count} reroutes)
                              </span>
                              <span className="text-slate-400">
                                {new Date(sess.started_at).toLocaleDateString()}
                              </span>
                            </div>
                            <p className="text-slate-500 dark:text-slate-400 truncate">
                              {sess.destination_label || `${sess.dest_lat.toFixed(4)}, ${sess.dest_lng.toFixed(4)}`}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Recent Routes
                    </p>
                    {history.routes.length === 0 ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400">No route calculations logged yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {history.routes.map((rt) => (
                          <button
                            key={rt.id}
                            type="button"
                            onClick={() => {
                              onLoadHistoryRoute(rt);
                              onClose();
                            }}
                            className="w-full text-left p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/70 text-xs space-y-1 transition"
                          >
                            <div className="flex items-center justify-between text-slate-800 dark:text-slate-200 font-medium">
                              <span className="inline-flex items-center gap-1 truncate">
                                <MapPin className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                                {rt.destination_label || 'Saved Route'}
                              </span>
                              <span className="text-slate-400 shrink-0 ml-2 capitalize">{rt.profile}</span>
                            </div>
                            <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                              <Clock className="w-3.5 h-3.5" />
                              <span>
                                {formatDuration(rt.duration_seconds)} • {formatDistance(rt.distance_meters)}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => {
                  logout();
                  onClose();
                }}
                className="w-full py-2.5 px-4 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold inline-flex items-center justify-center gap-2 transition"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
