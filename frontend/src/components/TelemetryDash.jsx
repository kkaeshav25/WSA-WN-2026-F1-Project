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
 * TelemetryDash — Driver info panel with lap timing data
 *
 * Displays: driver header, DRS, gear, compound, lap times, sector times.
 * Speed, RPM, throttle, and brake have been removed.
 */
export default function TelemetryDash() {
    const { driverStates, selectedDriverNumber, drivers, driverLapInfo } = useSimulation();
    const [display, setDisplay] = useState({ gear: 0, drs: false, lap: 0 });
    const animRef = useRef(null);

    const driver = drivers.get(selectedDriverNumber);
    const teamColor = driver?.team_colour || '#3671C6';
    const lapInfo = driverLapInfo?.get(selectedDriverNumber);

    useEffect(() => {
        const update = () => {
            const state = driverStates.get(selectedDriverNumber);
            if (state) {
                setDisplay({
                    gear: state.gear,
                    drs: state.drs,
                    lap: state.lap,
                });
            }
            animRef.current = requestAnimationFrame(update);
        };
        animRef.current = requestAnimationFrame(update);
        return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
    }, [driverStates, selectedDriverNumber]);

    const compound = lapInfo?.compound || 'UNKNOWN';
    const compStyle = COMPOUND_STYLES[compound] || COMPOUND_STYLES.UNKNOWN;
    const sectorColors = lapInfo?.sectorColors || [null, null, null];
    const lastSectors = lapInfo?.lastSectors || [null, null, null];

    return (
        <div className="glass-panel p-4 h-full flex flex-col animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
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
            <div className="flex items-center gap-3 mb-3 py-2 px-3 bg-f1-surface-alt/40 rounded-lg border border-f1-border/30">
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
            <div className="flex items-center gap-1 mb-4">
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


        </div>
    );
}
