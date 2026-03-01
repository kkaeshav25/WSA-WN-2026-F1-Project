import { useMemo } from 'react';
import { useSimulation } from '../context/SimulationContext.jsx';
import MOCK_STINT_DATA, { COMPOUND_COLORS } from '../data/mockStintData.js';

const ROW_HEIGHT = 36;
const BAR_HEIGHT = 14;
const PIT_CIRCLE_R = 10;
const HEADER_HEIGHT = 50;
const FOOTER_HEIGHT = 36;

const EVENT_STYLES = {
    SC: { color: '#FF6B00', bg: '#FF6B0015', label: '🏎 SC', border: '#FF6B0050' },
    VSC: { color: '#FFD700', bg: '#FFD70015', label: '⚡ VSC', border: '#FFD70050' },
    RED_FLAG: { color: '#FF0000', bg: '#FF000012', label: '🚩 RED', border: '#FF000040' },
};

/**
 * StintChart — Tyre strategy timeline for all drivers
 *
 * Driver rows reorder dynamically based on current race positions.
 * Each driver's bar grows independently based on that driver's current lap.
 */
export default function StintChart() {
    const { driverStates, positions, retiredDrivers } = useSimulation();
    const { totalLaps, drivers, raceEvents } = MOCK_STINT_DATA;

    // Build a lookup from driver number to their mock stint data
    const driverByNumber = useMemo(() => {
        const map = new Map();
        for (const d of drivers) map.set(d.number, d);
        return map;
    }, [drivers]);

    // Get per-driver current lap from simulation
    // For retired drivers, use their last lap so stints stay visible
    const driverCurrentLap = useMemo(() => {
        const map = new Map();
        if (driverStates && driverStates.size > 0) {
            for (const [num, state] of driverStates) {
                map.set(num, state.lap || 1);
            }
        }
        // Retired drivers: use their last lap
        if (retiredDrivers && retiredDrivers.size > 0) {
            for (const [num, info] of retiredDrivers) {
                if (!map.has(num)) {
                    map.set(num, info.lastLap || 1);
                }
            }
        }
        return map;
    }, [driverStates, retiredDrivers]);

    // Order drivers by current race position (from simulation positions)
    // Fall back to mock position order for drivers not in the simulation
    const orderedDrivers = useMemo(() => {
        const result = [];
        const added = new Set();

        // First: drivers in current position order from simulation
        if (positions && positions.length > 0) {
            for (const p of positions) {
                const d = driverByNumber.get(p.driver_number);
                if (d) {
                    result.push(d);
                    added.add(d.number);
                }
            }
        }

        // Then: any remaining drivers (e.g. retired) at the bottom in mock position order
        for (const d of [...drivers].sort((a, b) => a.position - b.position)) {
            if (!added.has(d.number)) {
                result.push(d);
                added.add(d.number);
            }
        }

        return result;
    }, [positions, driverByNumber, drivers]);

    // Max visible lap across all drivers (for race event visibility)
    const maxVisibleLap = useMemo(() => {
        let max = 1;
        for (const [, lap] of driverCurrentLap) {
            if (lap > max) max = lap;
        }
        return Math.min(max, totalLaps);
    }, [driverCurrentLap, totalLaps]);

    // Lap positions for drawing — always relative to totalLaps so the grid stays stable
    const lapWidth = (idx) => `${(idx / totalLaps) * 100}%`;
    const lapWidthSpan = (start, end) => `${((end - start + 1) / totalLaps) * 100}%`;

    return (
        <div className="h-full flex flex-col glass-panel overflow-hidden animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-4 pb-2">
                <div className="flex items-center gap-3">
                    <div className="w-1.5 h-7 rounded-full bg-f1-accent" />
                    <div>
                        <h2 className="text-sm font-bold text-f1-text uppercase tracking-wider">
                            Tyre Strategy
                        </h2>
                        <p className="text-[10px] text-f1-text-muted">
                            Stint timeline &amp; pit stops • {totalLaps} laps
                        </p>
                    </div>
                </div>

                {/* Legend */}
                <div className="flex items-center gap-3 text-[10px] font-semibold">
                    {Object.entries(COMPOUND_COLORS).map(([name, color]) => (
                        <div key={name} className="flex items-center gap-1.5">
                            <span className="w-3 h-3 rounded-full border"
                                style={{ backgroundColor: color, borderColor: `${color}80` }} />
                            <span className="text-f1-text-muted uppercase tracking-wide">{name}</span>
                        </div>
                    ))}
                    <span className="text-f1-border mx-1">|</span>
                    <div className="flex items-center gap-1">
                        <span className="stint-pit-legend" />
                        <span className="text-f1-text-muted">PIT STOP</span>
                    </div>
                </div>
            </div>

            {/* Chart area */}
            <div className="flex-1 overflow-y-auto px-5 pb-2">
                <div className="relative" style={{ minHeight: orderedDrivers.length * ROW_HEIGHT + HEADER_HEIGHT + FOOTER_HEIGHT }}>

                    {/* ── Lap grid lines ── */}
                    <div className="absolute inset-0" style={{ top: HEADER_HEIGHT, bottom: FOOTER_HEIGHT }}>
                        {Array.from({ length: totalLaps + 1 }, (_, i) => (
                            <div key={i}
                                className="absolute top-0 bottom-0 border-l"
                                style={{
                                    left: lapWidth(i),
                                    borderColor: i <= maxVisibleLap ? 'rgba(42,42,58,0.4)' : 'rgba(42,42,58,0.12)',
                                }}
                            />
                        ))}
                    </div>

                    {/* ── Race event zones (only show if within visible laps) ── */}
                    {raceEvents
                        .filter(evt => evt.startLap <= maxVisibleLap)
                        .map((evt, idx) => {
                            const style = EVENT_STYLES[evt.type] || EVENT_STYLES.SC;
                            const clampedEnd = Math.min(evt.endLap, maxVisibleLap);
                            return (
                                <div key={idx}
                                    className="absolute stint-event-zone"
                                    style={{
                                        left: lapWidth(evt.startLap - 1),
                                        width: lapWidthSpan(evt.startLap, clampedEnd),
                                        top: 0,
                                        bottom: FOOTER_HEIGHT,
                                        backgroundColor: style.bg,
                                        borderLeft: `2px solid ${style.border}`,
                                        borderRight: clampedEnd >= evt.endLap ? `2px solid ${style.border}` : 'none',
                                    }}
                                >
                                    <div className="absolute -top-0 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-b-md text-[9px] font-black tracking-wider whitespace-nowrap"
                                        style={{ backgroundColor: style.color, color: evt.type === 'RED_FLAG' ? '#fff' : '#000' }}>
                                        {style.label}
                                    </div>
                                </div>
                            );
                        })}

                    {/* ── Lap number header ── */}
                    <div className="relative flex" style={{ height: HEADER_HEIGHT }}>
                        {Array.from({ length: totalLaps }, (_, i) => (
                            <div key={i}
                                className="text-center text-[10px] font-mono transition-colors duration-300"
                                style={{
                                    position: 'absolute',
                                    left: lapWidth(i),
                                    width: lapWidthSpan(1, 1),
                                    bottom: 4,
                                    color: i < maxVisibleLap ? 'rgba(136,136,160,0.8)' : 'rgba(136,136,160,0.2)',
                                }}>
                                {i + 1}
                            </div>
                        ))}
                    </div>

                    {/* ── Driver rows ── */}
                    {orderedDrivers.map((driver, rowIdx) => {
                        const y = HEADER_HEIGHT + rowIdx * ROW_HEIGHT;
                        const lastStint = driver.stints[driver.stints.length - 1];
                        const isDNF = lastStint.endLap < totalLaps;

                        // Per-driver lap from simulation
                        const driverLap = driverCurrentLap.get(driver.number) || 0;
                        const visibleLapsForDriver = Math.min(Math.max(driverLap, 0), totalLaps);
                        const dnfVisible = isDNF && lastStint.endLap <= visibleLapsForDriver;

                        // Current position label
                        const posIdx = positions?.findIndex(p => p.driver_number === driver.number);
                        const displayPos = posIdx !== undefined && posIdx >= 0 ? posIdx + 1 : driver.position;

                        return (
                            <div key={driver.number}
                                className="stint-row absolute left-0 right-0 flex items-center transition-all duration-700 ease-in-out"
                                style={{ top: y, height: ROW_HEIGHT }}
                            >
                                {/* Position + Name */}
                                <div className="w-[60px] flex-shrink-0 flex items-center gap-1.5 pr-2 z-10">
                                    <span className="text-[10px] font-mono text-f1-text-muted/60 w-4 text-right tabular-nums">
                                        {displayPos}
                                    </span>
                                    <div className="w-[3px] h-5 rounded-full" style={{ backgroundColor: driver.teamColor }} />
                                    <span className="text-[11px] font-bold text-f1-text font-mono tracking-wide">
                                        {driver.abbr}
                                    </span>
                                </div>

                                {/* Bar area */}
                                <div className="flex-1 relative" style={{ height: BAR_HEIGHT }}>
                                    {driver.stints.map((stint, sIdx) => {
                                        // Only show stints that have started within this driver's visible range
                                        if (stint.startLap > visibleLapsForDriver) return null;

                                        const clampedEnd = Math.min(stint.endLap, visibleLapsForDriver);
                                        const stintLeft = ((stint.startLap - 1) / totalLaps) * 100;
                                        const stintWidth = ((clampedEnd - stint.startLap + 1) / totalLaps) * 100;
                                        const color = COMPOUND_COLORS[stint.compound] || '#888';
                                        const isFirst = sIdx === 0;
                                        const isLast = sIdx === driver.stints.length - 1;
                                        const isFullyRevealed = stint.endLap <= visibleLapsForDriver;

                                        return (
                                            <div key={sIdx}
                                                className="absolute top-0 stint-bar transition-all duration-500 ease-out"
                                                style={{
                                                    left: `${stintLeft}%`,
                                                    width: `${stintWidth}%`,
                                                    height: BAR_HEIGHT,
                                                    backgroundColor: `${color}30`,
                                                    borderTop: `2px solid ${color}`,
                                                    borderBottom: `2px solid ${color}`,
                                                    borderLeft: isFirst ? `2px solid ${color}` : 'none',
                                                    borderRight: (isLast && isFullyRevealed && !isDNF) ? `2px solid ${color}` : 'none',
                                                    borderRadius: `${isFirst ? '4px' : '0'} ${isLast && isFullyRevealed && !isDNF ? '4px' : '0'} ${isLast && isFullyRevealed && !isDNF ? '4px' : '0'} ${isFirst ? '4px' : '0'}`,
                                                }}
                                            >
                                                {/* Compound label inside the bar */}
                                                {(clampedEnd - stint.startLap + 1) >= 2 && (
                                                    <span className="absolute inset-0 flex items-center justify-center text-[8px] font-black uppercase tracking-widest"
                                                        style={{ color: `${color}90` }}>
                                                        {stint.compound}
                                                    </span>
                                                )}
                                            </div>
                                        );
                                    })}

                                    {/* Pit stop circles (only show if the pit lap has been reached by this driver) */}
                                    {driver.stints.slice(1).map((stint, pIdx) => {
                                        const pitLap = stint.startLap;
                                        if (pitLap > visibleLapsForDriver) return null;

                                        const cx = ((pitLap - 1) / totalLaps) * 100;
                                        return (
                                            <div key={pIdx}
                                                className="stint-pit-circle absolute z-20"
                                                style={{
                                                    left: `${cx}%`,
                                                    top: '50%',
                                                    transform: 'translate(-50%, -50%)',
                                                    width: PIT_CIRCLE_R * 2,
                                                    height: PIT_CIRCLE_R * 2,
                                                }}
                                            >
                                                <div className="w-full h-full rounded-full bg-f1-bg border-2 border-white flex items-center justify-center"
                                                    style={{ boxShadow: '0 0 8px rgba(255,255,255,0.3)' }}>
                                                    <span className="text-[8px] font-mono font-black text-white">
                                                        {pitLap}
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    })}

                                    {/* DNF marker (only show when that driver reaches the lap) */}
                                    {dnfVisible && (
                                        <div className="absolute z-20"
                                            style={{
                                                left: `${((lastStint.endLap) / totalLaps) * 100}%`,
                                                top: '50%',
                                                transform: 'translate(-50%, -50%)',
                                            }}>
                                            <div className="px-1.5 py-0.5 rounded text-[8px] font-black text-red-400 bg-red-500/15 border border-red-500/30">
                                                DNF
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}

                    {/* ── Lap number footer ── */}
                    <div className="relative flex" style={{ top: HEADER_HEIGHT + orderedDrivers.length * ROW_HEIGHT, height: FOOTER_HEIGHT }}>
                        {Array.from({ length: totalLaps }, (_, i) => (
                            <div key={i}
                                className="text-center text-[10px] font-mono transition-colors duration-300"
                                style={{
                                    position: 'absolute',
                                    left: lapWidth(i),
                                    width: lapWidthSpan(1, 1),
                                    top: 8,
                                    color: i < maxVisibleLap ? 'rgba(136,136,160,0.8)' : 'rgba(136,136,160,0.2)',
                                }}>
                                L{i + 1}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
