import React from 'react';
import { AlertTriangle, Check, Clock, Gauge, Info, ShieldAlert, Sparkles, Zap } from 'lucide-react';
import {
  formatDistance,
  formatDuration,
  formatEtaClock,
  formatIsoClock,
  getCongestionMeta,
  getEffectiveRouteDuration,
} from '../utils/geo';

export default function RouteComparisonPanel({
  routes,
  selectedRouteIndex,
  onSelectRoute,
  trafficAvailable,
  trafficProvider,
  availabilityNote,
  onRefreshTraffic,
  refreshingTraffic,
}) {
  if (!Array.isArray(routes) || routes.length === 0) return null;

  const selectedRoute = routes[selectedRouteIndex] || routes[0];
  const selectedEta = getEffectiveRouteDuration(selectedRoute);

  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <span>{routes.length} Distinct Route{routes.length > 1 ? 's' : ''}</span>
          <span>•</span>
          {trafficAvailable ? (
            <span className="text-emerald-600 dark:text-emerald-400">
              Live Traffic ({trafficProvider})
            </span>
          ) : (
            <span className="text-amber-600 dark:text-amber-400">Live traffic unavailable</span>
          )}
        </div>
        {onRefreshTraffic && (
          <button
            type="button"
            onClick={onRefreshTraffic}
            disabled={refreshingTraffic}
            className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
          >
            {refreshingTraffic ? 'Refreshing...' : 'Refresh traffic'}
          </button>
        )}
      </div>

      {availabilityNote && (
        <div className="p-2.5 rounded-xl bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900 text-[11px] text-blue-800 dark:text-blue-200 flex items-start gap-2">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{availabilityNote}</span>
        </div>
      )}

      <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar pr-0.5">
        {routes.map((route, idx) => {
          const isSelected = idx === selectedRouteIndex;
          const traffic = route.traffic || {};
          const isLive = traffic.traffic_status === 'live';
          const effectiveSec = getEffectiveRouteDuration(route);
          const congMeta = getCongestionMeta(traffic.congestion_level);
          const timeDiff = selectedEta - effectiveSec; // > 0 means this route is faster than selected

          return (
            <div
              key={route.route_id || `route-${idx}`}
              onClick={() => onSelectRoute(idx)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') onSelectRoute(idx);
              }}
              className={`p-3 rounded-xl border transition cursor-pointer ${
                isSelected
                  ? 'border-blue-600 bg-blue-50/75 dark:bg-blue-950/40 shadow-sm'
                  : 'border-slate-200 dark:border-slate-700/80 hover:bg-slate-50 dark:hover:bg-slate-800/70'
              }`}
            >
              {/* Header: Route Number, Color Dot, Badges */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-3 h-3 rounded-full shrink-0 ring-2 ring-white dark:ring-slate-900"
                    style={{ backgroundColor: route.color || '#1a73e8' }}
                  />
                  <span className="text-xs font-bold text-slate-900 dark:text-slate-100 shrink-0">
                    Route {route.route_number || idx + 1}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {route.summary}
                  </span>
                </div>

                <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
                  {route.is_fastest && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-md bg-emerald-600 text-white text-[10px] font-bold">
                      <Zap className="w-2.5 h-2.5" />
                      FASTEST
                    </span>
                  )}
                  {isLive && traffic.congestion_level === 'low' && (
                    <span className="px-1.5 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-[10px] font-semibold">
                      LOW TRAFFIC
                    </span>
                  )}
                </div>
              </div>

              {/* Main Duration + Distance + Arrival Time */}
              <div className="mt-1.5 flex items-baseline justify-between gap-2">
                <div className="flex items-baseline gap-2">
                  <span className="text-base font-bold text-slate-900 dark:text-slate-100">
                    {formatDuration(effectiveSec)}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    ({formatDistance(route.distance_meters)})
                  </span>
                </div>
                <span className="text-xs font-medium text-slate-600 dark:text-slate-300 inline-flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-400" />
                  Arrive {traffic.estimated_arrival_iso ? formatIsoClock(traffic.estimated_arrival_iso) : formatEtaClock(effectiveSec)}
                </span>
              </div>

              {/* Traffic Summary Card Details */}
              <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1.5 text-[11px]">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border font-semibold ${congMeta.badgeClass}`}
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: congMeta.color }}
                    />
                    {isLive ? congMeta.label : 'Live traffic unavailable'}
                  </span>

                  {isLive && typeof traffic.traffic_delay_seconds === 'number' ? (
                    <span className="text-slate-600 dark:text-slate-300 font-medium">
                      {traffic.traffic_delay_seconds >= 60
                        ? `+${Math.round(traffic.traffic_delay_seconds / 60)} min delay`
                        : 'No major delay'}
                    </span>
                  ) : (
                    <span className="text-slate-500 dark:text-slate-400">
                      Base ETA {formatDuration(route.duration_seconds)}
                    </span>
                  )}
                </div>

                {/* Speed & Timestamp when live traffic is present */}
                {isLive && (
                  <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Gauge className="w-3 h-3" />
                      {traffic.current_speed_kmh ? `${traffic.current_speed_kmh} km/h` : '—'}
                      {traffic.normal_speed_kmh ? ` (normal ${traffic.normal_speed_kmh} km/h)` : ''}
                    </span>
                    {typeof traffic.confidence === 'number' && (
                      <span>Conf {Math.round(traffic.confidence * 100)}%</span>
                    )}
                  </div>
                )}

                {/* Predicted traffic ETA (explicitly labeled separately from live traffic) */}
                {typeof traffic.predicted_duration_seconds === 'number' && (
                  <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-indigo-500" />
                      {traffic.prediction_label || 'Predicted traffic'}:
                    </span>
                    <span className="font-medium text-slate-700 dark:text-slate-300">
                      {formatDuration(traffic.predicted_duration_seconds)}
                    </span>
                  </div>
                )}

                {/* Road closure warning */}
                {traffic.has_road_closure && (
                  <div className="flex items-center gap-1.5 text-red-700 dark:text-red-300 font-semibold">
                    <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
                    Road closure reported along this route
                  </div>
                )}

                {/* Comparison vs Selected Route & Select Button */}
                <div className="flex items-center justify-between pt-1">
                  <span className="font-medium">
                    {isSelected ? (
                      <span className="text-blue-600 dark:text-blue-400 inline-flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Selected route
                      </span>
                    ) : timeDiff >= 60 ? (
                      <span className="text-emerald-600 dark:text-emerald-400">
                        {Math.round(timeDiff / 60)} min faster than selected
                      </span>
                    ) : timeDiff <= -60 ? (
                      <span className="text-slate-500 dark:text-slate-400">
                        {Math.round(Math.abs(timeDiff) / 60)} min slower
                      </span>
                    ) : (
                      <span className="text-slate-500 dark:text-slate-400">Similar ETA</span>
                    )}
                  </span>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectRoute(idx);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition ${
                      isSelected
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-200/80 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-blue-600 hover:text-white'
                    }`}
                  >
                    {isSelected ? 'Selected' : 'Select Route'}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
