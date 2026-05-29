import type { PreviewState } from "../types/game";

const BOARD_SIZES = [9, 13, 19] as const;

interface PreviewTopbarProps {
  routeLabel: string;
}

interface PreviewSidePanelProps {
  state: PreviewState;
  onBoardSizeChange: (size: number) => void;
  onClearBoard: () => void;
}

export function PreviewTopbar({ routeLabel }: PreviewTopbarProps) {
  return (
    <section className="topbar">
      <div>
        <p className="eyebrow">React/TypeScript preview</p>
        <h1>rogue-go-arena</h1>
      </div>
      <div className="build-note" data-testid="preview-route">
        {routeLabel}
      </div>
    </section>
  );
}

export function PreviewSidePanel({ state, onBoardSizeChange, onClearBoard }: PreviewSidePanelProps) {
  return (
    <aside className="side-panel" aria-label="Preview controls">
      <div className="panel-section">
        <h2>Board</h2>
        <div className="segmented" aria-label="Board size">
          {BOARD_SIZES.map((size) => (
            <button
              className={state.boardSize === size ? "active" : ""}
              key={size}
              onClick={() => onBoardSizeChange(size)}
              type="button"
            >
              {size}x{size}
            </button>
          ))}
        </div>
      </div>

      <div className="panel-section">
        <h2>State Probe</h2>
        <dl className="probe-list">
          <div>
            <dt>Next</dt>
            <dd data-testid="next-color">{state.nextColor}</dd>
          </div>
          <div>
            <dt>Stones</dt>
            <dd data-testid="stone-count">{state.stones.length}</dd>
          </div>
          <div>
            <dt>Last</dt>
            <dd data-testid="last-click">{state.lastClick?.coord ?? "none"}</dd>
          </div>
        </dl>
      </div>

      <div className="panel-section">
        <h2>Server Contract</h2>
        <dl className="probe-list">
          <div>
            <dt>Revision</dt>
            <dd data-testid="server-revision">{state.serverStatus?.server_rev ?? "pending"}</dd>
          </div>
          <div>
            <dt>Engine</dt>
            <dd data-testid="engine-phase">{state.serverStatus?.engine_phase ?? "pending"}</dd>
          </div>
        </dl>
        {state.serverStatusError ? (
          <p className="error-text" data-testid="server-status-error">
            {state.serverStatusError}
          </p>
        ) : null}
      </div>

      <div className="panel-section">
        <h2>Migration Boundary</h2>
        <p>
          This preview validates the React canvas shell and reducer state while the legacy app
          remains the production root.
        </p>
        <button className="secondary" onClick={onClearBoard} type="button">
          Clear stones
        </button>
      </div>
    </aside>
  );
}
