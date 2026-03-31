/**
 * main.js — entry point. Initializes all modules and runs the render loop.
 */

import * as THREE from 'three';
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
    loadTransitRoutes,
} from './DataLoader.js';
import { TransitLayer } from './TransitLayer.js';

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
    const transitLayer = new TransitLayer();

    // ── Load base data ──────────────────────────────────────────────────────

    loadingEl.textContent = 'Loading buildings...';
    const [buildingsData, roadsData, metadata, transitRoutesData] = await Promise.all([
        loadBuildings(),
        loadRoads(),
        loadMetadata(),
        loadTransitRoutes().catch(() => null),
    ]);

    // ── Build static scene objects ──────────────────────────────────────────

    loadingEl.textContent = 'Building scene geometry...';

    // Buildings (may take a moment to merge geometry)
    const buildingMesh = buildBuildingMesh(buildingsData);
    if (buildingMesh) scene.add(buildingMesh);

    // Roads
    const roadNet = new RoadNetwork(roadsData);
    scene.add(roadNet.mesh);

    // Transit route shapes (GTFS overlay — hidden until transit x-ray mode)
    if (transitRoutesData) {
        transitLayer.load(transitRoutesData);
        if (transitLayer.mesh) scene.add(transitLayer.mesh);
    }

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
                roadNet.applyCongestion(congData, timeCtrl.simTime);
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

    // ── Neighborhood labels ──────────────────────────────────────────────────
    // World positions (x, y, z) for each label. Adjust after VIZ_BBOX expansion.
    const LABELS = [
        { id: 'label-downtown', pos: new THREE.Vector3(0,    200,  -100) },
        { id: 'label-eastport', pos: new THREE.Vector3(544,  200,   800) },
        { id: 'label-naval',    pos: new THREE.Vector3(600,  200,  -200) },
        { id: 'label-spacreek', pos: new THREE.Vector3(300,  200,   900) },
        { id: 'label-west',     pos: new THREE.Vector3(-900, 200,  -200) },
    ];
    const labelEls = LABELS.map(l => document.getElementById(l.id));

    function updateLabels() {
        const v = new THREE.Vector3();
        for (let i = 0; i < LABELS.length; i++) {
            v.copy(LABELS[i].pos);
            v.project(scene.camera);
            const x = (v.x *  0.5 + 0.5) * window.innerWidth;
            const y = (v.y * -0.5 + 0.5) * window.innerHeight;
            const visible = v.z > -1 && v.z < 1;
            labelEls[i].style.left    = x + 'px';
            labelEls[i].style.top     = y + 'px';
            labelEls[i].style.display = visible ? 'block' : 'none';
        }
    }

    // ── Trip counter ────────────────────────────────────────────────────────
    const counterEl = document.getElementById('trip-counter');
    const liveEls = {
        CAR:     document.getElementById('live-car'),
        TRANSIT: document.getElementById('live-transit'),
        BICYCLE: document.getElementById('live-bike'),
        WALK:    document.getElementById('live-walk'),
    };

    // ── Wire up scenario switching ──────────────────────────────────────────

    scenarioPanel.setOnChange(async (name) => {
        await loadScenario(name);
    });

    // ── X-ray mode: click a stat row to filter agents by mode ───────────────

    let activeFilter = null;
    document.querySelectorAll('.stat-row[data-mode]').forEach(row => {
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => {
            const mode = row.dataset.mode;
            if (activeFilter === mode) {
                // Click same mode again → clear filter
                activeFilter = null;
                agents.setModeFilter(null);
                transitLayer.hide();
                document.querySelectorAll('.stat-row[data-mode]').forEach(r => {
                    r.classList.remove('xray-active', 'xray-dim');
                });
                // Restore road congestion colors
                if (currentCongestion) roadNet.applyCongestion(currentCongestion, timeCtrl.simTime);
                lastCongestionSimTime = -999;
            } else {
                activeFilter = mode;
                agents.setModeFilter(mode);
                document.querySelectorAll('.stat-row[data-mode]').forEach(r => {
                    r.classList.toggle('xray-active', r.dataset.mode === mode);
                    r.classList.toggle('xray-dim',    r.dataset.mode !== mode);
                });
                // Dim roads to gray so agents stand out
                roadNet.resetColors();
                // Transit route overlay stays under manual debug toggle — not auto-shown here
            }
        });
    });

    // ── Fullscreen + debug transit toggle ──────────────────────────────────

    let transitVisible = false;
    const transitToggleBtn = document.getElementById('transit-routes-toggle');

    function setTransitVisible(v) {
        transitVisible = v;
        if (v) { transitLayer.show(); } else { transitLayer.hide(); }
        if (transitToggleBtn) {
            transitToggleBtn.classList.toggle('active', v);
            transitToggleBtn.textContent = v ? 'Routes ✓' : 'Routes';
        }
    }

    if (transitToggleBtn) {
        transitToggleBtn.addEventListener('click', () => setTransitVisible(!transitVisible));
    }

    document.addEventListener('keydown', (e) => {
        if (e.code === 'KeyF') {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }
        if (e.code === 'KeyT') {
            setTransitVisible(!transitVisible);
        }
    });

    // ── Render loop ─────────────────────────────────────────────────────────

    let prevTime = performance.now();
    let lastCongestionSimTime = -999;

    function animate(now) {
        requestAnimationFrame(animate);

        const dt = Math.min((now - prevTime) / 1000, 0.1);
        prevTime = now;

        timeCtrl.tick(now);
        agents.update(timeCtrl.simTime);
        cinematic.update(dt);
        updateLabels();

        // Update road congestion colors only when simTime has moved ≥15 sim-seconds
        // (≈0.5 real seconds at 30× speed). Avoids uploading the full color buffer
        // to GPU every frame, which caused lag and visual flickering.
        // Skip update entirely when x-ray mode dims the roads to flat gray.
        const simTimeDelta = Math.abs(timeCtrl.simTime - lastCongestionSimTime);
        if (!activeFilter && currentCongestion && simTimeDelta >= 15) {
            roadNet.applyCongestion(currentCongestion, timeCtrl.simTime);
            lastCongestionSimTime = timeCtrl.simTime;
        }

        // Live mode counts
        const counts = agents.getActiveCounts();
        const total  = counts.CAR + counts.TRANSIT + counts.BICYCLE + counts.WALK;
        if (counterEl) counterEl.textContent = `● ${agents.getActiveCount()} active`;
        if (liveEls.CAR)     liveEls.CAR.textContent     = total > 0 ? `${counts.CAR} now`     : '';
        if (liveEls.TRANSIT) liveEls.TRANSIT.textContent = total > 0 ? `${counts.TRANSIT} now` : '';
        if (liveEls.BICYCLE) liveEls.BICYCLE.textContent = total > 0 ? `${counts.BICYCLE} now` : '';
        if (liveEls.WALK)    liveEls.WALK.textContent    = total > 0 ? `${counts.WALK} now`    : '';

        scene.render();
    }

    requestAnimationFrame(animate);
}

init().catch(err => {
    console.error('Init failed:', err);
    document.getElementById('loading').textContent = 'Error: ' + err.message;
});
