/**
 * main.js — entry point. Initializes all modules and runs the render loop.
 */

import { SceneManager } from './SceneManager.js';
import { buildBuildingMesh } from './Buildings.js';
import { RoadNetwork } from './RoadNetwork.js';
import { AgentSystem } from './AgentSystem.js';
import { TimeController } from './TimeController.js';
import { ScenarioPanel } from './ScenarioPanel.js';
import { CinematicCamera } from './CinematicCamera.js';
import {
    loadBuildings,
    loadRoads,
    loadMetadata,
    loadTrips,
    loadCongestion,
} from './DataLoader.js';

// ── Bootstrap ────────────────────────────────────────────────────────────────

async function init() {
    const loadingEl = document.getElementById('loading');

    // Create canvas and attach to body
    const canvas = document.createElement('canvas');
    document.body.insertBefore(canvas, document.body.firstChild);

    const scene = new SceneManager(canvas);
    const timeCtrl = new TimeController();
    const scenarioPanel = new ScenarioPanel();
    const agents = new AgentSystem();

    // ── Load base data ──────────────────────────────────────────────────────

    loadingEl.textContent = 'Loading buildings...';
    const [buildingsData, roadsData, metadata] = await Promise.all([
        loadBuildings(),
        loadRoads(),
        loadMetadata(),
    ]);

    // ── Build static scene objects ──────────────────────────────────────────

    loadingEl.textContent = 'Building scene geometry...';

    // Buildings (may take a moment to merge geometry)
    const buildingMesh = buildBuildingMesh(buildingsData);
    if (buildingMesh) scene.add(buildingMesh);

    // Roads
    const roadNet = new RoadNetwork(roadsData);
    scene.add(roadNet.mesh);

    // Agents (empty until scenario loads)
    scene.add(agents.mesh);

    // ── Load initial scenario (baseline) ──────────────────────────────────

    loadingEl.textContent = 'Loading trips (baseline)...';
    let currentCongestion = null;

    async function loadScenario(name) {
        loadingEl.style.display = 'flex';
        loadingEl.textContent = `Loading ${name}...`;

        try {
            const [tripsData, congData] = await Promise.all([
                loadTrips(name).catch(() => null),
                loadCongestion(name).catch(() => null),
            ]);

            if (tripsData) {
                agents.loadTrips(tripsData);
            }

            currentCongestion = congData;

            // Apply congestion for current time window
            if (congData) {
                roadNet.applyCongestion(congData, timeCtrl.windowIndex);
            } else {
                roadNet.resetColors();
            }

            // Update stats
            const stats = metadata?.stats?.[name];
            scenarioPanel.updateStats(stats);
        } catch (err) {
            console.warn('Failed to load scenario:', name, err);
        }

        loadingEl.style.display = 'none';
    }

    await loadScenario('baseline');

    // ── Cinematic camera ────────────────────────────────────────────────────

    const cinematic = new CinematicCamera(scene.controls, scene.camera);

    // ── Wire up scenario switching ──────────────────────────────────────────

    scenarioPanel.setOnChange(async (name) => {
        await loadScenario(name);
    });

    // ── Wire up time changes (update congestion on window change) ───────────

    timeCtrl.setOnChange((simTime, windowIndex) => {
        if (currentCongestion) {
            roadNet.applyCongestion(currentCongestion, windowIndex);
        }
    });

    // ── Fullscreen ──────────────────────────────────────────────────────────

    document.addEventListener('keydown', (e) => {
        if (e.code === 'KeyF') {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }
    });

    // ── Render loop ─────────────────────────────────────────────────────────

    let prevTime = performance.now();

    function animate(now) {
        requestAnimationFrame(animate);

        const dt = Math.min((now - prevTime) / 1000, 0.1); // cap at 100ms
        prevTime = now;

        timeCtrl.tick(now);
        agents.update(timeCtrl.simTime);
        cinematic.update(dt);
        scene.render();
    }

    requestAnimationFrame(animate);
}

init().catch(err => {
    console.error('Init failed:', err);
    document.getElementById('loading').textContent = 'Error: ' + err.message;
});
