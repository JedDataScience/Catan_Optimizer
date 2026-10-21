/**
 * boardValidation.js — Client-side checks that mirror the backend's board
 * validation (backend/schemas.py), so problems show up before Continue
 * instead of as a server error.
 */

import { RESOURCE_COUNTS, RESOURCE_MAP } from './constants';

/** Human-readable list of problems; empty when the board is ready. */
export function getBoardIssues(hexes) {
  const issues = [];

  const noResource = hexes.filter((h) => !h.resource).length;
  const noNumber   = hexes.filter((h) => h.resource && h.resource !== 'desert' && !h.number).length;
  // "tiles" matches the wording used everywhere else in the app
  if (noResource > 0) issues.push(`${noResource} ${noResource > 1 ? 'tiles need' : 'tile needs'} terrain`);
  if (noNumber   > 0) issues.push(`${noNumber} ${noNumber > 1 ? 'tiles need' : 'tile needs'} a number`);

  // Only check counts once every hex has a resource, so a half-built board
  // isn't flooded with warnings
  if (noResource === 0) {
    for (const [res, expected] of Object.entries(RESOURCE_COUNTS)) {
      const actual = hexes.filter((h) => h.resource === res).length;
      if (actual !== expected) {
        issues.push(`Use exactly ${expected} ${RESOURCE_MAP[res].label} tile${expected > 1 ? 's' : ''} (you have ${actual})`);
      }
    }
  }
  return issues;
}

export function isBoardValid(hexes) {
  return getBoardIssues(hexes).length === 0;
}
