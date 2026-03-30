/**
 * TransitLayer — renders GTFS route shapes as glowing lines.
 *
 * Visible only during transit x-ray mode. Each route is drawn in its
 * GTFS color (or blue default). Routes are rendered above the road network
 * so they're clearly visible even when roads are dimmed.
 */

import * as THREE from 'three';
import { project } from './SceneManager.js';

// Elevation above ground — well above roads (max road y=6) so routes are visible
const TRANSIT_Y = 18;

export class TransitLayer {
    constructor() {
        this._mesh = null;
        this._routes = [];
        this._visible = false;
    }

    /**
     * Load and build geometry from transit_routes.json data.
     */
    load(data) {
        if (!data || !data.routes) return;
        this._routes = data.routes;
        this._build();
        this._mesh.visible = false; // hidden by default
        console.log(`TransitLayer: loaded ${this._routes.length} route shapes`);
    }

    _build() {
        // Each route path is a series of line segments
        let totalPairs = 0;
        for (const route of this._routes) {
            if (route.path && route.path.length >= 2) {
                totalPairs += route.path.length - 1;
            }
        }

        const positions = new Float32Array(totalPairs * 2 * 3);
        const colors    = new Float32Array(totalPairs * 2 * 3);

        let vi = 0;
        for (const route of this._routes) {
            if (!route.path || route.path.length < 2) continue;

            const color = new THREE.Color(route.color || '#4488ff');
            // Brighten slightly for visibility
            color.r = Math.min(color.r * 1.4, 1);
            color.g = Math.min(color.g * 1.4, 1);
            color.b = Math.min(color.b * 1.4, 1);

            for (let i = 0; i < route.path.length - 1; i++) {
                const [x0, z0] = project(route.path[i][0],     route.path[i][1]);
                const [x1, z1] = project(route.path[i + 1][0], route.path[i + 1][1]);

                positions[vi * 3]     = x0;
                positions[vi * 3 + 1] = TRANSIT_Y;
                positions[vi * 3 + 2] = z0;
                colors[vi * 3]     = color.r;
                colors[vi * 3 + 1] = color.g;
                colors[vi * 3 + 2] = color.b;
                vi++;

                positions[vi * 3]     = x1;
                positions[vi * 3 + 1] = TRANSIT_Y;
                positions[vi * 3 + 2] = z1;
                colors[vi * 3]     = color.r;
                colors[vi * 3 + 1] = color.g;
                colors[vi * 3 + 2] = color.b;
                vi++;
            }
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('color',    new THREE.BufferAttribute(colors, 3));

        const mat = new THREE.LineBasicMaterial({
            vertexColors: true,
            linewidth: 2,        // note: linewidth > 1 only works in some renderers
            transparent: true,
            opacity: 0.9,
        });

        if (this._mesh) {
            this._mesh.geometry.dispose();
            this._mesh.material.dispose();
        }
        this._mesh = new THREE.LineSegments(geo, mat);
        this._mesh.frustumCulled = false;
        this._mesh.renderOrder = 1; // draw on top of road network
    }

    get mesh() { return this._mesh; }

    show() {
        if (this._mesh) this._mesh.visible = true;
    }

    hide() {
        if (this._mesh) this._mesh.visible = false;
    }
}
