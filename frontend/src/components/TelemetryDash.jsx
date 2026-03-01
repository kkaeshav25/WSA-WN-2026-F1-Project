import { useState, useEffect, useRef } from 'react';
import { useSimulation } from '../context/SimulationContext.jsx';

const SECTOR_COLORS = {
    purple: '#A855F7',
    green: '#22C55E',
    yellow: '#EAB308',
};

const COMPOUND_STYLES = {
    SOFT: { color: '#FF0000', label: 'SOFT' },
    MEDIUM: { color: '#FFCC00', label: 'MEDIUM' },
    HARD: { color: '#FFFFFF', label: 'HARD' },
    INTERMEDIATE: { color: '#2ECC40', label: 'INTER' },
    WET: { color: '#0074D9', label: 'WET' },
    UNKNOWN: { color: '#888888', label: '---' },
};

function formatSectorTime(secs) {
    if (secs == null) return '-.---';
    return secs.toFixed(3);
}

function formatLapTime(secs) {
    if (secs == null) return '-:--.---';
    const mins = Math.floor(secs / 60);
    const rest = secs % 60;
    return `${mins}:${rest < 10 ? '0' : ''}${rest.toFixed(3)}`;
}

/**
 * TelemetryDash — Real F1 telemetry from FastF1 data
 */
export default function TelemetryDash() {
    const { driverStates, selectedDriverNumber, drivers, driverLapInfo } = useSimulation();
    const [display, setDisplay] = useState({ speed: 0, throttle: 0, brake: 0, gear: 0, drs: false, rpm: 0 });
    const smoothRef = useRef({ speed: 0, throttle: 0, brake: 0, rpm: 0 });
    const animRef = useRef(null);

    const driver = drivers.get(selectedDriverNumber);
    const teamColor = driver?.team_colour || '#3671C6';
    const lapInfo = driverLapInfo?.get(selectedDriverNumber);

    useEffect(() => {
        const update = () => {
            const state = driverStates.get(selectedDriverNumber);
            if (state) {
                const sm = smoothRef.current;
                const lerpRate = 0.18;
                const speedMph = state.speed * 0.621371;
                sm.speed += (speedMph - sm.speed) * lerpRate;
                sm.throttle += (state.throttle - sm.throttle) * 0.22;
                sm.brake += ((state.brake ? 100 : 0) - sm.brake) * 0.22;
                sm.rpm += (state.rpm - sm.rpm) * lerpRate;

                setDisplay({
                    speed: Math.round(sm.speed),
                    throttle: Math.round(sm.throttle),
                    brake: Math.round(sm.brake),
                    gear: state.gear,
                    drs: state.drs,
                    rpm: Math.round(sm.rpm),
                    lap: state.lap,
                });
            }
            animRef.current = requestAnimationFrame(update);
        };
        animRef.current = requestAnimationFrame(update);
        return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
    }, [driverStates, selectedDriverNumber]);

    // Speedometer arc
    const maxSpeed = 220;
    const speedPct = Math.min(display.speed / maxSpeed, 1);
    const arcAngle = 240;
    const R = 70, CX = 90, CY = 85;

    function polar(cx, cy, r, deg) {
        const rad = deg * Math.PI / 180;
        return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
    }
    function arc(cx, cy, r, s, e) {
        const start = polar(cx, cy, r, e);
        const end = polar(cx, cy, r, s);
        return `M ${start.x} ${start.y} A ${r} ${r} 0 ${e - s > 180 ? 1 : 0} 0 ${end.x} ${end.y}`;
    }

    const bgStart = 270 - arcAngle / 2;
    const bgEnd = 270 + arcAngle / 2;
    const activeEnd = bgStart + arcAngle * speedPct;

    const compound = lapInfo?.compound || 'UNKNOWN';
    const compStyle = COMPOUND_STYLES[compound] || COMPOUND_STYLES.UNKNOWN;
    const sectorColors = lapInfo?.sectorColors || [null, null, null];
    const lastSectors = lapInfo?.lastSectors || [null, null, null];

    return (
        <div className="glass-panel p-4 h-full flex flex-col animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                    <div className="w-1.5 h-8 rounded-full" style={{ backgroundColor: teamColor }} />
                    <div>
                        <h3 className="text-sm font-bold text-f1-text">{driver?.name_acronym || '---'}</h3>
                        <p className="text-[10px] text-f1-text-muted">{driver?.full_name || 'Select a driver'}</p>
                        {driver?.team_name && (
                            <p className="text-[9px] font-semibold uppercase tracking-wider"
                                style={{ color: teamColor }}>
                                {driver.team_name}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-f1-text-muted">#{selectedDriverNumber}</span>
                    {display.lap > 0 && (
                        <span className="text-[10px] font-mono text-f1-text-muted">LAP {display.lap}</span>
                    )}
                    <div className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider
                        transition-all duration-300
                        ${display.drs
                            ? 'bg-green-500/20 text-green-400 border border-green-400/50'
                            : 'bg-f1-surface-alt text-f1-text-muted border border-f1-border'}`}>
                        DRS
                    </div>
                </div>
            </div>

            {/* Lap Times & Sectors */}
            <div className="flex items-center gap-3 mb-2 py-2 px-3 bg-f1-surface-alt/40 rounded-lg border border-f1-border/30">
                {/* Compound */}
                <div className="flex items-center gap-1.5">
                    <span className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black border"
                        style={{ color: compStyle.color, borderColor: compStyle.color, background: `${compStyle.color}15` }}>
                        {compound[0]}
                    </span>
                    <div className="flex flex-col">
                        <span className="text-[8px] text-f1-text-muted uppercase">Tyre</span>
                        <span className="text-[9px] font-bold" style={{ color: compStyle.color }}>
                            {compStyle.label} L{lapInfo?.tyreLife || 0}
                        </span>
                    </div>
                </div>

                <span className="text-f1-border">|</span>

                {/* Best Lap */}
                <div className="flex flex-col">
                    <span className="text-[8px] text-f1-text-muted uppercase">Best</span>
                    <span className="text-[10px] font-mono font-bold text-f1-text tabular-nums">
                        {lapInfo?.bestLapStr || '-:--.---'}
                    </span>
                </div>

                <span className="text-f1-border">|</span>

                {/* Last Lap */}
                <div className="flex flex-col">
                    <span className="text-[8px] text-f1-text-muted uppercase">Last</span>
                    <span className="text-[10px] font-mono font-bold text-f1-text tabular-nums">
                        {lapInfo?.lastLapStr || '-:--.---'}
                    </span>
                </div>

                <span className="text-f1-border">|</span>

                {/* Current lap elapsed */}
                <div className="flex flex-col">
                    <span className="text-[8px] text-f1-text-muted uppercase">Current</span>
                    <span className="text-[10px] font-mono font-bold text-f1-yellow tabular-nums">
                        {lapInfo?.currentLapElapsed != null
                            ? formatLapTime(lapInfo.currentLapElapsed)
                            : '-:--.---'}
                    </span>
                </div>
            </div>

            {/* Sector times */}
            <div className="flex items-center gap-1 mb-3">
                {[0, 1, 2].map(s => (
                    <div key={s} className="flex-1 py-1.5 px-2 rounded-md text-center"
                        style={{
                            backgroundColor: sectorColors[s]
                                ? `${SECTOR_COLORS[sectorColors[s]]}20`
                                : '#ffffff08',
                            border: sectorColors[s]
                                ? `1px solid ${SECTOR_COLORS[sectorColors[s]]}50`
                                : '1px solid #ffffff10',
                        }}>
                        <div className="text-[8px] font-semibold text-f1-text-muted uppercase">S{s + 1}</div>
                        <div className="text-[11px] font-mono font-bold tabular-nums"
                            style={{ color: sectorColors[s] ? SECTOR_COLORS[sectorColors[s]] : '#ffffff50' }}>
                            {formatSectorTime(lastSectors[s])}
                        </div>
                    </div>
                ))}
            </div>

            {/* Main telemetry */}
            <div className="flex items-center gap-4 flex-1">
                {/* Speedometer */}
                <div className="relative flex-shrink-0">
                    <svg width="180" height="140" viewBox="0 0 180 140">
                        <path d={arc(CX, CY, R, bgStart, bgEnd)}
                            fill="none" stroke="#2a2a3a" strokeWidth="8" strokeLinecap="round" />
                        <path d={arc(CX, CY, R, bgStart, activeEnd)}
                            fill="none" stroke={teamColor} strokeWidth="8" strokeLinecap="round"
                            style={{ filter: `drop-shadow(0 0 6px ${teamColor}80)` }} />
                        {[0, 50, 100, 150, 200].map(spd => {
                            const pct = spd / maxSpeed;
                            const deg = bgStart + arcAngle * pct;
                            const inner = polar(CX, CY, R - 14, deg);
                            const outer = polar(CX, CY, R - 8, deg);
                            const label = polar(CX, CY, R - 22, deg);
                            return (
                                <g key={spd}>
                                    <line x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
                                        stroke="#555" strokeWidth="1.5" />
                                    <text x={label.x} y={label.y} fill="#666" fontSize="7"
                                        fontFamily="'JetBrains Mono', monospace"
                                        textAnchor="middle" dominantBaseline="middle">{spd}</text>
                                </g>
                            );
                        })}
                        <text x={CX} y={CY + 2} fill="#e8e8f0" fontSize="32" fontWeight="800"
                            fontFamily="'JetBrains Mono', monospace" textAnchor="middle" dominantBaseline="middle">
                            {display.speed}
                        </text>
                        <text x={CX} y={CY + 22} fill="#8888a0" fontSize="9" fontWeight="600"
                            fontFamily="'Outfit', sans-serif" textAnchor="middle">MPH</text>
                    </svg>
                </div>

                {/* Gear + RPM + Bars */}
                <div className="flex flex-col gap-3 flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                        <div className="glass-panel-subtle flex items-center justify-center w-16 h-16 rounded-xl">
                            <span className="font-mono text-4xl font-black" style={{ color: teamColor }}>
                                {display.gear === 0 ? 'N' : display.gear}
                            </span>
                        </div>
                        <div className="flex flex-col gap-1 text-[10px] font-mono text-f1-text-muted">
                            <span>GEAR</span>
                            <span className="text-f1-text text-xs">{display.rpm.toLocaleString()} RPM</span>
                        </div>
                    </div>

                    {/* Throttle */}
                    <div className="flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] font-semibold text-f1-text-muted uppercase tracking-wider">Throttle</span>
                            <span className="text-xs font-mono font-bold text-green-400 tabular-nums">{display.throttle}%</span>
                        </div>
                        <div className="h-3 bg-f1-surface-alt rounded-full overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-100 ease-out"
                                style={{
                                    width: `${display.throttle}%`,
                                    background: 'linear-gradient(90deg, #00d27a, #00ff99)',
                                    boxShadow: display.throttle > 80 ? '0 0 12px rgba(0,210,122,0.5)' : 'none',
                                }} />
                        </div>
                    </div>

                    {/* Brake */}
                    <div className="flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                            <span className="text-[10px] font-semibold text-f1-text-muted uppercase tracking-wider">Brake</span>
                            <span className="text-xs font-mono font-bold text-red-400 tabular-nums">{display.brake}%</span>
                        </div>
                        <div className="h-3 bg-f1-surface-alt rounded-full overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-100 ease-out"
                                style={{
                                    width: `${display.brake}%`,
                                    background: 'linear-gradient(90deg, #e10600, #ff4444)',
                                    boxShadow: display.brake > 50 ? '0 0 12px rgba(225,6,0,0.5)' : 'none',
                                }} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
