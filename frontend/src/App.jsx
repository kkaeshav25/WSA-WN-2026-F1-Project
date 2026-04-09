import { useRef, useCallback, useState } from 'react';
import { SimulationProvider, useSimulation } from './context/SimulationContext.jsx';
import TrackMap from './components/TrackMap.jsx';
import Leaderboard from './components/Leaderboard.jsx';
import TelemetryDash from './components/TelemetryDash.jsx';

// ── Track Status Banner ──
const STATUS_STYLES = {
  GREEN: null,
  YELLOW: { bg: '#FFD700', text: '#000', label: '⚠ YELLOW FLAG', glow: '#FFD70060' },
  DOUBLE_YELLOW: { bg: '#ffd500ff', text: '#000', label: '⚠⚠ DOUBLE YELLOW', glow: '#FF8C0060' },
  SAFETY_CAR: { bg: '#FF6B00', text: '#000', label: '🏎 SAFETY CAR', glow: '#FF6B0060' },
  SC_ENDING: { bg: '#32CD32', text: '#000', label: '🏎 SC IN THIS LAP', glow: '#32CD3260' },
  VSC: { bg: '#FFD700', text: '#000', label: '⚡ VIRTUAL SAFETY CAR', glow: '#FFD70060' },
  VSC_ENDING: { bg: '#32CD32', text: '#000', label: '⚡ VSC ENDING', glow: '#32CD3260' },
  RED_FLAG: { bg: '#FF0000', text: '#fff', label: '🚩 RED FLAG', glow: '#FF000060' },
  CHEQUERED: { bg: '#ffffff', text: '#000', label: '🏁 CHEQUERED FLAG', glow: '#ffffff40' },
};

function FastestLapDisplay() {
  const { fastestLap } = useSimulation();
  if (!fastestLap) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-purple-500/30"
      style={{ background: '#A855F715' }}>
      <span className="text-[9px] text-purple-400 font-semibold uppercase tracking-wider">⏱ FL</span>
      <span className="text-[11px] font-mono font-bold text-purple-300 tabular-nums">
        {fastestLap.timeStr}
      </span>
      <span className="text-[9px] font-bold text-purple-400">{fastestLap.driverName}</span>
    </div>
  );
}

function WeatherDisplay() {
  const { currentWeather } = useSimulation();
  if (!currentWeather) return null;

  const w = currentWeather;
  const tempF = Math.round(w.air_temp * 9 / 5 + 32);

  // Determine track conditions: WET (actively raining), DAMP (high humidity/recently rained), DRY
  let condition, condIcon, condColor;
  if (w.rainfall) {
    condition = 'WET';
    condIcon = '🌧';
    condColor = 'text-blue-400';
  } else if (w.humidity >= 75) {
    condition = 'DAMP';
    condIcon = '🌥';
    condColor = 'text-cyan-400';
  } else {
    condition = 'DRY';
    condIcon = '☀';
    condColor = 'text-f1-text-muted';
  }

  return (
    <div className="flex items-center gap-4 text-[10px] font-mono text-f1-text-muted">
      <span className={`${condColor} font-bold flex items-center gap-1`}>
        {condIcon} {condition}
      </span>

      <span className="text-f1-border">|</span>

      <span className="flex items-center gap-1">
        <span className="text-orange-400">🌡</span>
        <span className="text-f1-text">{w.air_temp}°C</span>
        <span className="text-f1-text-muted/60">/ {tempF}°F</span>
      </span>

      <span className="text-f1-border">|</span>

      <span className="flex items-center gap-1">
        <span>🛣</span>
        <span className="text-f1-text">{w.track_temp}°C</span>
      </span>

      <span className="text-f1-border">|</span>

      <span className="flex items-center gap-1">
        <span className="text-blue-300">💧</span>
        <span>{w.humidity}%</span>
      </span>

      <span className="text-f1-border">|</span>

      <span className="flex items-center gap-1">
        <span>💨</span>
        <span>{w.wind_speed} m/s</span>
      </span>
    </div>
  );
}

function TrackStatusBanner() {
  const { trackStatus, trackMessage } = useSimulation();
  const style = STATUS_STYLES[trackStatus];

  if (!style) return null;

  return (
    <div
      className="px-4 py-2 flex items-center justify-center gap-3 rounded-xl animate-fade-in"
      style={{
        background: style.bg,
        color: style.text,
        boxShadow: `0 0 20px ${style.glow}, inset 0 0 20px ${style.glow}`,
      }}
    >
      <span className="text-sm font-black uppercase tracking-wider">
        {trackMessage || style.label}
      </span>
    </div>
  );
}

function PlaybackControls() {
  const {
    isPlaying, togglePlayback, restart, seekTo,
    speed, setPlaybackSpeed,
    progress, currentTime, currentLap,
    retiredDrivers, totalTicks,
  } = useSimulation();

  const scrubberRef = useRef(null);
  const isDragging = useRef(false);

  const mins = Math.floor(currentTime / 60);
  const secs = Math.floor(currentTime % 60);
  const displayTime = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

  // ── Scrubber handlers ──
  const handleScrub = useCallback((e) => {
    if (!scrubberRef.current || totalTicks <= 0) return;
    const rect = scrubberRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const pct = x / rect.width;
    const targetIndex = Math.round(pct * (totalTicks - 1));
    seekTo(targetIndex);
  }, [seekTo, totalTicks]);

  const onMouseDown = useCallback((e) => {
    isDragging.current = true;
    handleScrub(e);
    const onMove = (ev) => { if (isDragging.current) handleScrub(ev); };
    const onUp = () => { isDragging.current = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [handleScrub]);

  return (
    <div className="glass-panel px-4 py-2 flex items-center gap-4">
      <button onClick={togglePlayback}
        className="w-9 h-9 rounded-lg bg-f1-accent hover:bg-f1-accent-glow transition-colors
                    flex items-center justify-center text-white flex-shrink-0">
        {isPlaying ? (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <rect x="2" y="1" width="4" height="12" rx="1" />
            <rect x="8" y="1" width="4" height="12" rx="1" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
            <polygon points="3,1 13,7 3,13" />
          </svg>
        )}
      </button>

      <button onClick={restart} title="Restart"
        className="w-7 h-7 rounded-md bg-f1-surface-alt hover:bg-f1-border transition-colors
                    flex items-center justify-center text-f1-text-muted flex-shrink-0">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M1 1v4h4" /><path d="M1 5A5 5 0 1 1 2.5 9.5" />
        </svg>
      </button>

      {/* Scrubber */}
      <div className="flex-1 flex items-center gap-3 min-w-0">
        <div
          ref={scrubberRef}
          className="flex-1 h-4 relative cursor-pointer group"
          onMouseDown={onMouseDown}
        >
          {/* Track */}
          <div className="absolute top-1/2 -translate-y-1/2 w-full h-1.5 bg-f1-surface-alt rounded-full overflow-hidden">
            <div className="h-full bg-f1-accent rounded-full"
              style={{ width: `${progress}%` }} />
          </div>
          {/* Knob */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-f1-accent
                            border-2 border-white shadow-lg transition-transform
                            group-hover:scale-125"
            style={{ left: `calc(${progress}% - 7px)` }}
          />
        </div>
      </div>

      <span className="text-[10px] font-mono text-f1-yellow font-semibold flex-shrink-0">
        LAP {currentLap}
      </span>

      <div className="font-mono text-xs text-f1-text tabular-nums flex-shrink-0">
        {displayTime}
      </div>

      {retiredDrivers.size > 0 && (
        <span className="text-[10px] font-mono text-red-400 flex-shrink-0">
          {retiredDrivers.size} OUT
        </span>
      )}

      <div className="flex items-center gap-1 flex-shrink-0">
        {[1, 2, 5, 10].map(s => (
          <button key={s} onClick={() => setPlaybackSpeed(s)}
            className={`px-2 py-1 rounded text-[10px] font-bold transition-colors
                            ${speed === s ? 'bg-f1-accent text-white'
                : 'bg-f1-surface-alt text-f1-text-muted hover:text-f1-text'}`}>
            {s}x
          </button>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <SimulationProvider>
      <div className="h-screen w-screen bg-f1-bg flex flex-col xl:flex-row xl:overflow-hidden overflow-y-auto">
        {/* Sidebar — full height on xl+, horizontal strip on smaller */}
        <aside className="xl:w-[340px] xl:flex-shrink-0 glass-panel m-2 xl:mr-0 flex flex-col animate-slide-in overflow-hidden
                          max-xl:max-h-[240px] max-xl:min-h-[180px] flex-shrink-0">
          <Leaderboard />
        </aside>

        <main className="xl:flex-1 flex flex-col gap-2 p-2 min-w-0 xl:min-h-0">
          {/* Header */}
          <header className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 glass-panel flex-shrink-0">
            <div className="flex items-center gap-3">
              <FastestLapDisplay />
            </div>

            <div className="flex items-center gap-4 text-[10px] font-mono text-f1-text-muted max-lg:hidden">
              <span>CHINA 2026</span>
              <span>•</span>
              <span>SHANGHAI INTERNATIONAL CIRCUIT</span>
              <span>•</span>
              <span className="text-f1-yellow font-semibold">RACE PREDICTION</span>
            </div>

            <WeatherDisplay />
          </header>

          <TrackStatusBanner />

          {/* Live Timing View */}
          <div className="xl:flex-1 flex flex-col lg:flex-row gap-2 xl:min-h-0">
            <div className="flex-1 glass-panel overflow-hidden min-w-0 max-lg:min-h-[400px] min-h-[300px]">
              <TrackMap />
            </div>
            <div className="lg:w-[360px] lg:flex-shrink-0 min-h-[280px]">
              <TelemetryDash />
            </div>
          </div>

          <PlaybackControls />
        </main>
      </div>
    </SimulationProvider>
  );
}
