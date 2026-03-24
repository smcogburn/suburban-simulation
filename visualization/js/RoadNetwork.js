/**
 * RoadNetwork — renders roads as line geometry, colored by congestion ratio.
 */

import * as THREE from 'three';
import { project } from './SceneManager.js';

// Congestion color scale: free-flow green → yellow → red
function congestionColor(ratio) {
    // ratio: 1.0 = free flow, 2.0+ = heavily congested
    const t = Math.min((ratio - 1.0) / 1.5, 1.0); // normalize to [0,1]
    if (t < 0.5) {
        // green → yellow
        const s = t * 2;
        return new THREE.Color(s, 1, 0);
    } else {
        // yellow → red
        const s = (t - 0.5) * 2;
        return new THREE.Color(1, 1 - s, 0);
    }
}

// Road type → base width multiplier (visual only, lines don't have width in WebGL)
const ROAD_Y = {
    motorway: 3,
    motorway_link: 2,
    trunk: 3,
    trunk_link: 2,
    primary: 2,
    primary_link: 1,
    secondary: 1,
    secondary_link: 1,
    tertiary: 0.5,
    tertiary_link: 0.5,
    residential: 0,
    unclassified: 0,
};

export class RoadNetwork {
    constructor(roadsData) {
        this.segments = roadsData.segments;
        this.segmentIndexMap = new Map(); // id → {start, end} in position array
        this._mesh = null;
        this._positions = null;
        this._colors = null;
        this._build();
    }

    _build() {
        // Count total line vertices (each segment has N-1 line segments = N points)
        let totalPairs = 0;
        for (const seg of this.segments) {
            totalPairs += seg.coords.length - 1;
        }

        // 2 vertices per line pair, 3 floats per vertex
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

            this.segmentIndexMap.set(seg.id, {
                start: startIdx,
                end: vi,
                pairCount: seg.coords.length - 1,
            });
        }

        // Default color: dim gray (free flow)
        const defaultColor = new THREE.Color(0x334455);
        for (let i = 0; i < totalPairs * 2; i++) {
            this._colors[i * 3]     = defaultColor.r;
            this._colors[i * 3 + 1] = defaultColor.g;
            this._colors[i * 3 + 2] = defaultColor.b;
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(this._positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(this._colors, 3));

        const mat = new THREE.LineBasicMaterial({ vertexColors: true });
        this._mesh = new THREE.LineSegments(geo, mat);
        this._mesh.frustumCulled = false;
    }

    get mesh() {
        return this._mesh;
    }

    /**
     * Update road colors based on congestion data for a given time window index.
     * congestionData: { data: { segId: [ratio0, ratio1, ...] } }
     */
    applyCongestion(congestionData, windowIndex) {
        if (!congestionData) return;

        const data = congestionData.data;
        const colorAttr = this._mesh.geometry.getAttribute('color');

        for (const seg of this.segments) {
            const ratios = data[seg.id];
            const ratio = ratios ? ratios[windowIndex] : 1.0;
            const color = congestionColor(ratio || 1.0);

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

    /**
     * Reset all roads to the free-flow dim color.
     */
    resetColors() {
        const colorAttr = this._mesh.geometry.getAttribute('color');
        const defaultColor = new THREE.Color(0x334455);
        for (let i = 0; i < colorAttr.array.length / 3; i++) {
            colorAttr.array[i * 3]     = defaultColor.r;
            colorAttr.array[i * 3 + 1] = defaultColor.g;
            colorAttr.array[i * 3 + 2] = defaultColor.b;
        }
        colorAttr.needsUpdate = true;
    }
}
