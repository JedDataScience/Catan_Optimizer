/**
 * client.js — Calls to the optimizer backend.
 *
 * The backend URL comes from the VITE_API_URL environment variable (see
 * frontend/.env.example), defaulting to the local dev server.
 *
 * Every call accepts an AbortSignal so a request that's no longer needed
 * (the user moved on, changed a setting, or undid a placement) can be
 * cancelled and its late response ignored.
 */

export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Turn FastAPI's error `detail` into one readable line.
 * 422 validation errors look like [{ loc: [...], msg: 'Value error, hex 3: ...' }].
 */
export function formatErrorDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => String(d.msg ?? d).replace(/^Value error, /, ''))
      .join('; ');
  }
  return JSON.stringify(detail);
}

async function postJSON(path, body, { signal } = {}) {
  let resp;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    // fetch only throws on network failure (server down, CORS, offline)
    throw new Error(`Can't reach the optimizer server at ${API_BASE}. Is the backend running?`, { cause: e });
  }

  if (!resp.ok) {
    let message = `Server error ${resp.status}`;
    try {
      const data = await resp.json();
      if (data?.detail) message = formatErrorDetail(data.detail);
    } catch {
      // Body wasn't JSON; keep the status-code message
    }
    throw new Error(message);
  }
  return resp.json();
}

function boardPayload(hexes) {
  return hexes.map((h) => ({ id: h.id, resource: h.resource, number: h.number }));
}

export async function fetchRecommendations(state, signal) {
  const data = await postJSON('/recommend', {
    board:              boardPayload(state.hexes),
    ports:              state.ports,
    placed_settlements: state.placements,
    user_position:      state.userPosition,
    num_players:        state.numPlayers,
    draft_step:         state.draftStep,
    s1_id:              state.userS1,
    n_simulations:      state.nSimulations,
    strategy_weight:    state.strategyWeight,
  }, { signal });
  return data.rankings;
}

export function fetchBoardAnalysis(state, signal) {
  return postJSON('/board-analysis', { board: boardPayload(state.hexes) }, { signal });
}

export function fetchAnalysis(state, signal) {
  return postJSON('/analyze', {
    board:           boardPayload(state.hexes),
    ports:           state.ports,
    s1_id:           state.userS1,
    s2_id:           state.userS2,
    all_placements:  state.placements,
    num_players:     state.numPlayers,
    user_position:   state.userPosition,
    strategy_weight: state.strategyWeight,
  }, { signal });
}
