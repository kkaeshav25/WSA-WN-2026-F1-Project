/**
 * Mock track coordinates — a simplified Monza-like circuit
 * X/Y coordinates normalized to a 0–1000 range
 */
const MONZA_TRACK = [
    // Start/Finish straight
    { x: 200, y: 800 }, { x: 300, y: 800 }, { x: 400, y: 790 }, { x: 500, y: 780 },
    { x: 600, y: 770 }, { x: 700, y: 760 }, { x: 780, y: 740 },
    // Turn 1 – Variante del Rettifilo (chicane)
    { x: 830, y: 710 }, { x: 860, y: 670 }, { x: 870, y: 630 }, { x: 860, y: 590 },
    { x: 840, y: 560 },
    // Curva Grande
    { x: 810, y: 520 }, { x: 770, y: 480 }, { x: 720, y: 440 }, { x: 670, y: 410 },
    { x: 620, y: 390 }, { x: 570, y: 380 },
    // Variante della Roggia (chicane)
    { x: 520, y: 360 }, { x: 480, y: 330 }, { x: 460, y: 290 }, { x: 470, y: 250 },
    { x: 500, y: 220 },
    // Curve di Lesmo
    { x: 540, y: 200 }, { x: 560, y: 170 }, { x: 550, y: 140 }, { x: 520, y: 120 },
    { x: 480, y: 110 }, { x: 440, y: 120 }, { x: 410, y: 150 }, { x: 390, y: 180 },
    // Back straight
    { x: 360, y: 220 }, { x: 330, y: 270 }, { x: 300, y: 330 }, { x: 270, y: 400 },
    { x: 250, y: 460 },
    // Ascari chicane
    { x: 220, y: 500 }, { x: 190, y: 530 }, { x: 170, y: 560 }, { x: 180, y: 600 },
    { x: 210, y: 630 },
    // Parabolica
    { x: 190, y: 660 }, { x: 160, y: 690 }, { x: 140, y: 720 }, { x: 135, y: 750 },
    { x: 145, y: 780 }, { x: 170, y: 800 },
    // Close the loop
    { x: 200, y: 800 },
];

export default MONZA_TRACK;
