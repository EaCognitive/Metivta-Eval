package leaderboard

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

func TestNewModel(t *testing.T) {
	m := NewModel()

	if m.mode != ModeAll {
		t.Errorf("NewModel() mode = %v, want %v", m.mode, ModeAll)
	}

	if !m.loading {
		t.Error("NewModel() loading should be true initially")
	}

	if m.cursor != 0 {
		t.Errorf("NewModel() cursor = %v, want 0", m.cursor)
	}

	if len(m.entries) != 0 {
		t.Errorf("NewModel() entries should be empty, got %d", len(m.entries))
	}
}

func TestNewModelWithMode(t *testing.T) {
	tests := []struct {
		name     string
		mode     EvaluationMode
		expected EvaluationMode
	}{
		{"daat mode", ModeDaat, ModeDaat},
		{"mteb mode", ModeMteb, ModeMteb},
		{"all mode", ModeAll, ModeAll},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := NewModelWithMode(tt.mode)
			if m.mode != tt.expected {
				t.Errorf("NewModelWithMode(%v) mode = %v, want %v", tt.mode, m.mode, tt.expected)
			}
		})
	}
}

func TestModel_Init(t *testing.T) {
	m := NewModel()
	cmd := m.Init()

	if cmd == nil {
		t.Error("Init() should return a command")
	}
}

func TestModel_Update_Quit(t *testing.T) {
	m := NewModel()

	newModel, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})

	model := newModel.(Model)
	if !model.quitting {
		t.Error("Update(q) should set quitting to true")
	}

	if cmd == nil {
		t.Error("Update(q) should return a quit command")
	}
}

func TestModel_Update_Navigation(t *testing.T) {
	m := NewModel()
	m.loading = false
	m.entries = getMockLeaderboardData(ModeAll)

	// Test down navigation
	newModel, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'j'}})
	model := newModel.(Model)
	if model.cursor != 1 {
		t.Errorf("Update(j) cursor = %v, want 1", model.cursor)
	}

	// Test up navigation
	newModel, _ = model.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'k'}})
	model = newModel.(Model)
	if model.cursor != 0 {
		t.Errorf("Update(k) cursor = %v, want 0", model.cursor)
	}

	// Test home
	model.cursor = 5
	newModel, _ = model.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'g'}})
	model = newModel.(Model)
	if model.cursor != 0 {
		t.Errorf("Update(g) cursor = %v, want 0", model.cursor)
	}

	// Test end
	newModel, _ = model.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'G'}})
	model = newModel.(Model)
	if model.cursor != len(model.entries)-1 {
		t.Errorf("Update(G) cursor = %v, want %v", model.cursor, len(model.entries)-1)
	}
}

func TestModel_Update_ModeToggle(t *testing.T) {
	m := NewModel()
	m.mode = ModeAll

	// Toggle to daat
	newModel, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'m'}})
	model := newModel.(Model)
	if model.mode != ModeDaat {
		t.Errorf("Update(m) mode = %v, want %v", model.mode, ModeDaat)
	}

	// Toggle to mteb
	newModel, _ = model.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'m'}})
	model = newModel.(Model)
	if model.mode != ModeMteb {
		t.Errorf("Update(m) mode = %v, want %v", model.mode, ModeMteb)
	}

	// Toggle back to all
	newModel, _ = model.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'m'}})
	model = newModel.(Model)
	if model.mode != ModeAll {
		t.Errorf("Update(m) mode = %v, want %v", model.mode, ModeAll)
	}
}

func TestModel_Update_WindowSize(t *testing.T) {
	m := NewModel()

	newModel, _ := m.Update(tea.WindowSizeMsg{Width: 120, Height: 40})
	model := newModel.(Model)

	if model.width != 120 {
		t.Errorf("Update(WindowSizeMsg) width = %v, want 120", model.width)
	}

	if model.height != 40 {
		t.Errorf("Update(WindowSizeMsg) height = %v, want 40", model.height)
	}

	if !model.ready {
		t.Error("Update(WindowSizeMsg) should set ready to true")
	}
}

func TestModel_View(t *testing.T) {
	m := NewModel()
	m.ready = true
	m.loading = false
	m.entries = getMockLeaderboardData(ModeAll)
	m.width = 100
	m.height = 30

	view := m.View()

	if view == "" {
		t.Error("View() should not return empty string")
	}

	// Check for key elements
	if !containsSubstring(view, "MetivitaEval") {
		t.Error("View() should contain 'MetivitaEval'")
	}
}

func TestModel_View_Loading(t *testing.T) {
	m := NewModel()
	m.ready = true
	m.loading = true
	m.width = 100
	m.height = 30

	view := m.View()

	if !containsSubstring(view, "Loading") {
		t.Error("View() in loading state should contain 'Loading'")
	}
}

func TestModel_View_Empty(t *testing.T) {
	m := NewModel()
	m.ready = true
	m.loading = false
	m.entries = []LeaderboardEntry{}
	m.width = 100
	m.height = 30

	view := m.View()

	if !containsSubstring(view, "No entries") {
		t.Error("View() with no entries should show 'No entries'")
	}
}

func TestModel_View_Quitting(t *testing.T) {
	m := NewModel()
	m.quitting = true

	view := m.View()

	if view != "" {
		t.Error("View() when quitting should return empty string")
	}
}

func TestGetMockLeaderboardData(t *testing.T) {
	// Test all mode
	all := getMockLeaderboardData(ModeAll)
	if len(all) == 0 {
		t.Error("getMockLeaderboardData(ModeAll) should return entries")
	}

	// Test daat mode filtering
	daat := getMockLeaderboardData(ModeDaat)
	for _, e := range daat {
		if e.Mode != ModeDaat {
			t.Errorf("getMockLeaderboardData(ModeDaat) returned entry with mode %v", e.Mode)
		}
	}

	// Test mteb mode filtering
	mteb := getMockLeaderboardData(ModeMteb)
	for _, e := range mteb {
		if e.Mode != ModeMteb {
			t.Errorf("getMockLeaderboardData(ModeMteb) returned entry with mode %v", e.Mode)
		}
	}

	// Test re-ranking
	for i, e := range daat {
		if e.Rank != i+1 {
			t.Errorf("getMockLeaderboardData() entry %d has rank %d, want %d", i, e.Rank, i+1)
		}
	}
}

func TestLeaderboardMsg(t *testing.T) {
	m := NewModel()
	m.loading = true

	entries := getMockLeaderboardData(ModeAll)
	msg := leaderboardMsg{entries: entries}

	newModel, _ := m.Update(msg)
	model := newModel.(Model)

	if model.loading {
		t.Error("Update(leaderboardMsg) should set loading to false")
	}

	if len(model.entries) != len(entries) {
		t.Errorf("Update(leaderboardMsg) entries count = %d, want %d", len(model.entries), len(entries))
	}
}

func TestDefaultKeyMap(t *testing.T) {
	km := DefaultKeyMap()

	// Check some key bindings exist
	if len(km.Up.Keys()) == 0 {
		t.Error("DefaultKeyMap() Up should have keys")
	}

	if len(km.Down.Keys()) == 0 {
		t.Error("DefaultKeyMap() Down should have keys")
	}

	if len(km.Quit.Keys()) == 0 {
		t.Error("DefaultKeyMap() Quit should have keys")
	}
}

func TestPadRight(t *testing.T) {
	tests := []struct {
		input    string
		width    int
		expected string
	}{
		{"abc", 5, "abc  "},
		{"abc", 3, "abc"},
		{"abc", 2, "abc"},
		{"", 3, "   "},
	}

	for _, tt := range tests {
		result := padRight(tt.input, tt.width)
		if result != tt.expected {
			t.Errorf("padRight(%q, %d) = %q, want %q", tt.input, tt.width, result, tt.expected)
		}
	}
}

func containsSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
