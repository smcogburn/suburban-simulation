/**
 * ScenarioPanel — handles the 4 scenario buttons and stats display.
 */

export class ScenarioPanel {
    constructor() {
        this._buttons = document.querySelectorAll('.scenario-btn');
        this._current = 'baseline';
        this._onChange = null;
    }

    setOnChange(fn) {
        this._onChange = fn;

        this._buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const scenario = btn.dataset.scenario;
                if (scenario === this._current) return;
                this._current = scenario;
                this._buttons.forEach(b => b.classList.toggle('active', b === btn));
                if (this._onChange) this._onChange(scenario);
            });
        });
    }

    get current() {
        return this._current;
    }

    /**
     * Update mode share stat bars.
     * stats: { car_pct, transit_pct, bicycle_pct, walk_pct }
     */
    updateStats(stats) {
        if (!stats) return;
        const set = (id, barId, pct) => {
            const el = document.getElementById(id);
            const bar = document.getElementById(barId);
            if (el) el.textContent = `${pct.toFixed(1)}%`;
            if (bar) bar.style.width = `${pct}%`;
        };
        set('pct-car',     'bar-car',     stats.car_pct     || 0);
        set('pct-transit', 'bar-transit', stats.transit_pct || 0);
        set('pct-bike',    'bar-bike',    stats.bicycle_pct || 0);
        set('pct-walk',    'bar-walk',    stats.walk_pct    || 0);
    }
}
