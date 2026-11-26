import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Web Speech API (SpeechSynthesis) hook for turn-by-turn voice guidance.
 * Announces authentic maneuver instructions only, avoids duplicate triggers, and degrades gracefully.
 */
export function useVoiceNavigation() {
  const isSupported =
    typeof window !== 'undefined' &&
    'speechSynthesis' in window &&
    typeof window.SpeechSynthesisUtterance !== 'undefined';

  const [isMuted, setIsMuted] = useState(false);
  const [lastSpoken, setLastSpoken] = useState('');
  const spokenKeysRef = useRef(new Set());

  const cancelSpeech = useCallback(() => {
    if (isSupported) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Ignore browser speech synthesis cancellation errors
      }
    }
  }, [isSupported]);

  useEffect(() => {
    return () => {
      cancelSpeech();
    };
  }, [cancelSpeech]);

  const speak = useCallback(
    (text, announcementKey = null) => {
      if (!isSupported || isMuted || !text || typeof text !== 'string') {
        return false;
      }
      if (announcementKey && spokenKeysRef.current.has(announcementKey)) {
        return false;
      }
      if (announcementKey) {
        spokenKeysRef.current.add(announcementKey);
      }

      try {
        window.speechSynthesis.cancel();
        const utterance = new window.SpeechSynthesisUtterance(text);
        utterance.lang = 'en-US';
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
        setLastSpoken(text);
        return true;
      } catch {
        return false;
      }
    },
    [isSupported, isMuted]
  );

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (next) {
        cancelSpeech();
      }
      return next;
    });
  }, [cancelSpeech]);

  const resetHistory = useCallback(() => {
    spokenKeysRef.current.clear();
    setLastSpoken('');
  }, []);

  return {
    isSupported,
    isMuted,
    lastSpoken,
    speak,
    toggleMute,
    cancelSpeech,
    resetHistory,
  };
}
