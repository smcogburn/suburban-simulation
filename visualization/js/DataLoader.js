/**
 * DataLoader — fetches and caches JSON export files.
 * All paths are relative to the visualization/ directory when served.
 */

const DATA_BASE = '../data/export/';
const cache = {};

async function loadJSON(filename) {
    if (cache[filename]) return cache[filename];
    const resp = await fetch(DATA_BASE + filename);
    if (!resp.ok) throw new Error(`Failed to load ${filename}: ${resp.status}`);
    const data = await resp.json();
    cache[filename] = data;
    return data;
}

export async function loadBuildings() {
    return loadJSON('buildings.json');
}

export async function loadRoads() {
    return loadJSON('roads.json');
}

export async function loadMetadata() {
    return loadJSON('metadata.json');
}

export async function loadTrips(scenario) {
    return loadJSON(`trips_${scenario}.json`);
}

export async function loadCongestion(scenario) {
    return loadJSON(`congestion_${scenario}.json`);
}

export async function loadTransitRoutes() {
    return loadJSON('transit_routes.json');
}

export async function preloadAll(scenarios = ['baseline']) {
    const tasks = [loadBuildings(), loadRoads(), loadMetadata()];
    for (const s of scenarios) {
        tasks.push(loadTrips(s).catch(() => null));
        tasks.push(loadCongestion(s).catch(() => null));
    }
    await Promise.all(tasks);
}
