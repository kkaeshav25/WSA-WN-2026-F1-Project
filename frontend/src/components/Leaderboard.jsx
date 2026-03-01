import { useSimulation } from '../context/SimulationContext.jsx';

/**
 * Tyre compound display colors and abbreviations
 */
const COMPOUND_STYLES = {
    SOFT: { color: '#FF0000', abbr: 'S', bg: '#FF000020' },
    MEDIUM: { color: '#FFCC00', abbr: 'M', bg: '#FFCC0020' },
    HARD: { color: '#FFFFFF', abbr: 'H', bg: '#FFFFFF15' },
    INTERMEDIATE: { color: '#2ECC40', abbr: 'I', bg: '#2ECC4020' },
    WET: { color: '#0074D9', abbr: 'W', bg: '#0074D920' },
    UNKNOWN: { color: '#888888', abbr: '?', bg: '#88888815' },
};

function formatGap(val) {
    if (val == null) return '---';
    if (val === 0) return 'LEADER';
    if (val < 0) return `${Math.abs(val)} LAP${Math.abs(val) > 1 ? 'S' : ''}`;
    return `+${val.toFixed(3)}`;
}

function formatInterval(val) {
    if (val == null) return '---';
    if (val < 0) return `+${Math.abs(val)} L`;
    return `+${val.toFixed(3)}`;
}

/**
 * Leaderboard — Live timing sidebar
 */
export default function Leaderboard() {
    const {
        positions, drivers, driverStates, isLoading,
        selectedDriverNumber, setSelectedDriverNumber,
        retiredDrivers, driverLapInfo, driverGaps,
    } = useSimulation();

    if (isLoading) {
        return (
            <div className="flex flex-col h-full items-center justify-center">
                <div className="text-sm text-f1-text-muted animate-pulse">Loading race data...</div>
            </div>
        );
    }

    const displayPositions = positions.length > 0
        ? positions.filter(p => !retiredDrivers.has(p.driver_number))
        : [...driverStates.keys()]
            .filter(n => !retiredDrivers.has(n))
            .map((num, i) => ({ driver_number: num, position: i + 1 }));

    const retiredList = [...retiredDrivers.entries()].map(([num, info]) => ({
        driver_number: num,
        status: info.status || 'DNF',
        lastLap: info.lastLap || 0,
    }));

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-4 py-3 border-b border-f1-border">
                <h2 className="text-sm font-bold uppercase tracking-wider text-f1-text">Live Timing</h2>
                <span className="text-[10px] font-mono text-f1-text-muted uppercase">
                    {displayPositions.length + retiredList.length} drivers
                </span>
            </div>

            <div className="grid grid-cols-[32px_1fr_26px_70px_65px] gap-1 px-4 py-2 text-[9px] font-semibold text-f1-text-muted uppercase tracking-wider border-b border-f1-border/50">
                <span>Pos</span>
                <span>Driver</span>
                <span className="text-center">Tyr</span>
                <span className="text-right">Gap</span>
                <span className="text-right">Int</span>
            </div>

            <div className="flex-1 overflow-y-auto">
                {/* Active drivers */}
                {displayPositions.map((pos) => {
                    const driver = drivers.get(pos.driver_number);
                    if (!driver) return null;
                    const lapInfo = driverLapInfo?.get(pos.driver_number);
                    const compound = lapInfo?.compound || 'UNKNOWN';
                    const compStyle = COMPOUND_STYLES[compound] || COMPOUND_STYLES.UNKNOWN;
                    const gaps = driverGaps?.get(pos.driver_number);

                    return (
                        <div
                            key={pos.driver_number}
                            onClick={() => setSelectedDriverNumber(pos.driver_number)}
                            className={`grid grid-cols-[32px_1fr_26px_70px_65px] gap-1 items-center px-4 py-2
                                transition-all duration-300 ease-out border-b border-f1-border/30 cursor-pointer
                                ${pos.driver_number === selectedDriverNumber
                                    ? 'bg-f1-accent/10 border-l-2 border-l-f1-accent'
                                    : 'hover:bg-f1-surface-alt/60'}`}
                        >
                            <span className="font-mono font-bold text-sm text-f1-text tabular-nums">
                                {pos.position}
                            </span>

                            <div className="flex items-center gap-2 min-w-0">
                                <div className="w-1 h-6 rounded-full flex-shrink-0"
                                    style={{ backgroundColor: driver.team_colour }} />
                                <div className="flex flex-col min-w-0">
                                    <span className="text-xs font-bold text-f1-text">{driver.name_acronym}</span>
                                    <span className="text-[8px] text-f1-text-muted/60 truncate">{driver.team_name}</span>
                                </div>
                            </div>

                            {/* Tyre compound */}
                            <div className="flex items-center justify-center">
                                <span className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black border"
                                    style={{
                                        color: compStyle.color,
                                        borderColor: compStyle.color,
                                        background: compStyle.bg,
                                    }}>
                                    {compStyle.abbr}
                                </span>
                            </div>

                            {/* Gap to leader */}
                            <span className={`text-right text-[10px] font-mono tabular-nums
                                ${gaps?.gapToLeader === 0 ? 'text-f1-text font-bold' : 'text-f1-text-muted'}`}>
                                {formatGap(gaps?.gapToLeader)}
                            </span>

                            {/* Interval */}
                            <span className="text-right text-[10px] font-mono text-f1-text-muted tabular-nums">
                                {gaps?.interval != null ? formatInterval(gaps.interval) : (pos.position === 1 ? '---' : '---')}
                            </span>
                        </div>
                    );
                })}

                {/* Retired drivers separator */}
                {retiredList.length > 0 && (
                    <div className="px-4 py-1.5 bg-f1-surface-alt/40 border-y border-f1-border/50">
                        <span className="text-[9px] font-semibold text-red-400/80 uppercase tracking-widest">
                            Retired
                        </span>
                    </div>
                )}

                {/* Retired drivers */}
                {retiredList.map(({ driver_number, status, lastLap }) => {
                    const driver = drivers.get(driver_number);
                    if (!driver) return null;

                    const displayStatus = status.toLowerCase().includes('not classified')
                        ? 'DNS' : 'DNF';

                    return (
                        <div
                            key={driver_number}
                            onClick={() => setSelectedDriverNumber(driver_number)}
                            className={`grid grid-cols-[32px_1fr_26px_70px_65px] gap-1 items-center px-4 py-2
                                border-b border-f1-border/20 cursor-pointer opacity-50
                                ${driver_number === selectedDriverNumber
                                    ? 'bg-f1-accent/10 border-l-2 border-l-f1-accent opacity-80'
                                    : 'hover:opacity-70'}`}
                        >
                            <span className="font-mono font-bold text-[10px] text-red-400">
                                {displayStatus}
                            </span>

                            <div className="flex items-center gap-2 min-w-0">
                                <div className="w-1 h-6 rounded-full flex-shrink-0 opacity-40"
                                    style={{ backgroundColor: driver.team_colour }} />
                                <span className="text-xs font-bold text-f1-text-muted line-through">
                                    {driver.name_acronym}
                                </span>
                            </div>

                            <span></span>

                            <span className="text-right text-[9px] font-mono text-red-400/70 truncate"
                                title={status}>
                                {status.length > 10 ? status.substring(0, 10) + '…' : status}
                            </span>

                            <span className="text-right text-[10px] font-mono text-f1-text-muted/50">
                                L{lastLap}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
