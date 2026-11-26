import React from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Compass,
  Flag,
  Loader2,
  RefreshCw,
  RotateCw,
  Volume2,
  VolumeX,
  XCircle,
} from 'lucide-react';
import {
  formatDistance,
  formatDuration,
  formatEtaClock,
  formatIsoClock,
  formatSpeedKmh,
  getCongestionMeta,
} from '../utils/geo';

function ManeuverIcon({ type, modifier }) {
  const m = (modifier || '').toLowerCase();
  const t = (type || '').toLowerCase();

  if (t === 'arrive') return <Flag className="w-7 h-7" />;
  if (t === 'roundabout' || t === 'rotary') return <RotateCw className="w-7 h-7" />;
  if (m.includes('left')) return <ArrowLeft className="w-7 h-7" />;
  if (m.includes('right')) return <ArrowRight className="w-7 h-7" />;
  if (m.includes('uturn')) return <ArrowDown className="w-7 h-7" />;
  return <ArrowUp className="w-7 h-7" />;
}

export default function NavigationHUD({
  isNavigating,
  activeRoute,
  currentStep,
  distanceToNextStepMeters,
  remainingDistanceMeters,
  remainingDurationSeconds,
  isRerouting,
  deviationMeters,
  gpsPosition,
  isVoiceMuted,
  isVoiceSupported,
  onToggleVoice,
  onRecenter,
  onStopNavigation,
  lastTrafficCheckIso,
  trafficRefreshing,
  onManualTrafficCheck,
  autoRerouteEnabled,
  onToggleAutoReroute,
}) {
  if (!isNavigating) return null;

  const speedKmh = formatSpeedKmh(gpsPosition?.speed);
  const traffic = activeRoute?.traffic || {};
  const isLiveTraffic = traffic.traffic_status === 'live';
  const congMeta = getCongestionMeta(traffic.congestion_level);

  return (
    <>
      {/* Top Turn-by-Turn Guidance Banner */}
      <div className="fixed top-3 left-3 right-3 sm:left-1/2 sm:-translate-x-1/2 sm:w-[500px] z-30 pointer-events-auto">
        <div className="bg-emerald-700 dark:bg-emerald-800 text-white rounded-2xl shadow-map-lg p-3.5 border border-emerald-500/40">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-12 h-12 rounded-xl bg-emerald-900/50 flex items-center justify-center shrink-0">
                <ManeuverIcon type={currentStep?.maneuver_type} modifier={currentStep?.modifier} />
              </div>
              <div className="min-w-0">
                <p className="text-lg font-bold leading-tight">
                  {typeof distanceToNextStepMeters === 'number'
                    ? formatDistance(distanceToNextStepMeters)
                    : currentStep?.distance_meters
                    ? formatDistance(currentStep.distance_meters)
                    : 'Follow route'}
                </p>
                <p className="text-sm text-emerald-50 font-medium truncate">
                  {currentStep?.instruction || 'Proceed along highlighted route'}
                </p>
                {currentStep?.road_name && (
                  <p className="text-xs text-emerald-200 truncate mt-0.5">{currentStep.road_name}</p>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={onToggleVoice}
              disabled={!isVoiceSupported}
              title={
                !isVoiceSupported
                  ? 'Voice guidance unavailable in this browser'
                  : isVoiceMuted
                  ? 'Unmute voice navigation'
                  : 'Mute voice navigation'
              }
              aria-label={isVoiceMuted ? 'Unmute voice' : 'Mute voice'}
              className="p-2.5 rounded-xl bg-emerald-800/70 hover:bg-emerald-900/80 disabled:opacity-50 transition shrink-0"
            >
              {isVoiceMuted || !isVoiceSupported ? (
                <VolumeX className="w-5 h-5" />
              ) : (
                <Volume2 className="w-5 h-5" />
              )}
            </button>
          </div>

          {/* Live Traffic Strip inside Navigation Banner */}
          <div className="mt-2.5 pt-2 border-t border-emerald-600/60 flex items-center justify-between gap-2 flex-wrap text-[11px]">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/25 font-semibold">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: congMeta.color }} />
                {isLiveTraffic ? congMeta.label : 'Live traffic unavailable'}
              </span>
              {isLiveTraffic && typeof traffic.traffic_delay_seconds === 'number' && traffic.traffic_delay_seconds >= 60 && (
                <span className="text-amber-200 font-semibold">
                  +{Math.round(traffic.traffic_delay_seconds / 60)}m delay
                </span>
              )}
              {lastTrafficCheckIso && (
                <span className="text-emerald-200/90 hidden sm:inline">
                  Checked {formatIsoClock(lastTrafficCheckIso)}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5">
              {onToggleAutoReroute && (
                <button
                  type="button"
                  onClick={onToggleAutoReroute}
                  className={`px-2 py-0.5 rounded-md font-semibold transition ${
                    autoRerouteEnabled
                      ? 'bg-emerald-950/60 text-emerald-200 border border-emerald-400/40'
                      : 'bg-black/20 text-emerald-100'
                  }`}
                >
                  Auto-switch: {autoRerouteEnabled ? 'ON' : 'OFF'}
                </button>
              )}
              {onManualTrafficCheck && (
                <button
                  type="button"
                  onClick={onManualTrafficCheck}
                  disabled={trafficRefreshing}
                  title="Check traffic & faster alternatives now"
                  className="p-1 rounded-md bg-black/20 hover:bg-black/35 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${trafficRefreshing ? 'animate-spin' : ''}`} />
                </button>
              )}
            </div>
          </div>

          {isRerouting && (
            <div className="mt-2 px-3 py-1.5 rounded-xl bg-amber-500/25 border border-amber-300/40 flex items-center gap-2 text-xs font-medium text-amber-100">
              <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
              Off route ({Math.round(deviationMeters)} m away) — recalculating road route...
            </div>
          )}
          {!isRerouting && typeof deviationMeters === 'number' && deviationMeters > 45 && (
            <div className="mt-2 px-3 py-1 rounded-lg bg-amber-500/20 flex items-center gap-1.5 text-xs text-amber-100">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              Slight deviation detected ({Math.round(deviationMeters)} m)
            </div>
          )}
        </div>
      </div>

      {/* Bottom Live Telemetry & Controls */}
      <div className="fixed bottom-3 left-3 right-3 sm:left-1/2 sm:-translate-x-1/2 sm:w-[540px] z-30 pointer-events-auto">
        <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-2xl shadow-map-lg border border-slate-200 dark:border-slate-700 p-3.5 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-bold text-emerald-700 dark:text-emerald-400">
                {formatDuration(remainingDurationSeconds)}
              </span>
              <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                ({formatDistance(remainingDistanceMeters)})
              </span>
              {activeRoute?.route_number && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  Route {activeRoute.route_number}
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              <span>ETA {formatEtaClock(remainingDurationSeconds)}</span>
              {speedKmh !== null && <span>{speedKmh} km/h</span>}
              {typeof gpsPosition?.accuracy === 'number' && (
                <span>GPS ±{Math.round(gpsPosition.accuracy)} m</span>
              )}
              {typeof gpsPosition?.heading === 'number' && (
                <span>{Math.round(gpsPosition.heading)}°</span>
              )}
              <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <Activity className="w-3 h-3" /> Monitoring
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onRecenter}
              className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold inline-flex items-center gap-1.5 transition"
            >
              <Compass className="w-4 h-4 text-blue-600" />
              <span className="hidden sm:inline">Recenter</span>
            </button>
            <button
              type="button"
              onClick={onStopNavigation}
              className="px-3.5 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs sm:text-sm font-semibold inline-flex items-center gap-1.5 shadow-sm transition"
            >
              <XCircle className="w-4 h-4" />
              Stop
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
