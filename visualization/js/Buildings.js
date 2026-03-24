/**
 * Buildings — extrudes building footprints from buildings.json into a merged mesh.
 */

import * as THREE from 'three';
import { mergeGeometries } from '../lib/BufferGeometryUtils.js';
import { project } from './SceneManager.js';

const BUILDING_COLOR = 0x2a2a3e;
const BUILDING_EMISSIVE = 0x111120;

export function buildBuildingMesh(buildingsData) {
    const geometries = [];

    for (const feature of buildingsData.features) {
        const coords = feature.coords;
        const height = feature.height || 9;

        // Build a THREE.Shape from the footprint polygon
        const shape = new THREE.Shape();
        const [x0, z0] = project(coords[0][0], coords[0][1]);
        shape.moveTo(x0, -z0); // negate z: after rotateX(-π/2), shape.y → -world.z
        for (let i = 1; i < coords.length; i++) {
            const [x, z] = project(coords[i][0], coords[i][1]);
            shape.lineTo(x, -z);
        }
        shape.closePath();

        const extrudeSettings = {
            depth: height,
            bevelEnabled: false,
        };

        try {
            const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
            // ExtrudeGeometry extrudes along Z; rotate so extrusion goes up (Y)
            geo.rotateX(-Math.PI / 2);
            geometries.push(geo);
        } catch {
            // Skip degenerate polygons
        }
    }

    if (geometries.length === 0) {
        return null;
    }

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
