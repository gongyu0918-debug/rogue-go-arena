export type GameMode = "normal" | "rogue" | "ultimate";
export type PlayerColor = "black" | "white";

export interface MovePoint {
  x: number;
  y: number;
}

export type WsAction =
  | { action: "new_game"; mode?: GameMode; player_color?: PlayerColor; level?: string; [key: string]: unknown }
  | ({ action: "play" } & MovePoint)
  | { action: "pass" }
  | { action: "undo" }
  | { action: "score" }
  | { action: "resign" }
  | { action: "request_hint" }
  | { action: "reconnect" }
  | { action: "set_level"; level: string }
  | { action: "time_expired"; color: PlayerColor }
  | ({ action: "load_position" } & Record<string, unknown>)
  | { action: "rogue_select_card"; card_id: string }
  | { action: "challenge_refresh_offer" }
  | ({ action: "rogue_seal_point" } & MovePoint)
  | ({ action: "rogue_use_puppet" } & MovePoint)
  | { action: "rogue_use_twin" }
  | { action: "rogue_use_exchange"; from_x?: number; from_y?: number; to_x?: number; to_y?: number }
  | { action: "rogue_use_coach" }
  | { action: "ultimate_select_card"; card_id: string }
  | { action: "ultimate_quickthink_end" }
  | { action: "quickthink_shown"; key: string };

export interface GameStatePayload {
  board_size: number;
  board: unknown;
  moves: unknown[];
  current_turn: PlayerColor;
  player_color: PlayerColor;
  ai_color: PlayerColor;
  mode?: GameMode;
  [key: string]: unknown;
}

export interface AnalysisPayload {
  winrate?: number;
  scoreLead?: number;
  ownership?: unknown;
  moves?: unknown[];
  [key: string]: unknown;
}

export interface CardOffer {
  id: string;
  name?: string;
  desc?: string;
  description?: string;
  meta?: string;
  [key: string]: unknown;
}

export interface CardEvolution {
  level: number;
  charge: number;
  floor: number;
  next: number | null;
  max_level: number;
}

export interface CardImpactPayload {
  card_id: string | null;
  stones_gained: number;
  enemy_stones_lost: number;
  komi_gain: number;
  echo_points: [number, number][];
  echo_komi: number;
  evolution: CardEvolution;
  measured: boolean;
  winrate_before?: number;
  winrate_after?: number;
  winrate_delta?: number;
  lead_before?: number;
  lead_after?: number;
  lead_delta?: number;
}

/** Language-neutral message key sent next to the legacy Chinese text (app/domain/event_text.py). */
export interface EventKey {
  key?: string;
  params?: Record<string, unknown>;
}

export type WsMessage =
  | ({ type: "game_start" } & GameStatePayload)
  | ({ type: "game_state" } & GameStatePayload)
  | ({ type: "reconnected" } & GameStatePayload)
  | { type: "reconnect_failed" }
  | ({ type: "analysis" } & AnalysisPayload)
  | { type: "ai_move"; gtp: string; color: PlayerColor; x?: number | null; y?: number | null; [key: string]: unknown }
  | { type: "game_over"; winner: PlayerColor | "draw"; score?: string; reason?: string; [key: string]: unknown }
  | ({ type: "error"; message: string } & EventKey)
  | { type: "engine_not_ready"; message?: string; [key: string]: unknown }
  | { type: "level_set"; level: string }
  | { type: "rogue_offer"; cards: CardOffer[]; [key: string]: unknown }
  | { type: "ultimate_offer"; cards: CardOffer[]; [key: string]: unknown }
  | { type: "rogue_card_selected"; card_id: string; [key: string]: unknown }
  | { type: "rogue_ai_selected"; card_id: string; [key: string]: unknown }
  | { type: "ultimate_cards_selected"; player_card: string; ai_card: string; [key: string]: unknown }
  | ({ type: "rogue_event"; msg: string } & EventKey)
  | { type: "rogue_uses_update"; uses: number }
  | { type: "rogue_seal_update"; points: MovePoint[]; [key: string]: unknown }
  | { type: "rogue_seal_done" }
  | { type: "quickthink_armed"; key: string; seconds: number }
  | ({ type: "card_impact" } & CardImpactPayload)
  | ({ type: "card_evolved"; card_id: string | null; ultimate_twin: string | null } & CardEvolution);
