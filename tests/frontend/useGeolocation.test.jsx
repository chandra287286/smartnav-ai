import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GPS_STATUS, useGeolocation } from '../../frontend/src/hooks/useGeolocation';

describe('useGeolocation', () => {
  let getCurrentPositionMock;
  let watchPositionMock;
  let clearWatchMock;

  beforeEach(() => {
    getCurrentPositionMock = vi.fn();
    watchPositionMock = vi.fn().mockReturnValue(42);
    clearWatchMock = vi.fn();

    Object.defineProperty(window, 'isSecureContext', {
      configurable: true,
      value: true,
    });

    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition: getCurrentPositionMock,
        watchPosition: watchPositionMock,
        clearWatch: clearWatchMock,
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('handles GPS permission denial and stops active tracking', async () => {
    getCurrentPositionMock.mockImplementation((_success, error) => {
      error({ code: 1, message: 'User denied Geolocation' });
    });

    const { result } = renderHook(() => useGeolocation());

    await act(async () => {
      await expect(result.current.locateOnce()).rejects.toBeTruthy();
    });

    expect(result.current.status).toBe(GPS_STATUS.DENIED);
    expect(result.current.error).toMatch(/permission was denied/i);
    expect(result.current.isTracking).toBe(false);
  });

  it('handles GPS unavailable and timeout errors', async () => {
    getCurrentPositionMock.mockImplementationOnce((_s, error) => {
      error({ code: 2, message: 'Position unavailable' });
    });

    const { result } = renderHook(() => useGeolocation());
    await act(async () => {
      await expect(result.current.locateOnce()).rejects.toBeTruthy();
    });
    expect(result.current.status).toBe(GPS_STATUS.UNAVAILABLE);

    getCurrentPositionMock.mockImplementationOnce((_s, error) => {
      error({ code: 3, message: 'Timeout' });
    });
    await act(async () => {
      await expect(result.current.locateOnce()).rejects.toBeTruthy();
    });
    expect(result.current.status).toBe(GPS_STATUS.TIMEOUT);
  });

  it('updates live position via watchPosition, prevents duplicate watchers, and cleans up on unmount', () => {
    let successCallback;
    watchPositionMock.mockImplementation((success) => {
      successCallback = success;
      return 99;
    });

    const { result, unmount } = renderHook(() => useGeolocation());

    act(() => {
      const started1 = result.current.startTracking();
      const started2 = result.current.startTracking();
      expect(started1).toBe(true);
      expect(started2).toBe(true);
    });

    expect(watchPositionMock).toHaveBeenCalledTimes(1);
    expect(result.current.isTracking).toBe(true);

    act(() => {
      successCallback({
        coords: {
          latitude: 12.9716,
          longitude: 77.5946,
          accuracy: 9.4,
          speed: 8.5,
          heading: 180,
          altitude: 900,
        },
        timestamp: 1700000000000,
      });
    });

    expect(result.current.status).toBe(GPS_STATUS.ACTIVE);
    expect(result.current.position).toMatchObject({
      lat: 12.9716,
      lng: 77.5946,
      accuracy: 9.4,
      speed: 8.5,
      heading: 180,
    });

    unmount();
    expect(clearWatchMock).toHaveBeenCalledWith(99);
  });

  it('detects insecure HTTP context for mobile GPS access', () => {
    Object.defineProperty(window, 'isSecureContext', {
      configurable: true,
      value: false,
    });

    const { result } = renderHook(() => useGeolocation());
    expect(result.current.status).toBe(GPS_STATUS.INSECURE_CONTEXT);

    act(() => {
      expect(result.current.startTracking()).toBe(false);
    });
    expect(result.current.error).toMatch(/HTTPS/i);
  });
});
