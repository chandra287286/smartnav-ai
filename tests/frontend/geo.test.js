import { describe, expect, it } from 'vitest';
import {
  computeRouteProgress,
  formatDistance,
  formatDuration,
  haversineDistanceMeters,
  isValidCoordinate,
} from '../../frontend/src/utils/geo';

describe('geospatial utilities', () => {
  it('validates coordinates accurately', () => {
    expect(isValidCoordinate(37.7749, -122.4194)).toBe(true);
    expect(isValidCoordinate(91, 0)).toBe(false);
    expect(isValidCoordinate(0, -181)).toBe(false);
    expect(isValidCoordinate(NaN, 10)).toBe(false);
  });

  it('computes route progress and detects off-route deviation', () => {
    const polyline = [
      [37.7749, -122.4194],
      [37.7790, -122.4140],
      [37.7849, -122.4094],
    ];

    const onRoute = computeRouteProgress(37.77695, -122.4167, polyline);
    expect(onRoute.distanceToRouteMeters).toBeLessThan(25);
    expect(onRoute.remainingDistanceMeters).toBeGreaterThan(500);
    expect(onRoute.progressFraction).toBeGreaterThan(0.1);
    expect(onRoute.progressFraction).toBeLessThan(0.9);

    const offRoute = computeRouteProgress(37.7749, -122.4000, polyline);
    expect(offRoute.distanceToRouteMeters).toBeGreaterThan(500);
  });

  it('formats distance and duration cleanly', () => {
    expect(formatDistance(240)).toBe('240 m');
    expect(formatDistance(1450)).toBe('1.5 km');
    expect(formatDuration(420)).toBe('7 min');
    expect(formatDuration(3900)).toBe('1 hr 5 min');
    expect(haversineDistanceMeters(37.7749, -122.4194, 37.7749, -122.4194)).toBe(0);
  });
});
