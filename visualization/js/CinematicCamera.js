/**
 * CinematicCamera — Apple TV-style shot sequence when idle.
 *
 * Each shot: camera pans smoothly from startEye → endEye while looking at
 * startTarget → endTarget. At the end of each shot there is a HARD CUT to
 * the next shot's startEye (no crossfade). Activates after IDLE_TIMEOUT ms
 * of no user input; any input instantly returns to orbit mode.
 *
 * Tune shot coordinates after VIZ_BBOX expansion to the full corridor.
 * Scene space: CENTER = downtown Annapolis (0,0,0), SCALE = 100000.
 * x = east, z = south (positive z faces away from camera looking north).
 */

const IDLE_TIMEOUT = 8000; // ms before cinematic activates

// Each shot: smooth pan from start to end over `duration` ms, then hard cut.
// startTarget / endTarget: where the camera looks during the pan.
const SHOTS = [
    // 1. Street-level east-bound pan — like flying into downtown along the main artery
    {
        startEye:    [-2000, 150, -100],  startTarget: [-1500,  0, -100],
        endEye:      [ 1200, 150, -100],  endTarget:   [ 1700,  0, -100],
        duration: 12000,
    },
    // 2. God's-eye overhead drift — slowly across the whole scene
    {
        startEye:    [ -600, 5000, -400],  startTarget: [ -600, 0, -400],
        endEye:      [  800, 5000,  300],  endTarget:   [  800, 0,  300],
        duration: 10000,
    },
    // 3. Harbor approach from the south — Eastport/Spa Creek looking north toward downtown
    {
        startEye:    [ 600,  700, 3200],  startTarget: [0, 0,    0],
        endEye:      [ 300,  400, 1600],  endTarget:   [0, 0,    0],
        duration: 10000,
    },
    // 4. Low sweeping arc around State Circle — agents stream in every direction
    {
        startEye:    [-1200, 280, 1200],  startTarget: [0, 0, 0],
        endEye:      [ 1400, 280,  800],  endTarget:   [0, 0, 0],
        duration: 10000,
    },
    // 5. Elevated Naval Academy view — looking west over the waterfront
    {
        startEye:    [2200, 1400,  400],  startTarget: [200,  0,    0],
        endEye:      [1000, 1000, -800],  endTarget:   [  0,  0, -300],
        duration: 10000,
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

        const reset = () => this._resetIdle();
        window.addEventListener('mousemove',  reset);
        window.addEventListener('mousedown',  reset);
        window.addEventListener('wheel',      reset);
        window.addEventListener('touchstart', reset);
        window.addEventListener('keydown',    reset);

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
        this._shotIdx      = 0;
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
            const shot = SHOTS[0];

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

        const t    = easeInOut(this._elapsed / shot.duration);
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
