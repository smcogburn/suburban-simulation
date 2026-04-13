/**
 * CinematicCamera — Apple TV-style shot sequence when idle.
 *
 * Each shot: camera pans smoothly from startEye → endEye while looking at
 * startTarget → endTarget. At the end of each shot there is a HARD CUT to
 * the next shot's startEye (no crossfade). Activates after IDLE_TIMEOUT ms
 * of no user input; any input instantly returns to orbit mode.
 *
 * Scene space: CENTER = (-76.66, 38.985), SCALE = 100000.
 * x = east, z = south (north is negative z).
 *
 * Named area world positions (x, z):
 *   Landover:    (-18389, 5040)   — far west, south
 *   Bowie:        (-5851, 4030)   — west, south
 *   Crofton:      (-2137, -1680)  — central
 *   Crownsville:  ( 6536, -5400)  — east, north
 *   Edgewater:    ( 7888,  4800)  — east, south
 *   Annapolis:    (13040,   660)  — far east, center
 *   Severna Park: ( 8922, -8540)  — east, far north
 *
 * All shots use linear interpolation (constant velocity — no ease in/out).
 */

const IDLE_TIMEOUT = 8000; // ms before cinematic activates

// Each shot: linear pan from start to end over `duration` ms, then hard cut.
// Camera moves at constant velocity — no acceleration or deceleration.
const SHOTS = [
    // 1. Grand corridor sweep — west (Landover) to east (Annapolis) at elevation
    {
        startEye:    [-17000, 12000, 10000], startTarget: [-14000, 0, 4000],
        endEye:      [ 12000, 12000, 10000], endTarget:   [ 11000, 0, 1000],
        duration: 50000,
    },
    // 2. Low Annapolis approach — gliding north from Edgewater into the peninsula
    {
        startEye:    [ 7000, 1200, 6500],  startTarget: [10000, 0,  600],
        endEye:      [11500,  700, 2500],  endTarget:   [13000, 0,    0],
        duration: 30000,
    },
    // 3. Severna Park ridge — looking south over the northern corridor
    {
        startEye:    [ 9500, 6000, -9500], startTarget: [ 8500, 0, -5500],
        endEye:      [ 5500, 6000, -7500], endTarget:   [ 5000, 0, -4000],
        duration: 36000,
    },
    // 4. Crofton to Crownsville — medium-altitude eastward pan through the central corridor
    {
        startEye:    [-3000, 5000, 2000],  startTarget: [  500, 0, -1500],
        endEye:      [ 7000, 5000, 1000],  endTarget:   [ 8500, 0, -2500],
        duration: 36000,
    },
    // 5. Western suburbs — Landover to Bowie steady glide eastward
    {
        startEye:    [-18000, 5500, 7000], startTarget: [-15000, 0, 4500],
        endEye:      [ -5000, 5500, 6000], endTarget:   [ -5000, 0, 3500],
        duration: 36000,
    },
];

function easeInOut(t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function lerp(a, b, t) { return a + (b - a) * t; }

export class CinematicCamera {
    constructor(controls, camera) {
        this.controls = controls;
        this.camera = camera;

        this._idleTimer    = null;
        this._active       = false;
        this._activating   = false; // true during glide-in to first shot

        this._shotIdx      = 0;
        this._elapsed      = 0;    // ms within current shot

        this._glideElapsed = 0;    // ms into the initial glide-in
        this._fromEye      = [0, 2800, 1800];
        this._fromTarget   = [0, 0, 0];

        // Only exit cinematic on genuine navigation gestures on the 3D canvas:
        // drag (pointerdown + move) or scroll/pinch (wheel). Plain mouse moves
        // and UI button clicks are ignored so the mode share panel stays usable.
        const canvas = controls.domElement;
        let _pointerDown = false;

        canvas.addEventListener('pointerdown', () => { _pointerDown = true; });
        window.addEventListener('pointerup',   () => { _pointerDown = false; });
        canvas.addEventListener('pointermove', () => {
            if (_pointerDown) this._resetIdle();
        });
        canvas.addEventListener('wheel', () => this._resetIdle(), { passive: true });

        // Touch pinch/drag on canvas
        canvas.addEventListener('touchstart', () => { _pointerDown = true; }, { passive: true });
        canvas.addEventListener('touchmove',  () => {
            if (_pointerDown) this._resetIdle();
        }, { passive: true });

        this._startIdleTimer();
    }

    _startIdleTimer() {
        clearTimeout(this._idleTimer);
        this._idleTimer = setTimeout(() => this._activate(), IDLE_TIMEOUT);
    }

    _activate() {
        this._fromEye    = this.camera.position.toArray();
        this._fromTarget = this.controls.target.toArray();
        this._activating   = true;
        this._active       = true;
        this._glideElapsed = 0;
        this._shotIdx      = Math.floor(Math.random() * SHOTS.length);
        this._elapsed      = 0;
        this.controls.enabled = false;
    }

    _resetIdle() {
        if (this._active || this._activating) {
            this._active     = false;
            this._activating = false;
            this.controls.enabled = true;
        }
        this._startIdleTimer();
    }

    /** Call from render loop. dt = delta time in seconds. */
    update(dt) {
        if (!this._active && !this._activating) return;

        const ms = dt * 1000;

        // ── Glide-in: smooth transition from user camera → first shot start ──
        if (this._activating) {
            const GLIDE_MS = 3000;
            this._glideElapsed += ms;
            const t = easeInOut(Math.min(this._glideElapsed / GLIDE_MS, 1));
            const shot = SHOTS[this._shotIdx];

            const eyeX = lerp(this._fromEye[0], shot.startEye[0], t);
            const eyeY = lerp(this._fromEye[1], shot.startEye[1], t);
            const eyeZ = lerp(this._fromEye[2], shot.startEye[2], t);
            const tX   = lerp(this._fromTarget[0], shot.startTarget[0], t);
            const tY   = lerp(this._fromTarget[1], shot.startTarget[1], t);
            const tZ   = lerp(this._fromTarget[2], shot.startTarget[2], t);

            this.camera.position.set(eyeX, eyeY, eyeZ);
            this.controls.target.set(tX, tY, tZ);
            this.camera.lookAt(tX, tY, tZ);

            if (this._glideElapsed >= GLIDE_MS) {
                this._activating = false; // _active stays true → shot sequence begins
            }
            return;
        }

        // ── Shot sequence: pan within shot, then hard cut ────────────────────
        this._elapsed += ms;
        const shot = SHOTS[this._shotIdx];

        if (this._elapsed >= shot.duration) {
            // Hard cut to next shot
            this._shotIdx = (this._shotIdx + 1) % SHOTS.length;
            this._elapsed = 0;
            return; // draw on next frame
        }

        const t    = this._elapsed / shot.duration; // linear — constant velocity
        const eyeX = lerp(shot.startEye[0],    shot.endEye[0],    t);
        const eyeY = lerp(shot.startEye[1],    shot.endEye[1],    t);
        const eyeZ = lerp(shot.startEye[2],    shot.endEye[2],    t);
        const tX   = lerp(shot.startTarget[0], shot.endTarget[0], t);
        const tY   = lerp(shot.startTarget[1], shot.endTarget[1], t);
        const tZ   = lerp(shot.startTarget[2], shot.endTarget[2], t);

        this.camera.position.set(eyeX, eyeY, eyeZ);
        this.controls.target.set(tX, tY, tZ);
        this.camera.lookAt(tX, tY, tZ);
    }
}
