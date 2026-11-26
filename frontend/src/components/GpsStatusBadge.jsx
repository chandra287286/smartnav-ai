import React from 'react';
import { AlertCircle, Crosshair, Loader2, Radio, Square } from 'lucide-react';
import { GPS_STATUS } from '../hooks/useGeolocation';
import { formatSpeedKmh } from '../utils/geo';

export default function GpsStatusBadge({
  position,
  status,
  error,
  isTracking,
  onLocateOnce,
  onStartTracking,
  onStopTracking,
  onCenterOnGps,
  isNavigating,
}) {
  const speedKmh = formatSpeedKmh(position?.speed);

  return (
    <div className="flex flex-col items-end gap-2">
      {/* Error / Permission Banner */}
      {error && (
        <div className="max-w-xs bg-amber-50 dark:bg-amber-950/90 border border-amber-300 dark:border-amber-700 text-amber-900 dark:text-amber-100 rounded-xl px-3 py-2 shadow-map text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Telemetry pill when GPS fix exists (hidden when NavigationHUD handles bottom telemetry) */}
      {position && !isNavigating && (
        <button
          type="button"
          onClick={onCenterOnGps}
          title="Center map on your real GPS coordinates"
          className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-1.5 shadow-map text-[11px] text-slate-700 dark:text-slate-200 flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isTracking ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'
            }`}
          />
          <span className="font-mono">
            {position.lat.toFixed(5)}, {position.lng.toFixed(5)}
          </span>
          {typeof position.accuracy === 'number' && (
            <span className="text-slate-500 dark:text-slate-400">±{Math.round(position.accuracy)}m</span>
          )}
          {speedKmh !== null && <span className="text-blue-600 dark:text-blue-400">{speedKmh} km/h</span>}
          {typeof position.heading === 'number' && (
            <span className="text-slate-500 dark:text-slate-400">{Math.round(position.heading)}°</span>
          )}
        </button>
      )}

      {/* GPS Controls */}
      {!isNavigating && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => (isTracking ? onStopTracking() : onStartTracking())}
            title={isTracking ? 'Stop live GPS tracking' : 'Start continuous live GPS tracking'}
            className={`h-11 px-3.5 rounded-full shadow-map border text-xs font-semibold inline-flex items-center gap-1.5 transition ${
              isTracking
                ? 'bg-red-600 hover:bg-red-700 text-white border-red-600'
                : 'bg-white/95 dark:bg-slate-900/95 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-100 border-slate-200 dark:border-slate-700'
            }`}
          >
            {isTracking ? (
              <>
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop GPS
              </>
            ) : (
              <>
                <Radio className="w-4 h-4 text-emerald-600" />
                Live GPS
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onLocateOnce}
            title="Get current GPS position"
            aria-label="Current location"
            className="w-11 h-11 rounded-full bg-white/95 dark:bg-slate-900/95 hover:bg-slate-50 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-map flex items-center justify-center text-blue-600 dark:text-blue-400 transition"
          >
            {status === GPS_STATUS.REQUESTING ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Crosshair className="w-5 h-5" />
            )}
          </button>
        </div>
      )}
    </div>
  );
}
