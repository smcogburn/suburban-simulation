/**
 * AgentSystem — animates trip agents as glowing dots along their paths.
 *
 * Uses THREE.Points for performance. All agents share one geometry;
 * inactive agents are moved to a hidden position (0, -9999, 0).
 */

import * as THREE from 'three';
import { project } from './SceneManager.js';

const HIDDEN = new THREE.Vector3(0, -9999, 0);
const AGENT_SIZE = 4.0;

const MODE_COLORS = {
    CAR:     new THREE.Color(0xff4444),
    TRANSIT: new THREE.Color(0x4488ff),
    BICYCLE: new THREE.Color(0x44ff88),
    WALK:    new THREE.Color(0xffcc00),
};

function makeCircleTexture(size = 64) {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const r = size / 2;
    const grad = ctx.createRadialGradient(r, r, 0, r, r, r);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.4, 'rgba(255,255,255,0.8)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}

// Filter: only show trips with ≥5% of waypoints inside this bbox.
// Update these bounds after expanding VIZ_BBOX in config.py + pipeline rerun.
const VIZ_BBOX = { w: -76.90, e: -76.42, s: 38.87, n: 39.10 };
const MIN_IN_BOX = 0.05;

export class AgentSystem {
    constructor() {
        this.trips = [];
        this._preparedPaths = [];
        this._points = null;
        this._positions = null;
        this._colors = null;
        this._maxAgents = 0;
        this._activeCount = 0;
        this._activeCounts = { CAR: 0, TRANSIT: 0, BICYCLE: 0, WALK: 0 };
        this._modeFilter = null; // null = show all; string = show only that mode
        this._initEmpty();
    }

    _initEmpty() {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(0), 3));
        geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(0), 3));
        const mat = new THREE.PointsMaterial({
            size: AGENT_SIZE,
            map: makeCircleTexture(),
            vertexColors: true,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: false,
        });
        this._points = new THREE.Points(geo, mat);
        this._points.frustumCulled = false;
    }

    /**
     * Load trip data for a scenario. Filters to trips within VIZ_BBOX.
     */
    loadTrips(tripsData) {
        const all = tripsData.trips;
        this.trips = all.filter(trip => {
            // Require at least 5 waypoints — 2-point trips are routing failures
            // (r5py returned a straight origin→destination line with no road geometry)
            if (!trip.path || trip.path.length < 5) return false;

            // Filter beeline trips: routing failures often produce a path that
            // follows roads briefly, then has one giant straight-line "jump"
            // segment across the map before rejoining roads at the destination.
            // Detect this by finding the max individual segment length and
            // comparing it to the median segment length. A real road path has
            // no segment dramatically longer than the others.
            // Skip this check for TRANSIT: GTFS paths legitimately contain long
            // inter-stop segments that would be incorrectly flagged as beelines.
            if (trip.mode !== 'TRANSIT') {
                const segLens = [];
                for (let i = 1; i < trip.path.length; i++) {
                    const ddlng = trip.path[i][0] - trip.path[i-1][0];
                    const ddlat = trip.path[i][1] - trip.path[i-1][1];
                    segLens.push(Math.sqrt(ddlng * ddlng + ddlat * ddlat));
                }
                const sorted = segLens.slice().sort((a, b) => a - b);
                const median = sorted[Math.floor(sorted.length / 2)];
                const maxSeg = sorted[sorted.length - 1];
                if (median > 0 && maxSeg / median > 20) return false; // giant jump — skip
            }

            let inBox = 0;
            for (const [lng, lat] of trip.path) {
                if (lng >= VIZ_BBOX.w && lng <= VIZ_BBOX.e &&
                    lat >= VIZ_BBOX.s && lat <= VIZ_BBOX.n) inBox++;
            }
            return inBox / trip.path.length >= MIN_IN_BOX;
        });
        console.log(`AgentSystem: showing ${this.trips.length} / ${all.length} trips within scene bounds`);
        this._maxAgents = this.trips.length;
        this._preparePaths();
        this._buildGeometry();
    }

    _preparePaths() {
        this._preparedPaths = this.trips.map(trip => {
            const path = trip.path;
            if (!path || path.length === 0) {
                return { projCoords: [], cumDist: [], totalDist: 0 };
            }

            const projCoords = path.map(([lng, lat]) => project(lng, lat));
            const cumDist = [0];
            let total = 0;
            for (let i = 1; i < projCoords.length; i++) {
                const dx = projCoords[i][0] - projCoords[i - 1][0];
                const dz = projCoords[i][1] - projCoords[i - 1][1];
                total += Math.sqrt(dx * dx + dz * dz);
                cumDist.push(total);
            }
            return { projCoords, cumDist, totalDist: total };
        });

        // Raw path coordinates are no longer needed — projCoords holds the
        // pre-projected equivalents. Free them to reduce mobile memory pressure.
        for (const trip of this.trips) {
            delete trip.path;
        }
    }

    _buildGeometry() {
        if (this._points) {
            this._points.geometry.dispose();
        }

        const n = this._maxAgents;
        this._positions = new Float32Array(n * 3);
        this._colors = new Float32Array(n * 3);

        // Init all hidden
        for (let i = 0; i < n; i++) {
            this._positions[i * 3]     = HIDDEN.x;
            this._positions[i * 3 + 1] = HIDDEN.y;
            this._positions[i * 3 + 2] = HIDDEN.z;
            this._colors[i * 3]     = 1;
            this._colors[i * 3 + 1] = 1;
            this._colors[i * 3 + 2] = 1;
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(this._positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(this._colors, 3));

        const mat = new THREE.PointsMaterial({
            size: AGENT_SIZE,
            map: makeCircleTexture(),
            vertexColors: true,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: false,
        });

        if (this._points) {
            this._points.geometry = geo;
            this._points.material.dispose();
            this._points.material = mat;
        } else {
            this._points = new THREE.Points(geo, mat);
            this._points.frustumCulled = false;
        }
    }

    get mesh() {
        return this._points;
    }

    /** Returns how many agents are currently moving (total). */
    getActiveCount() { return this._activeCount; }

    /** Returns per-mode live counts: { CAR, TRANSIT, BICYCLE, WALK } */
    getActiveCounts() { return this._activeCounts; }

    /**
     * Set an x-ray filter. Pass a mode string (e.g. "BICYCLE") to show only
     * that mode; pass null to show all modes.
     */
    setModeFilter(mode) { this._modeFilter = mode; }

    /**
     * Update agent positions for the given simulation time (seconds since 7AM).
     */
    update(simTime) {
        if (!this._points || this.trips.length === 0) return;

        const posAttr = this._points.geometry.getAttribute('position');
        const colAttr = this._points.geometry.getAttribute('color');
        this._activeCount = 0;
        this._activeCounts = { CAR: 0, TRANSIT: 0, BICYCLE: 0, WALK: 0 };

        for (let i = 0; i < this.trips.length; i++) {
            const trip = this.trips[i];
            const elapsed = simTime - trip.departure;
            const active = elapsed >= 0 && elapsed <= trip.duration;
            const visible = active && (!this._modeFilter || trip.mode === this._modeFilter);

            if (!visible) {
                posAttr.array[i * 3]     = HIDDEN.x;
                posAttr.array[i * 3 + 1] = HIDDEN.y;
                posAttr.array[i * 3 + 2] = HIDDEN.z;
            } else {
                const t = trip.duration > 0 ? elapsed / trip.duration : 0;
                const [x, z] = this._interpolatePath(i, t);
                posAttr.array[i * 3]     = x;
                posAttr.array[i * 3 + 1] = 8;
                posAttr.array[i * 3 + 2] = z;

                const color = MODE_COLORS[trip.mode] || MODE_COLORS.CAR;
                colAttr.array[i * 3]     = color.r;
                colAttr.array[i * 3 + 1] = color.g;
                colAttr.array[i * 3 + 2] = color.b;
                this._activeCount++;
            }

            // Count all active trips regardless of filter (for stats display)
            if (active && this._activeCounts[trip.mode] !== undefined) {
                this._activeCounts[trip.mode]++;
            }
        }

        posAttr.needsUpdate = true;
        colAttr.needsUpdate = true;
    }

    _interpolatePath(tripIndex, t) {
        const { projCoords, cumDist, totalDist } = this._preparedPaths[tripIndex];

        if (projCoords.length === 0) return [0, 0];
        if (projCoords.length === 1) return projCoords[0];

        const dist = t * totalDist;

        // Binary search for segment
        let lo = 0, hi = cumDist.length - 1;
        while (lo < hi - 1) {
            const mid = (lo + hi) >> 1;
            if (cumDist[mid] <= dist) lo = mid;
            else hi = mid;
        }

        const segDist = cumDist[hi] - cumDist[lo];
        if (segDist < 0.0001) return projCoords[lo];

        const s = (dist - cumDist[lo]) / segDist;
        const [x0, z0] = projCoords[lo];
        const [x1, z1] = projCoords[hi];
        return [x0 + (x1 - x0) * s, z0 + (z1 - z0) * s];
    }
}
