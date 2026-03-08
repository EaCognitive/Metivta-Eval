// Package tui provides the terminal user interface for MetivitaEval.
package tui

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/metivta/metivta-eval/internal/tui/leaderboard"
)

// RunLeaderboard starts the leaderboard TUI.
func RunLeaderboard() error {
	model := leaderboard.NewModel()
	program := tea.NewProgram(model, tea.WithAltScreen())

	_, err := program.Run()
	if err != nil {
		return fmt.Errorf("error running leaderboard TUI: %w", err)
	}

	return nil
}

// RunLeaderboardWithMode starts the leaderboard TUI with a specific mode.
func RunLeaderboardWithMode(mode string) error {
	var evalMode leaderboard.EvaluationMode
	switch mode {
	case "daat":
		evalMode = leaderboard.ModeDaat
	case "mteb":
		evalMode = leaderboard.ModeMteb
	default:
		evalMode = leaderboard.ModeAll
	}

	model := leaderboard.NewModelWithMode(evalMode)
	program := tea.NewProgram(model, tea.WithAltScreen())

	_, err := program.Run()
	if err != nil {
		return fmt.Errorf("error running leaderboard TUI: %w", err)
	}

	return nil
}
