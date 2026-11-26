import React from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, X } from 'lucide-react';
import { formatDuration } from '../utils/geo';

export default function TrafficNotificationBanner({
  notification,
  onSwitchRoute,
  onContinueCurrent,
}) {
  if (!notification) return null;

  const minsSaved = Math.max(1, Math.round((notification.time_saved_seconds || 0) / 60));

  return (
    <div className="fixed top-28 left-3 right-3 sm:left-1/2 sm:-translate-x-1/2 sm:w-[480px] z-40 pointer-events-auto">
      <div className="bg-slate-900 dark:bg-slate-950 text-white rounded-2xl shadow-map-lg border border-amber-400/60 p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-amber-300">{notification.title}</h3>
              <p className="text-xs text-slate-200 mt-0.5">{notification.message}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onContinueCurrent}
            aria-label="Dismiss route switch suggestion"
            className="text-slate-400 hover:text-white p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center bg-slate-800/80 rounded-xl p-2.5 text-xs">
          <div>
            <p className="text-slate-400 text-[10px] uppercase">Current ETA</p>
            <p className="font-bold text-red-300">
              {formatDuration(notification.current_route_eta_seconds)}
            </p>
          </div>
          <div>
            <p className="text-slate-400 text-[10px] uppercase">Alternative ETA</p>
            <p className="font-bold text-emerald-400">
              {formatDuration(notification.alternative_route_eta_seconds)}
            </p>
          </div>
          <div>
            <p className="text-slate-400 text-[10px] uppercase">Time Saved</p>
            <p className="font-bold text-amber-300">{minsSaved} min</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onSwitchRoute(notification.recommended_route)}
            className="flex-1 py-2 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold inline-flex items-center justify-center gap-1.5 transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            Switch Route
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onContinueCurrent}
            className="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition"
          >
            Continue Current Route
          </button>
        </div>
      </div>
    </div>
  );
}
