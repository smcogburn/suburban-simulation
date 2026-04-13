/**
 * TransitLayer — renders GTFS route shapes as glowing ribbon quads.
 *
 * Visible only during transit x-ray mode. Each route is drawn in its
 * GTFS color (or blue default). Routes are rendered above the road network
 * so they're clearly visible even when roads are dimmed.
 *
 * Uses flat ribbon quads (Mesh) instead of LineSegments to avoid 1px WebGL
 * line aliasing/flickering at camera distance.
 */

import * as THREE from 'three';
import { project } from './SceneManager.js';

// Elevation above ground — well above roads (max road y=6) so routes are visible
const TRANSIT_Y   = 18;
const HALF_WIDTH  = 8; // world units — routes are prominent feature lines

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
        let totalPairs = 0;
        for (const route of this._routes) {
            if (route.path && route.path.length >= 2) {
                totalPairs += route.path.length - 1;
            }
        }

        // 6 vertices per quad (2 triangles, non-indexed)
        const VERTS_PER_PAIR = 6;
        const positions = new Float32Array(totalPairs * VERTS_PER_PAIR * 3);
        const colors    = new Float32Array(totalPairs * VERTS_PER_PAIR * 3);

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

                // Perpendicular to segment direction in the XZ plane
                const dx  = x1 - x0, dz = z1 - z0;
                const len = Math.sqrt(dx * dx + dz * dz) || 1;
                const px  = (-dz / len) * HALF_WIDTH;
                const pz  = ( dx / len) * HALF_WIDTH;

                // Four corners of the ribbon quad
                const A0x = x0 + px, A0z = z0 + pz;
                const A1x = x0 - px, A1z = z0 - pz;
                const B0x = x1 + px, B0z = z1 + pz;
                const B1x = x1 - px, B1z = z1 - pz;

                // Triangle 1: A0, B0, A1
                positions[vi*3]=A0x; positions[vi*3+1]=TRANSIT_Y; positions[vi*3+2]=A0z; colors[vi*3]=color.r; colors[vi*3+1]=color.g; colors[vi*3+2]=color.b; vi++;
                positions[vi*3]=B0x; positions[vi*3+1]=TRANSIT_Y; positions[vi*3+2]=B0z; colors[vi*3]=color.r; colors[vi*3+1]=color.g; colors[vi*3+2]=color.b; vi++;
                positions[vi*3]=A1x; positions[vi*3+1]=TRANSIT_Y; positions[vi*3+2]=A1z; colors[vi*3]=color.r; colors[vi*3+1]=color.g; colors[vi*3+2]=color.b; vi++;
                // Triangle 2: A1, B0, B1
                positions[vi*3]=A1x; positions[vi*3+1]=TRANSIT_Y; positions[vi*3+2]=A1z; colors[vi*3]=color.r; colors[vi*3+1]=color.g; colors[vi*3+2]=color.b; vi++;
                positions[vi*3]=B0x; positions[vi*3+1]=TRANSIT_Y; positions[vi*3+2]=B0z; colors[vi*3]=color.r; colors[vi*3+1]=color.g; colors[vi*3+2]=color.b; vi++;
                positions[vi*3]=B1x; positions[vi*3+1]=TRANSIT_Y; positions[vi*3+2]=B1z; colors[vi*3]=color.r; colors[vi*3+1]=color.g; colors[vi*3+2]=color.b; vi++;
            }
        }

        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('color',    new THREE.BufferAttribute(colors, 3));

        const mat = new THREE.MeshBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.9,
            depthWrite: false,   // overlay — don't compete with road depth values
            side: THREE.DoubleSide,
        });

        if (this._mesh) {
            this._mesh.geometry.dispose();
            this._mesh.material.dispose();
        }
        this._mesh = new THREE.Mesh(geo, mat);
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
