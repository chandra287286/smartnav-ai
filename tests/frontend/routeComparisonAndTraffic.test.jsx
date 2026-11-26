import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RouteComparisonPanel from '../../frontend/src/components/RouteComparisonPanel';
import TrafficNotificationBanner from '../../frontend/src/components/TrafficNotificationBanner';
import { sliceRouteProgressPolylines } from '../../frontend/src/utils/geo';

const SAMPLE_ROUTES = [
  {
    route_id: 'rt-1',
    route_number: 1,
    color: '#1a73e8',
    summary: 'Highway 101',
    distance_meters: 12000,
    duration_seconds: 720,
    is_fastest: true,
    traffic: {
      provider: 'tomtom',
      traffic_status: 'live',
      traffic_label: 'Live traffic',
      congestion_level: 'low',
      color: '#16a34a',
      current_speed_kmh: 58,
      normal_speed_kmh: 60,
      traffic_delay_seconds: 30,
      traffic_adjusted_duration_seconds: 750,
      predicted_duration_seconds: 780,
      prediction_label: 'Predicted traffic',
      confidence: 0.94,
    },
  },
  {
    route_id: 'rt-2',
    route_number: 2,
    color: '#0f9d58',
    summary: 'Market Corridor',
    distance_meters: 11200,
    duration_seconds: 780,
    is_fastest: false,
    traffic: {
      provider: 'none',
      traffic_status: 'unavailable',
      traffic_label: 'Live traffic unavailable',
      congestion_level: 'unknown',
      color: '#64748b',
      predicted_duration_seconds: 860,
      prediction_label: 'Predicted traffic',
    },
  },
];

describe('RouteComparisonPanel and TrafficNotificationBanner', () => {
  it('renders route comparison cards, fastest badge, unavailable traffic fallback, and handles selection', () => {
    const onSelectRoute = vi.fn();
    render(
      <RouteComparisonPanel
        routes={SAMPLE_ROUTES}
        selectedRouteIndex={0}
        onSelectRoute={onSelectRoute}
        trafficAvailable={true}
        trafficProvider="tomtom"
        availabilityNote="Found 2 genuinely distinct valid road route(s) out of 5 requested."
      />
    );

    expect(screen.getByText('FASTEST')).toBeInTheDocument();
    expect(screen.getByText('LOW TRAFFIC')).toBeInTheDocument();
    expect(screen.getByText('Live traffic unavailable')).toBeInTheDocument();
    expect(screen.getByText(/Found 2 genuinely distinct/)).toBeInTheDocument();

    const selectBtns = screen.getAllByRole('button', { name: /Select Route/i });
    fireEvent.click(selectBtns[0]);
    expect(onSelectRoute).toHaveBeenCalledWith(1);
  });

  it('handles user accepting or rejecting a faster alternative route notification', () => {
    const onSwitch = vi.fn();
    const onContinue = vi.fn();

    render(
      <TrafficNotificationBanner
        notification={{
          title: 'Heavy traffic detected ahead!',
          message: 'Alternative Route 3 is 8 minutes faster.',
          current_route_eta_seconds: 1500,
          alternative_route_eta_seconds: 1020,
          time_saved_seconds: 480,
          recommended_route: SAMPLE_ROUTES[0],
        }}
        onSwitchRoute={onSwitch}
        onContinueCurrent={onContinue}
      />
    );

    expect(screen.getByText('Heavy traffic detected ahead!')).toBeInTheDocument();
    expect(screen.getByText('8 min')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Switch Route/i }));
    expect(onSwitch).toHaveBeenCalledWith(SAMPLE_ROUTES[0]);

    fireEvent.click(screen.getByRole('button', { name: /Continue Current Route/i }));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it('slices traveled and remaining route polylines along GPS position', () => {
    const polyline = [
      [37.77, -122.42],
      [37.78, -122.41],
      [37.79, -122.40],
    ];
    const { traveledCoords, remainingCoords } = sliceRouteProgressPolylines(37.78, -122.41, polyline);
    expect(traveledCoords.length).toBeGreaterThanOrEqual(2);
    expect(remainingCoords.length).toBeGreaterThanOrEqual(2);
  });
});
