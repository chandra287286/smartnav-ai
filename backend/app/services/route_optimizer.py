"""
Dynamic Fastest-Route Optimization Engine.

Decision Logic:
IF current route is still the fastest (or no route passes safety/saving thresholds):
    Continue the current route.
ELSE IF an alternative saves a significant amount of time (or avoids a road closure):
    Either notify the user (recommend_switch) or switch automatically (auto_switch)
    respecting user preferences and rerouting cooldowns.
"""

import logging
import time
from typing import List, Optional

from app.schemas.geo import AlternativeRouteOption
from app.schemas.navigation import (
    OptimizationPreferences,
    OptimizeRouteResponse,
    RouteSwitchNotification,
)

logger = logging.getLogger("smartnav.optimizer")


def effective_eta_seconds(route: AlternativeRouteOption) -> float:
    if route.traffic.traffic_adjusted_duration_seconds is not None:
        return route.traffic.traffic_adjusted_duration_seconds
    return route.duration_seconds


def evaluate_route_switch(
    candidate_routes: List[AlternativeRouteOption],
    current_route_id: Optional[str] = None,
    current_route_remaining_seconds: Optional[float] = None,
    current_route_has_closure: bool = False,
    last_reroute_timestamp_ms: Optional[int] = None,
    preferences: Optional[OptimizationPreferences] = None,
    now_ms: Optional[int] = None,
) -> OptimizeRouteResponse:
    prefs = preferences or OptimizationPreferences()
    current_ms = now_ms if now_ms is not None else int(time.time() * 1000)

    if not candidate_routes:
        return OptimizeRouteResponse(
            decision="continue",
            reason="No alternative routes available to evaluate.",
            current_route_eta_seconds=current_route_remaining_seconds,
            evaluated_routes=[],
        )

    # Filter out toll routes if user opted to avoid tolls (keeping fallback if all have tolls)
    feasible_routes = candidate_routes
    if prefs.avoid_tolls:
        non_toll = [r for r in candidate_routes if not r.has_tolls]
        if non_toll:
            feasible_routes = non_toll

    # Identify current route baseline ETA
    current_route = next((r for r in candidate_routes if r.route_id == current_route_id), None)
    if current_route_remaining_seconds is not None and current_route_remaining_seconds > 0:
        cur_eta = float(current_route_remaining_seconds)
    elif current_route is not None:
        cur_eta = effective_eta_seconds(current_route)
    else:
        cur_eta = effective_eta_seconds(feasible_routes[0])

    cur_closed = current_route_has_closure or bool(
        current_route and current_route.traffic.has_road_closure
    )

    # Prefer open routes (no road closure)
    open_candidates = [r for r in feasible_routes if not r.traffic.has_road_closure]
    pool = open_candidates or feasible_routes

    if prefs.route_preference == "shortest":
        best_route = min(pool, key=lambda r: (r.distance_meters, effective_eta_seconds(r)))
    else:
        best_route = min(pool, key=effective_eta_seconds)

    best_eta = effective_eta_seconds(best_route)
    time_saved = round(cur_eta - best_eta, 1)
    rel_improvement = (time_saved / cur_eta) if cur_eta > 0 else 0.0

    # Update relative annotations on evaluated routes
    for r in feasible_routes:
        r_eta = effective_eta_seconds(r)
        r.is_fastest = r.route_id == best_route.route_id
        r.time_saved_vs_selected_seconds = round(cur_eta - r_eta, 1)

    cooldown_active = False
    if last_reroute_timestamp_ms is not None:
        elapsed_sec = (current_ms - last_reroute_timestamp_ms) / 1000.0
        if 0 <= elapsed_sec < prefs.reroute_cooldown_seconds:
            cooldown_active = True

    # If the best route IS the current route (and current isn't closed), continue
    if current_route_id and best_route.route_id == current_route_id and not cur_closed:
        return OptimizeRouteResponse(
            decision="continue",
            reason="Current route remains the fastest feasible option.",
            current_route_eta_seconds=cur_eta,
            best_route_eta_seconds=best_eta,
            time_saved_seconds=0.0,
            relative_improvement=0.0,
            cooldown_active=cooldown_active,
            evaluated_routes=feasible_routes,
        )

    # Anti-oscillation cooldown (bypassed only if current route is blocked by a road closure)
    if cooldown_active and not cur_closed:
        return OptimizeRouteResponse(
            decision="continue",
            reason=f"Rerouting cooldown ({prefs.reroute_cooldown_seconds}s) active to prevent route oscillation.",
            current_route_eta_seconds=cur_eta,
            best_route_eta_seconds=best_eta,
            time_saved_seconds=max(0.0, time_saved),
            relative_improvement=round(max(0.0, rel_improvement), 4),
            cooldown_active=True,
            evaluated_routes=feasible_routes,
        )

    meets_time_saving = time_saved >= prefs.min_time_saving_seconds
    meets_relative = rel_improvement >= prefs.min_relative_improvement
    significant_improvement = (meets_time_saving and meets_relative) or (cur_closed and not best_route.traffic.has_road_closure)

    if not significant_improvement:
        return OptimizeRouteResponse(
            decision="continue",
            reason=(
                f"Alternative saves {max(0, round(time_saved / 60, 1))} min "
                f"({round(max(0.0, rel_improvement) * 100, 1)}%), below threshold "
                f"({prefs.min_time_saving_seconds // 60} min & {int(prefs.min_relative_improvement * 100)}%)."
            ),
            current_route_eta_seconds=cur_eta,
            best_route_eta_seconds=best_eta,
            time_saved_seconds=max(0.0, time_saved),
            relative_improvement=round(max(0.0, rel_improvement), 4),
            cooldown_active=False,
            evaluated_routes=feasible_routes,
        )

    minutes_saved = max(1, round(time_saved / 60))
    if cur_closed:
        title = "Road closure detected ahead!"
        reason_text = f"Road closure on current route. Alternative Route {best_route.route_number} avoids closure."
    else:
        title = "Heavy traffic detected ahead!"
        reason_text = (
            f"Alternative Route {best_route.route_number} ({best_route.summary}) "
            f"is {minutes_saved} min faster."
        )

    decision = "auto_switch" if (prefs.auto_reroute and not prefs.manual_confirmation) else "recommend_switch"

    logger.info(
        "Optimizer decision=%s current_eta=%.1fs best_eta=%.1fs saved=%.1fs",
        decision,
        cur_eta,
        best_eta,
        time_saved,
    )

    return OptimizeRouteResponse(
        decision=decision,
        reason=reason_text,
        current_route_eta_seconds=cur_eta,
        best_route_eta_seconds=best_eta,
        time_saved_seconds=max(0.0, time_saved),
        relative_improvement=round(max(0.0, rel_improvement), 4),
        cooldown_active=False,
        notification=RouteSwitchNotification(
            title=title,
            message=reason_text,
            reason="road_closure" if cur_closed else "faster_alternative",
            current_route_eta_seconds=cur_eta,
            alternative_route_eta_seconds=best_eta,
            time_saved_seconds=max(0.0, time_saved),
            recommended_route=best_route,
        ),
        evaluated_routes=feasible_routes,
    )
