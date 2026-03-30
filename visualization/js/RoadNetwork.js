/**
 * RoadNetwork — renders roads as line geometry, colored by congestion ratio.
 */

import * as THREE from 'three';
import { project } from './SceneManager.js';

// Congestion color scale: muted teal → yellow → red
// ratio: 1.0 = free flow, 2.5+ = heavily congested
function congestionColor(ratio) {
    const t = Math.min((ratio - 1.0) / 1.5, 1.0);
    const c = new THREE.Color();
    if (t < 0.5) {
        // muted teal → yellow
        const s = t * 2;
        c.setHSL(0.44 - s * 0.30, 0.40 + s * 0.50, 0.30 + s * 0.25);
    } else {
        // yellow → red
        const s = (t - 0.5) * 2;
        c.setHSL(0.14 - s * 0.14, 0.90, 0.55 - s * 0.10);
    }
    return c;
}

// Lerp between two congestion ratios
function lerpRatio(r0, r1, t) {
    return r0 + (r1 - r0) * t;
}

// Road type → elevation. All raised off y=0 to prevent z-fighting with ground plane.
const ROAD_Y = {
    motorway: 6, motorway_link: 5,
    trunk: 6, trunk_link: 5,
    primary: 4, primary_link: 3,
    secondary: 3, secondary_link: 3,
    tertiary: 2, tertiary_link: 2,
    residential: 1, unclassified: 1,
};

const DEFAULT_COLOR = new THREE.Color(0x1a2a3a); // pre-congestion dark blue

export class RoadNetwork {
    constructor(roadsData) {
        this.segments = roadsData.segments;
        this.segmentIndexMap = new Map();
        this._mesh = null;
        this._positions = null;
        this._colors = null;
        this._build();
    }

    _build() {
        let totalPairs = 0;
        for (const seg of this.segments) {
            totalPairs += seg.coords.length - 1;
        }

        this._positions = new Float32Array(totalPairs * 2 * 3);
        this._colors = new Float32Array(totalPairs * 2 * 3);

        let vi = 0;
        for (const seg of this.segments) {
            const startIdx = vi;
            const yBase = ROAD_Y[seg.highway] !== undefined ? ROAD_Y[seg.highway] : 0;

            for (let i = 0; i < seg.coords.length - 1; i++) {
                const [x0, z0] = project(seg.coords[i][0], seg.coords[i][1]);
                const [x1, z1] = project(seg.coords[i + 1][0], seg.coords[i + 1][1]);

                this._positions[vi * 3]     = x0;
                this._positions[vi * 3 + 1] = yBase;
                this._positions[vi * 3 + 2] = z0;
                vi++;

                this._positions[vi * 3]     = x1;
                this._positions[vi * 3 + 1] = yBase;
                this._positions[vi * 3 + 2] = z1;
                vi++;
            }

            this.segmentIndexMap.set(seg.id, { start: startIdx, end: vi });
        }

        // Default: dim pre-congestion color
        for (let i = 0; i < totalPairs * 2; i++) {
            this._colors[i * 3]     = DEFAULT_COLOR.r;
            this._colors[i * 3 + 1] = DEFAULT_COLOR.g;
            this._colors[i * 3 + 2] = DEFAULT_COLOR.b;
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(this._positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(this._colors, 3));

        const mat = new THREE.LineBasicMaterial({ vertexColors: true });
        this._mesh = new THREE.LineSegments(geo, mat);
        this._mesh.frustumCulled = false;
    }

    get mesh() { return this._mesh; }

    /**
     * Update road colors, interpolating smoothly between time windows.
     * simTime: seconds since 7:00 AM (0–9000).
     * congestionData: { data: { segId: [ratio0..ratio29] } } — 30 × 5-min windows
     */
    applyCongestion(congestionData, simTime) {
        if (!congestionData) return;

        // 30 windows × 5 minutes each = 9000s total
        const WINDOW_SIZE = 300; // 5 minutes per window
        const NUM_WINDOWS = 30;
        const windowFloat = simTime / WINDOW_SIZE;
        // Backward interpolation: blend from the PREVIOUS window into the CURRENT one.
        // This means roads only turn red AFTER traffic has arrived, not before.
        const w1 = Math.min(Math.floor(windowFloat), NUM_WINDOWS - 1); // current window
        const w0 = Math.max(w1 - 1, 0);                                 // previous window
        const frac = windowFloat - Math.floor(windowFloat); // 0.0–1.0 within window

        const data = congestionData.data;
        const colorAttr = this._mesh.geometry.getAttribute('color');

        for (const seg of this.segments) {
            const ratios = data[seg.id];
            let ratio;
            if (ratios) {
                ratio = lerpRatio(ratios[w0] || 1.0, ratios[w1] || 1.0, frac);
            } else {
                ratio = 1.0;
            }

            const color = congestionColor(ratio);
            const info = this.segmentIndexMap.get(seg.id);
            if (!info) continue;

            for (let vi = info.start; vi < info.end; vi++) {
                colorAttr.array[vi * 3]     = color.r;
                colorAttr.array[vi * 3 + 1] = color.g;
                colorAttr.array[vi * 3 + 2] = color.b;
            }
        }

        colorAttr.needsUpdate = true;
    }

    /** Reset all roads to pre-congestion dim color. */
    resetColors() {
        const colorAttr = this._mesh.geometry.getAttribute('color');
        for (let i = 0; i < colorAttr.array.length / 3; i++) {
            colorAttr.array[i * 3]     = DEFAULT_COLOR.r;
            colorAttr.array[i * 3 + 1] = DEFAULT_COLOR.g;
            colorAttr.array[i * 3 + 2] = DEFAULT_COLOR.b;
        }
        colorAttr.needsUpdate = true;
    }
}
