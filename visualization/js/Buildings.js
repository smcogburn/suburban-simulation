/**
 * Buildings — extrudes building footprints from buildings.json into a merged mesh.
 */

import * as THREE from 'three';
import { mergeGeometries } from '../lib/BufferGeometryUtils.js';
import { project } from './SceneManager.js';

const BUILDING_COLOR    = 0xC3C9D6 ; // dark navy-slate — complements the cyan roads
const BUILDING_EMISSIVE = 0x04060c; // barely-there blue, prevents pure black

// Height variation table for untagged buildings (height === 9).
// Seeded by building coordinates so heights are stable across reloads.
const HEIGHT_VARIATION = [3, 6, 9, 12, 15, 9, 6, 18, 9, 6];

function buildingHeight(feature) {
    const h = feature.height;
    if (!h || h === 9) {
        // Untagged — pick a variation based on location
        const lng = feature.coords[0][0];
        const lat = feature.coords[0][1];
        const idx = Math.abs(Math.floor(lng * 1000 + lat * 1000)) % HEIGHT_VARIATION.length;
        return HEIGHT_VARIATION[idx];
    }
    return h;
}

export function buildBuildingMesh(buildingsData) {
    const geometries = [];

    for (const feature of buildingsData.features) {
        const coords = feature.coords;
        const height = buildingHeight(feature);

        const shape = new THREE.Shape();
        const [x0, z0] = project(coords[0][0], coords[0][1]);
        shape.moveTo(x0, -z0);
        for (let i = 1; i < coords.length; i++) {
            const [x, z] = project(coords[i][0], coords[i][1]);
            shape.lineTo(x, -z);
        }
        shape.closePath();

        try {
            const geo = new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false });
            geo.rotateX(-Math.PI / 2);
            geometries.push(geo);
        } catch {
            // Skip degenerate polygons
        }
    }

    if (geometries.length === 0) return null;

    const merged = mergeGeometries(geometries, false);
    geometries.forEach(g => g.dispose());

    const mat = new THREE.MeshLambertMaterial({
        color: BUILDING_COLOR,
        emissive: BUILDING_EMISSIVE,
    });

    const mesh = new THREE.Mesh(merged, mat);
    mesh.frustumCulled = false;
    return mesh;
}
