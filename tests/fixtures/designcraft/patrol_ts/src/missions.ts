// Fixture with known design defects (see tests/test_designcraft.py).
export interface MissionDef { id: string; title: string; family: string; brief: string; reward: { coins: number }; requires: string[]; steps: Step[] }
type Step = { kind: string; at?: Target; text: string };
interface Target { x: number; z: number; label: string }

export const HOME: Target = { x: 0, z: 0, label: 'Harbour Office' };

export const MISSIONS: MissionDef[] = [
  { id: 'first', title: 'First Shift', family: 'delivery', brief: 'Take the mail to the lighthouse.', reward: { coins: 100 }, requires: [],
    steps: [ { kind: 'goto', at: { x: 400, z: 0, label: 'Lighthouse' }, text: 'Sail to the lighthouse' }, { kind: 'deliver', text: 'Hand over the mail' }, { kind: 'goto', at: HOME, text: 'Return to the Harbour Office' } ] },
  { id: 'nets', title: 'Tangled Nets', family: 'delivery', brief: 'Bring nets to the fishers.', reward: { coins: 100 }, requires: ['first'],
    steps: [ { kind: 'goto', at: { x: 0, z: 400, label: 'Fish Market' }, text: 'Sail to the market' }, { kind: 'deliver', text: 'Drop the nets' }, { kind: 'goto', at: HOME, text: 'Return to the Harbour Office' } ] },
  { id: 'crates', title: 'Crates for Mara', family: 'delivery', brief: 'Mara needs crates at the pier.', reward: { coins: 100 }, requires: ['first'],
    steps: [ { kind: 'goto', at: { x: -400, z: 0, label: 'Old Pier' }, text: 'Sail to the pier' }, { kind: 'deliver', text: 'Unload the crates' }, { kind: 'goto', at: HOME, text: 'Return to the Harbour Office' } ] },
  { id: 'storm', title: 'Storm Warning', family: 'rescue', brief: 'A boat is lost in the storm. Find it before dark.', reward: { coins: 100 }, requires: ['nets', 'ghost_mission'],
    steps: [ { kind: 'goto', at: { x: 900, z: 900, label: 'Outer Rocks' }, text: 'Search the outer rocks' }, { kind: 'tow', text: 'Tow the boat' }, { kind: 'goto', at: HOME, text: 'Return to the Harbour Office' } ] },
];

export const PLACES = [
  { id: 'office', name: 'Harbour Office', x: 0, z: 0 },
  { id: 'light', name: 'Lighthouse', x: 400, z: 0 },
  { id: 'market', name: 'Fish Market', x: 0, z: 400 },
  { id: 'pier', name: 'Old Pier', x: -400, z: 0 },
  { id: 'rocks', name: 'Outer Rocks', x: 900, z: 900 },
  { id: 'cave', name: 'Smugglers Cave', x: -900, z: 900 },
  { id: 'island', name: 'Gull Island', x: 900, z: -900 },
  { id: 'wreck', name: 'Wreck of the Wren', x: -900, z: -900 },
];

export const WAVES = [
  { id: 1, spawns: [{ type: 'gull' }] },
  { id: 2, spawns: [{ type: 'gull' }, { type: 'gull' }] },
  { id: 3, spawns: [{ type: 'gull' }, { type: 'gull' }, { type: 'gull' }] },
  { id: 4, spawns: [{ type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }] },
  { id: 5, spawns: [{ type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }] },
  { id: 6, spawns: [{ type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }, { type: 'gull' }] },
];

export const UPGRADES = [
  { id: 'sail', name: 'Better Sail', cost: 900 },
  { id: 'hull', name: 'Stronger Hull', cost: 1500 },
  { id: 'lamp', name: 'Storm Lamp', cost: 2000 },
  { id: 'radio', name: 'Radio', cost: 1200 },
  { id: 'net', name: 'Wide Net', cost: 800 },
  { id: 'paint', name: 'Fresh Paint', cost: 700 },
];
