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
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, logarithmicDepthBuffer: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setClearColor(0x03040e);

        // Scene
        this.scene = new THREE.Scene();
        this.scene.fog = new THREE.FogExp2(0x03040e, 0.000018);

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
        this.ambientLight = new THREE.AmbientLight(0x1a2540, 0.9);
        this.scene.add(this.ambientLight);

        // Key light — from upper-left, cool blue-white
        this.dirLight = new THREE.DirectionalLight(0xc8d8f0, 1.2);
        this.dirLight.position.set(-1500, 2500, -800);
        this.scene.add(this.dirLight);

        // Fill light — from right/low, warm accent to separate shadow faces
        this.fillLight = new THREE.DirectionalLight(0x4466aa, 0.35);
        this.fillLight.position.set(2000, 600, 1200);
        this.scene.add(this.fillLight);

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

    updateDawnLighting(simTime) {
        const t = Math.min(simTime / 9000, 1); // 0 = 7:00 AM, 1 = 9:30 AM

        // Only the sky/fog shifts — pre-dawn near-black → deep morning blue
        // Lights stay constant so building colors remain clean throughout
        const bg = new THREE.Color().lerpColors(
            new THREE.Color(0x03040e),
            new THREE.Color(0x0c1428),
            t
        );
        this.renderer.setClearColor(bg);
        this.scene.fog.color.copy(bg);
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
