// Package leaderboard provides the TUI leaderboard component.
package leaderboard

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/metivta/metivta-eval/internal/tui/components"
)

// EvaluationMode represents the evaluation mode filter
type EvaluationMode string

const (
	ModeDaat EvaluationMode = "daat"
	ModeMteb EvaluationMode = "mteb"
	ModeAll  EvaluationMode = "all"
)

// LeaderboardEntry represents a single entry in the leaderboard
type LeaderboardEntry struct {
	Rank        int
	System      string
	Author      string
	NdcgAt10    float64
	MapAt100    float64
	MrrAt10     float64
	RecallAt100 float64
	Mode        EvaluationMode
	Timestamp   string
}

// Model represents the leaderboard TUI state
type Model struct {
	entries  []LeaderboardEntry
	cursor   int
	mode     EvaluationMode
	loading  bool
	spinner  spinner.Model
	err      error
	width    int
	height   int
	ready    bool
	quitting bool

	// Column widths
	colWidths columnWidths
}

type columnWidths struct {
	rank   int
	system int
	ndcg   int
	map_   int
	mrr    int
	recall int
	author int
}

// KeyMap defines the key bindings
type KeyMap struct {
	Up       key.Binding
	Down     key.Binding
	PageUp   key.Binding
	PageDown key.Binding
	Home     key.Binding
	End      key.Binding
	Mode     key.Binding
	Refresh  key.Binding
	Details  key.Binding
	Search   key.Binding
	Quit     key.Binding
	Help     key.Binding
}

// DefaultKeyMap returns the default key bindings
func DefaultKeyMap() KeyMap {
	return KeyMap{
		Up: key.NewBinding(
			key.WithKeys("up", "k"),
			key.WithHelp("k/up", "up"),
		),
		Down: key.NewBinding(
			key.WithKeys("down", "j"),
			key.WithHelp("j/down", "down"),
		),
		PageUp: key.NewBinding(
			key.WithKeys("pgup", "ctrl+u"),
			key.WithHelp("pgup", "page up"),
		),
		PageDown: key.NewBinding(
			key.WithKeys("pgdown", "ctrl+d"),
			key.WithHelp("pgdown", "page down"),
		),
		Home: key.NewBinding(
			key.WithKeys("home", "g"),
			key.WithHelp("g/home", "top"),
		),
		End: key.NewBinding(
			key.WithKeys("end", "G"),
			key.WithHelp("G/end", "bottom"),
		),
		Mode: key.NewBinding(
			key.WithKeys("m"),
			key.WithHelp("m", "toggle mode"),
		),
		Refresh: key.NewBinding(
			key.WithKeys("r"),
			key.WithHelp("r", "refresh"),
		),
		Details: key.NewBinding(
			key.WithKeys("enter"),
			key.WithHelp("enter", "details"),
		),
		Search: key.NewBinding(
			key.WithKeys("/"),
			key.WithHelp("/", "search"),
		),
		Quit: key.NewBinding(
			key.WithKeys("q", "ctrl+c"),
			key.WithHelp("q", "quit"),
		),
		Help: key.NewBinding(
			key.WithKeys("?"),
			key.WithHelp("?", "help"),
		),
	}
}

var keys = DefaultKeyMap()

// NewModel creates a new leaderboard model
func NewModel() Model {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(components.Primary)

	return Model{
		entries: []LeaderboardEntry{},
		cursor:  0,
		mode:    ModeAll,
		loading: true,
		spinner: s,
		colWidths: columnWidths{
			rank:   6,
			system: 25,
			ndcg:   10,
			map_:   10,
			mrr:    10,
			recall: 10,
			author: 20,
		},
	}
}

// NewModelWithMode creates a new leaderboard model with a specific mode
func NewModelWithMode(mode EvaluationMode) Model {
	m := NewModel()
	m.mode = mode
	return m
}

// Init initializes the model
func (m Model) Init() tea.Cmd {
	return tea.Batch(
		m.spinner.Tick,
		loadLeaderboard(m.mode),
	)
}

// Update handles messages
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch {
		case key.Matches(msg, keys.Quit):
			m.quitting = true
			return m, tea.Quit

		case key.Matches(msg, keys.Up):
			if m.cursor > 0 {
				m.cursor--
			}

		case key.Matches(msg, keys.Down):
			if m.cursor < len(m.entries)-1 {
				m.cursor++
			}

		case key.Matches(msg, keys.PageUp):
			m.cursor -= 10
			if m.cursor < 0 {
				m.cursor = 0
			}

		case key.Matches(msg, keys.PageDown):
			m.cursor += 10
			if m.cursor >= len(m.entries) {
				m.cursor = len(m.entries) - 1
			}

		case key.Matches(msg, keys.Home):
			m.cursor = 0

		case key.Matches(msg, keys.End):
			m.cursor = len(m.entries) - 1

		case key.Matches(msg, keys.Mode):
			m = m.cycleMode()
			return m, loadLeaderboard(m.mode)

		case key.Matches(msg, keys.Refresh):
			m.loading = true
			return m, loadLeaderboard(m.mode)
		}

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.ready = true

	case leaderboardMsg:
		m.loading = false
		m.entries = msg.entries
		m.err = msg.err
		if m.cursor >= len(m.entries) && len(m.entries) > 0 {
			m.cursor = len(m.entries) - 1
		}

	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd
	}

	return m, nil
}

func (m Model) cycleMode() Model {
	switch m.mode {
	case ModeAll:
		m.mode = ModeDaat
	case ModeDaat:
		m.mode = ModeMteb
	case ModeMteb:
		m.mode = ModeAll
	}
	m.loading = true
	return m
}

// View renders the model
func (m Model) View() string {
	if m.quitting {
		return ""
	}

	if !m.ready {
		return "\n  Initializing..."
	}

	var b strings.Builder

	// Header
	b.WriteString(m.renderHeader())
	b.WriteString("\n\n")

	// Loading state
	if m.loading {
		b.WriteString(m.renderLoading())
		return b.String()
	}

	// Error state
	if m.err != nil {
		b.WriteString(m.renderError())
		return b.String()
	}

	// Empty state
	if len(m.entries) == 0 {
		b.WriteString(m.renderEmpty())
		return b.String()
	}

	// Table
	b.WriteString(m.renderTable())
	b.WriteString("\n")

	// Help
	b.WriteString(m.renderHelp())

	return b.String()
}

func (m Model) renderHeader() string {
	title := components.LogoStyle.Render("MetivitaEval")
	subtitle := components.DimStyle.Render(" Leaderboard")

	modeLabel := m.renderModeLabel()

	header := lipgloss.JoinHorizontal(
		lipgloss.Center,
		title,
		subtitle,
		"  ",
		modeLabel,
	)

	return components.BoxStyle.Width(m.width - 4).Render(header)
}

func (m Model) renderModeLabel() string {
	switch m.mode {
	case ModeDaat:
		return components.ModeDaatStyle.Render("DAAT")
	case ModeMteb:
		return components.ModeMtebStyle.Render("MTEB")
	default:
		return components.BadgeStyle.Render("ALL")
	}
}

func (m Model) renderLoading() string {
	return lipgloss.NewStyle().
		Padding(2, 0).
		Render(m.spinner.View() + " Loading leaderboard...")
}

func (m Model) renderError() string {
	return components.ErrorStyle.Render(fmt.Sprintf("Error: %v", m.err))
}

func (m Model) renderEmpty() string {
	return components.MutedStyle.Render("No entries found")
}

func (m Model) renderTable() string {
	var b strings.Builder

	// Header row
	headerRow := m.renderTableHeader()
	b.WriteString(headerRow)
	b.WriteString("\n")

	// Separator
	separator := strings.Repeat("─", m.width-4)
	b.WriteString(components.MutedStyle.Render(separator))
	b.WriteString("\n")

	// Calculate visible rows based on height
	visibleRows := m.height - 12 // Account for header, help, padding
	if visibleRows < 5 {
		visibleRows = 5
	}

	// Calculate start index for scrolling
	startIdx := 0
	if m.cursor >= visibleRows {
		startIdx = m.cursor - visibleRows + 1
	}

	endIdx := startIdx + visibleRows
	if endIdx > len(m.entries) {
		endIdx = len(m.entries)
	}

	// Render visible rows
	for i := startIdx; i < endIdx; i++ {
		entry := m.entries[i]
		isSelected := i == m.cursor
		b.WriteString(m.renderTableRow(entry, isSelected))
		b.WriteString("\n")
	}

	// Scroll indicator
	if len(m.entries) > visibleRows {
		scrollInfo := fmt.Sprintf("%d/%d", m.cursor+1, len(m.entries))
		b.WriteString(components.MutedStyle.Render(scrollInfo))
	}

	return b.String()
}

func (m Model) renderTableHeader() string {
	cols := []string{
		padRight("Rank", m.colWidths.rank),
		padRight("System", m.colWidths.system),
		padRight("nDCG@10", m.colWidths.ndcg),
		padRight("MAP@100", m.colWidths.map_),
		padRight("MRR@10", m.colWidths.mrr),
		padRight("Recall@100", m.colWidths.recall),
		padRight("Author", m.colWidths.author),
	}

	row := ""
	for _, col := range cols {
		row += components.TableHeaderCellStyle.Render(col)
	}
	return row
}

func (m Model) renderTableRow(entry LeaderboardEntry, selected bool) string {
	// Rank with styling
	rankStr := fmt.Sprintf("%d", entry.Rank)
	rankStyle := components.StyleRank(entry.Rank)
	rank := padRight(rankStyle.Render(rankStr), m.colWidths.rank)

	// System name
	system := padRight(entry.System, m.colWidths.system)
	if len(system) > m.colWidths.system {
		system = system[:m.colWidths.system-3] + "..."
	}

	// Metrics with color coding
	ndcg := padRight(components.FormatFloat(entry.NdcgAt10), m.colWidths.ndcg)
	mapScore := padRight(components.FormatFloat(entry.MapAt100), m.colWidths.map_)
	mrr := padRight(components.FormatFloat(entry.MrrAt10), m.colWidths.mrr)
	recall := padRight(components.FormatFloat(entry.RecallAt100), m.colWidths.recall)

	// Author
	author := padRight(entry.Author, m.colWidths.author)
	if len(author) > m.colWidths.author {
		author = author[:m.colWidths.author-3] + "..."
	}

	// Build row
	cells := []string{rank, system, ndcg, mapScore, mrr, recall, author}

	var row string
	for _, cell := range cells {
		if selected {
			row += components.TableSelectedStyle.Render(cell)
		} else {
			row += components.TableCellStyle.Render(cell)
		}
	}

	// Add selection indicator
	if selected {
		row = components.SuccessStyle.Render("→ ") + row
	} else {
		row = "  " + row
	}

	return row
}

func (m Model) renderHelp() string {
	helpItems := [][]string{
		{"j/k", "navigate"},
		{"m", "mode"},
		{"r", "refresh"},
		{"enter", "details"},
		{"q", "quit"},
	}
	return components.RenderHelp(helpItems)
}

// Messages

type leaderboardMsg struct {
	entries []LeaderboardEntry
	err     error
}

func loadLeaderboard(mode EvaluationMode) tea.Cmd {
	return func() tea.Msg {
		// Mock data for now - in production this would call the API
		entries := getMockLeaderboardData(mode)
		return leaderboardMsg{entries: entries}
	}
}

func getMockLeaderboardData(mode EvaluationMode) []LeaderboardEntry {
	allEntries := []LeaderboardEntry{
		{Rank: 1, System: "TorahGPT Pro v2.1", Author: "OpenTorah Labs", NdcgAt10: 0.892, MapAt100: 0.845, MrrAt10: 0.918, RecallAt100: 0.956, Mode: ModeMteb},
		{Rank: 2, System: "SefariaSearch v3.0", Author: "Sefaria Team", NdcgAt10: 0.856, MapAt100: 0.812, MrrAt10: 0.889, RecallAt100: 0.934, Mode: ModeMteb},
		{Rank: 3, System: "HebrewBERT-Large", Author: "HUJI NLP", NdcgAt10: 0.834, MapAt100: 0.798, MrrAt10: 0.867, RecallAt100: 0.912, Mode: ModeMteb},
		{Rank: 4, System: "Talmud-Embeddings", Author: "Bar-Ilan AI", NdcgAt10: 0.821, MapAt100: 0.785, MrrAt10: 0.854, RecallAt100: 0.901, Mode: ModeMteb},
		{Rank: 5, System: "DivreYoel-RAG", Author: "Metivta Lab", NdcgAt10: 0.798, MapAt100: 0.756, MrrAt10: 0.832, RecallAt100: 0.889, Mode: ModeDaat},
		{Rank: 6, System: "Gemara-Search", Author: "YU Research", NdcgAt10: 0.776, MapAt100: 0.734, MrrAt10: 0.812, RecallAt100: 0.867, Mode: ModeDaat},
		{Rank: 7, System: "Mishna-Retriever", Author: "JTS Labs", NdcgAt10: 0.754, MapAt100: 0.712, MrrAt10: 0.789, RecallAt100: 0.845, Mode: ModeDaat},
		{Rank: 8, System: "HalaKHa-LLM", Author: "Touro AI", NdcgAt10: 0.732, MapAt100: 0.689, MrrAt10: 0.767, RecallAt100: 0.823, Mode: ModeDaat},
		{Rank: 9, System: "Parsha-Finder", Author: "OUPress Tech", NdcgAt10: 0.710, MapAt100: 0.667, MrrAt10: 0.745, RecallAt100: 0.801, Mode: ModeMteb},
		{Rank: 10, System: "Rashi-GPT", Author: "ArtScroll Labs", NdcgAt10: 0.688, MapAt100: 0.645, MrrAt10: 0.723, RecallAt100: 0.779, Mode: ModeMteb},
	}

	if mode == ModeAll {
		return allEntries
	}

	var filtered []LeaderboardEntry
	for _, e := range allEntries {
		if e.Mode == mode {
			filtered = append(filtered, e)
		}
	}

	// Re-rank
	for i := range filtered {
		filtered[i].Rank = i + 1
	}

	return filtered
}

// Helper functions

func padRight(s string, width int) string {
	if len(s) >= width {
		return s
	}
	return s + strings.Repeat(" ", width-len(s))
}
