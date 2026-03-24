/**
 * CinematicCamera — auto-orbits when no user interaction for IDLE_TIMEOUT ms.
 */

const IDLE_TIMEOUT = 10000; // 10 seconds

export class CinematicCamera {
    constructor(controls, camera) {
        this.controls = controls;
        this.camera = camera;
        this._idleTimer = null;
        this._active = false;
        this._angle = 0;
        this._radius = 3500;
        this._height = 2200;

        const resetIdle = () => this._resetIdle();
        window.addEventListener('mousemove', resetIdle);
        window.addEventListener('mousedown', resetIdle);
        window.addEventListener('wheel', resetIdle);
        window.addEventListener('touchstart', resetIdle);
        window.addEventListener('keydown', resetIdle);

        this._startIdleTimer();
    }

    _startIdleTimer() {
        clearTimeout(this._idleTimer);
        this._idleTimer = setTimeout(() => {
            this._active = true;
        }, IDLE_TIMEOUT);
    }

    _resetIdle() {
        this._active = false;
        this._startIdleTimer();
    }

    /**
     * Call from render loop. dt = delta time in seconds.
     */
    update(dt) {
        if (!this._active) return;

        this._angle += dt * 0.05; // radians/s

        const x = Math.cos(this._angle) * this._radius;
        const z = Math.sin(this._angle) * this._radius;
        this.camera.position.set(x, this._height, z);
        this.camera.lookAt(0, 0, 0);
        this.controls.target.set(0, 0, 0);
    }
}
