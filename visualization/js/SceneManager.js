/**
 * SceneManager — Three.js scene, camera, renderer, lighting.
 */

import * as THREE from 'three';
import { OrbitControls } from '../lib/OrbitControls.js';

// Corridor center (Bowie→Annapolis midpoint)
const CENTER_LNG = -76.66;
const CENTER_LAT = 38.985;
const SCALE = 100000;

/**
 * Project WGS84 → Three.js world coordinates.
 * Returns [x, z] where x=east, z=south (Three.js y is up).
 */
export function project(lng, lat) {
    const x = (lng - CENTER_LNG) * Math.cos(CENTER_LAT * Math.PI / 180) * SCALE;
    const z = -(lat - CENTER_LAT) * SCALE; // negate so north = -z (forward)
    return [x, z];
}

export class SceneManager {
    constructor(canvas) {
        this.canvas = canvas;

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setClearColor(0x0a0a14);

        // Scene
        this.scene = new THREE.Scene();
        this.scene.fog = new THREE.FogExp2(0x0a0a14, 0.00002);

        // Camera
        this.camera = new THREE.PerspectiveCamera(
            55,
            window.innerWidth / window.innerHeight,
            1,
            200000
        );
        this.camera.position.set(0, 12000, 8000);
        this.camera.lookAt(0, 0, 0);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.controls.minDistance = 200;
        this.controls.maxDistance = 60000;
        this.controls.maxPolarAngle = Math.PI / 2.1;
        this.controls.target.set(0, 0, 0);

        // Lighting
        const ambient = new THREE.AmbientLight(0x404060, 0.8);
        this.scene.add(ambient);

        const dirLight = new THREE.DirectionalLight(0x8899cc, 0.6);
        dirLight.position.set(1000, 2000, 500);
        this.scene.add(dirLight);

        // Ground plane
        const groundGeo = new THREE.PlaneGeometry(120000, 120000);
        const groundMat = new THREE.MeshBasicMaterial({ color: 0x0d0d1a });
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -1;
        this.scene.add(ground);

        // Resize handling
        window.addEventListener('resize', () => this._onResize());
    }

    _onResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    render() {
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    add(object) {
        this.scene.add(object);
    }

    remove(object) {
        this.scene.remove(object);
    }
}
