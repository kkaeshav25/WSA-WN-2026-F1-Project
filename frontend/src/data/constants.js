/**
 * F1 Constants — Slim version
 *
 * Only WebSocket config and utility functions remain.
 * Team colors, drivers, and compounds are now fetched from OpenF1 API.
 */

/**
 * WebSocket configuration (for when the real simulation connects)
 */
export const WS_CONFIG = {
    url: 'ws://localhost:8765',
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
};

/**
 * Tire compound colors matching F1 broadcast
 */
export const COMPOUND_COLORS = {
    SOFT: '#FF3333',
    MEDIUM: '#FFD700',
    HARD: '#FFFFFF',
    INTERMEDIATE: '#43B02A',
    WET: '#0067FF',
};

/**
 * Track status mappings
 */
export const TRACK_STATUS = {
    1: { label: 'Green', color: '#00d27a' },
    2: { label: 'Yellow Flag', color: '#ffc107' },
    4: { label: 'Safety Car', color: '#ff8c00' },
    5: { label: 'Red Flag', color: '#e10600' },
    6: { label: 'VSC Deployed', color: '#ff8c00' },
    7: { label: 'VSC Ending', color: '#ffc107' },
};

/**
 * Marshal sector → Turn number mapping (Spa-Francorchamps)
 *
 * OpenF1 divides the track into ~20 marshal sectors.
 * Each sector maps to the nearest corner(s) based on track distance.
 * Derived from corner distances along the 7.004km circuit.
 */
export const MARSHAL_SECTOR_TO_TURNS = {
    1: 'T1',           // Start/Finish → La Source
    2: 'T1',           // La Source exit
    3: 'T2–T3',        // Eau Rouge approach
    4: 'T3–T4',        // Eau Rouge / Raidillon
    5: 'T5',           // Kemmel straight end
    6: 'T5–T6',        // Les Combes entry
    7: 'T6–T7',        // Les Combes / Malmedy
    8: 'T8',           // Rivage
    9: 'T9',           // Rivage exit
    10: 'T10',          // Pouhon entry
    11: 'T10–T11',      // Pouhon
    12: 'T12',          // Fagnes
    13: 'T13',          // Fagnes exit
    14: 'T14',          // Stavelot
    15: 'T15',          // Paul Frère
    16: 'T16',          // Blanchimont approach
    17: 'T16–T17',      // Blanchimont
    18: 'T18',          // Bus Stop chicane entry
    19: 'T18–T19',      // Bus Stop chicane
    20: 'T19',          // Bus Stop exit → pit entry
};

/**
 * Convert a marshal sector number to a turn label
 */
export function marshalSectorToTurnLabel(sector) {
    return MARSHAL_SECTOR_TO_TURNS[sector] || `TURN ${sector}`;
}

/**
 * Get compound color
 */
export function getCompoundColor(compound) {
    return COMPOUND_COLORS[compound?.toUpperCase()] || '#888888';
}
