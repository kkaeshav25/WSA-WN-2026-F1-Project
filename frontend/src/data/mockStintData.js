/**
 * Mock stint data for the Strategy page.
 *
 * This mirrors what the real simulation will eventually provide.
 * Each driver has an array of stints: { startLap, endLap, compound }
 * Pit stops are inferred where one stint ends and the next begins.
 *
 * Data source: 2023 Belgian GP Sprint (11 laps, wet start → inters)
 * - SC deployed lap 3-5 (ALO accident lap 3)
 * - ALO (14) DNF lap 3 (Accident), PER (11) DNF lap 8 (Collision damage)
 */

const COMPOUND_COLORS = {
    SOFT: '#FF3333',
    MEDIUM: '#FFD700',
    HARD: '#FFFFFF',
    INTERMEDIATE: '#43B02A',
    WET: '#0067FF',
};

/**
 * Driver stint data — ordered by finishing position
 * Mirrors the actual Belgium Sprint 2023 race data from FastF1
 */
const MOCK_STINT_DATA = {
    totalLaps: 11,
    drivers: [
        { number: 1, abbr: 'VER', team: 'Red Bull Racing', teamColor: '#3671C6', position: 1, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 81, abbr: 'PIA', team: 'McLaren', teamColor: '#FF8000', position: 2, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 10, abbr: 'GAS', team: 'Alpine', teamColor: '#2293D1', position: 3, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 44, abbr: 'HAM', team: 'Mercedes', teamColor: '#27F4D2', position: 4, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 55, abbr: 'SAI', team: 'Ferrari', teamColor: '#E8002D', position: 5, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 16, abbr: 'LEC', team: 'Ferrari', teamColor: '#E8002D', position: 6, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 4, abbr: 'NOR', team: 'McLaren', teamColor: '#FF8000', position: 7, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 63, abbr: 'RUS', team: 'Mercedes', teamColor: '#27F4D2', position: 8, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 31, abbr: 'OCO', team: 'Alpine', teamColor: '#2293D1', position: 9, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 3, abbr: 'RIC', team: 'AlphaTauri', teamColor: '#5E8FAA', position: 10, stints: [{ startLap: 1, endLap: 11, compound: 'WET' }] },
        { number: 18, abbr: 'STR', team: 'Aston Martin', teamColor: '#229971', position: 11, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 23, abbr: 'ALB', team: 'Williams', teamColor: '#37BEDD', position: 12, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 77, abbr: 'BOT', team: 'Alfa Romeo', teamColor: '#C92D4B', position: 13, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 2, abbr: 'SAR', team: 'Williams', teamColor: '#37BEDD', position: 14, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 20, abbr: 'MAG', team: 'Haas', teamColor: '#B6BABD', position: 15, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 24, abbr: 'ZHO', team: 'Alfa Romeo', teamColor: '#C92D4B', position: 16, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 27, abbr: 'HUL', team: 'Haas', teamColor: '#B6BABD', position: 17, stints: [{ startLap: 1, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 22, abbr: 'TSU', team: 'AlphaTauri', teamColor: '#5E8FAA', position: 18, stints: [{ startLap: 1, endLap: 1, compound: 'WET' }, { startLap: 2, endLap: 11, compound: 'INTERMEDIATE' }] },
        { number: 11, abbr: 'PER', team: 'Red Bull Racing', teamColor: '#3671C6', position: 19, stints: [{ startLap: 1, endLap: 8, compound: 'WET' }] },              // DNF Lap 8 — Collision damage
        { number: 14, abbr: 'ALO', team: 'Aston Martin', teamColor: '#229971', position: 20, stints: [{ startLap: 1, endLap: 3, compound: 'INTERMEDIATE' }] },      // DNF Lap 3 — Accident
    ],
    raceEvents: [
        { type: 'SC', startLap: 3, endLap: 5, label: 'Safety Car' },
    ],
};

export { COMPOUND_COLORS };
export default MOCK_STINT_DATA;
