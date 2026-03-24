/**
 * TimeController — manages simulation time with play/pause and speed control.
 * Time is in seconds since 7:00 AM (0 = 7:00, 9000 = 9:30).
 */

export class TimeController {
    constructor() {
        this.simTime = 0;       // seconds since 7:00 AM
        this.playing = false;
        this.speed = 30;        // simulation seconds per real second

        this._lastRealTime = null;
        this._onChange = null;  // callback(simTime, windowIndex)

        this._slider = document.getElementById('time-slider');
        this._display = document.getElementById('time-display');
        this._playBtn = document.getElementById('play-btn');
        this._speedSelect = document.getElementById('speed-select');

        this._bindEvents();
    }

    _bindEvents() {
        this._playBtn.addEventListener('click', () => this.togglePlay());

        this._slider.addEventListener('input', () => {
            this.simTime = parseInt(this._slider.value);
            this._updateDisplay();
            if (this._onChange) this._onChange(this.simTime, this.windowIndex);
        });

        this._speedSelect.addEventListener('change', () => {
            this.speed = parseInt(this._speedSelect.value);
        });

        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && e.target.tagName !== 'INPUT') {
                e.preventDefault();
                this.togglePlay();
            }
        });
    }

    get windowIndex() {
        // Map simTime → congestion time window index (0-4, each 1800s)
        return Math.min(Math.floor(this.simTime / 1800), 4);
    }

    togglePlay() {
        this.playing = !this.playing;
        this._playBtn.textContent = this.playing ? '⏸' : '▶';
        if (this.playing) this._lastRealTime = performance.now();
    }

    setOnChange(fn) {
        this._onChange = fn;
    }

    /**
     * Advance simulation time. Call from render loop with current timestamp.
     * Returns true if time changed.
     */
    tick(realTimeMs) {
        if (!this.playing) {
            this._lastRealTime = realTimeMs;
            return false;
        }

        const dt = (realTimeMs - this._lastRealTime) / 1000; // real seconds
        this._lastRealTime = realTimeMs;

        const prevWindow = this.windowIndex;
        this.simTime = Math.min(this.simTime + dt * this.speed, 9000);

        if (this.simTime >= 9000) {
            this.simTime = 9000;
            this.playing = false;
            this._playBtn.textContent = '▶';
        }

        this._slider.value = Math.round(this.simTime);
        this._updateDisplay();

        const windowChanged = this.windowIndex !== prevWindow;
        if (windowChanged && this._onChange) {
            this._onChange(this.simTime, this.windowIndex);
        }

        return true;
    }

    _updateDisplay() {
        const totalSec = 7 * 3600 + Math.round(this.simTime);
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const ampm = h < 12 ? 'AM' : 'PM';
        const hDisplay = h > 12 ? h - 12 : h;
        this._display.textContent = `${hDisplay}:${String(m).padStart(2, '0')} ${ampm}`;
    }
}
