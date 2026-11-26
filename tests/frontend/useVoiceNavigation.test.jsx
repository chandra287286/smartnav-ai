import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useVoiceNavigation } from '../../frontend/src/hooks/useVoiceNavigation';

describe('useVoiceNavigation', () => {
  let speakMock;
  let cancelMock;

  beforeEach(() => {
    speakMock = vi.fn();
    cancelMock = vi.fn();
    window.speechSynthesis = {
      speak: speakMock,
      cancel: cancelMock,
    };
    window.SpeechSynthesisUtterance = vi.fn(function (text) {
      this.text = text;
    });
  });

  afterEach(() => {
    delete window.speechSynthesis;
    delete window.SpeechSynthesisUtterance;
  });

  it('speaks instructions without repeating the same key and respects mute toggle', () => {
    const { result } = renderHook(() => useVoiceNavigation());
    expect(result.current.isSupported).toBe(true);

    act(() => {
      expect(result.current.speak('Turn left in 200 meters', 'step-1-200')).toBe(true);
      expect(result.current.speak('Turn left in 200 meters', 'step-1-200')).toBe(false);
    });
    expect(speakMock).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.toggleMute();
    });
    expect(result.current.isMuted).toBe(true);
    expect(cancelMock).toHaveBeenCalled();

    act(() => {
      expect(result.current.speak('Turn right', 'step-2-now')).toBe(false);
    });
    expect(speakMock).toHaveBeenCalledTimes(1);
  });

  it('degrades gracefully when speechSynthesis is unavailable', () => {
    delete window.speechSynthesis;
    const { result } = renderHook(() => useVoiceNavigation());
    expect(result.current.isSupported).toBe(false);
    expect(result.current.speak('Turn left', 'step-1')).toBe(false);
  });
});
