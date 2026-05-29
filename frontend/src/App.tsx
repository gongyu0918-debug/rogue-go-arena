import { useCallback, useEffect, useReducer } from "react";
import { getStatus } from "./api/client";
import { BoardCanvas } from "./board/BoardCanvas";
import { PreviewSidePanel, PreviewTopbar } from "./components/PreviewShell";
import { initialPreviewState, previewReducer } from "./state/previewReducer";
import type { BoardClick } from "./types/game";

export function App() {
  const [state, dispatch] = useReducer(previewReducer, initialPreviewState);

  useEffect(() => {
    let cancelled = false;
    getStatus()
      .then((status) => {
        if (!cancelled) {
          dispatch({ type: "set-server-status", status });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          dispatch({
            type: "set-server-status-error",
            error: error instanceof Error ? error.message : String(error)
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePointClick = useCallback((point: BoardClick) => {
    dispatch({ type: "place-stone", point });
  }, []);

  const handleBoardSizeChange = useCallback((size: number) => {
    dispatch({ type: "set-board-size", size });
  }, []);

  const handleClearBoard = useCallback(() => {
    dispatch({ type: "clear-board" });
  }, []);

  return (
    <main className="app">
      <PreviewTopbar routeLabel="/react-preview" />

      <section className="workspace">
        <BoardCanvas
          boardSize={state.boardSize}
          onPointClick={handlePointClick}
          stones={state.stones}
        />
        <PreviewSidePanel
          onBoardSizeChange={handleBoardSizeChange}
          onClearBoard={handleClearBoard}
          state={state}
        />
      </section>
    </main>
  );
}
