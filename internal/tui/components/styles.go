// Package components provides reusable TUI components for MetivitaEval.
package components

import "github.com/charmbracelet/lipgloss"

// Supabase-inspired dark color palette
var (
	// Primary brand colors (Supabase green)
	Primary   = lipgloss.Color("#3ECF8E") // Supabase green
	Secondary = lipgloss.Color("#1C1C1C") // Dark surface
	Accent    = lipgloss.Color("#3ECF8E") // Green accent

	// Semantic colors
	Success = lipgloss.Color("#3ECF8E") // Green
	Warning = lipgloss.Color("#F5A623") // Orange/amber
	Error   = lipgloss.Color("#F56565") // Red

	// Grayscale (dark theme)
	Background    = lipgloss.Color("#1C1C1C") // Darkest
	Surface       = lipgloss.Color("#2D2D2D") // Cards/panels
	SurfaceLight  = lipgloss.Color("#3D3D3D") // Elevated
	Border        = lipgloss.Color("#444444") // Borders
	Muted         = lipgloss.Color("#6E6E6E") // Muted text
	Foreground    = lipgloss.Color("#EDEDED") // Primary text
	ForegroundDim = lipgloss.Color("#A0A0A0") // Secondary text

	// Table colors
	TableHeader = lipgloss.Color("#3ECF8E")
	Highlight   = lipgloss.Color("#3ECF8E")
)

// Base styles
var (
	BaseStyle = lipgloss.NewStyle().
			Foreground(Foreground)

	BoldStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(Foreground)

	MutedStyle = lipgloss.NewStyle().
			Foreground(Muted)

	DimStyle = lipgloss.NewStyle().
			Foreground(ForegroundDim)

	// Status styles
	SuccessStyle = lipgloss.NewStyle().
			Foreground(Success).
			Bold(true)

	WarningStyle = lipgloss.NewStyle().
			Foreground(Warning).
			Bold(true)

	ErrorStyle = lipgloss.NewStyle().
			Foreground(Error).
			Bold(true)

	// Title and header styles
	TitleStyle = lipgloss.NewStyle().
			Foreground(Primary).
			Bold(true).
			Padding(0, 1)

	SubtitleStyle = lipgloss.NewStyle().
			Foreground(ForegroundDim).
			Italic(true)

	HeaderStyle = lipgloss.NewStyle().
			Foreground(Foreground).
			Background(Surface).
			Bold(true).
			Padding(0, 2)

	// Logo style
	LogoStyle = lipgloss.NewStyle().
			Foreground(Primary).
			Bold(true)
)

// Table styles (Supabase table look)
var (
	TableBorderStyle = lipgloss.NewStyle().
				BorderForeground(Border)

	TableHeaderStyle = lipgloss.NewStyle().
				Foreground(Foreground).
				Background(Surface).
				Bold(true).
				Padding(0, 1)

	TableHeaderCellStyle = lipgloss.NewStyle().
				Foreground(ForegroundDim).
				Bold(true).
				Padding(0, 1).
				BorderBottom(true).
				BorderStyle(lipgloss.NormalBorder()).
				BorderForeground(Border)

	TableCellStyle = lipgloss.NewStyle().
			Foreground(Foreground).
			Padding(0, 1)

	TableSelectedStyle = lipgloss.NewStyle().
				Foreground(Background).
				Background(Primary).
				Bold(true).
				Padding(0, 1)

	TableRowStyle = lipgloss.NewStyle().
			BorderBottom(true).
			BorderStyle(lipgloss.NormalBorder()).
			BorderForeground(Border)

	// Rank badges
	TableRankFirstStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#FFD700")). // Gold
				Bold(true)

	TableRankSecondStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#C0C0C0")). // Silver
				Bold(true)

	TableRankThirdStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#CD7F32")). // Bronze
				Bold(true)
)

// Box and panel styles
var (
	BoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(Border).
			Background(Surface).
			Padding(1, 2)

	SelectedBoxStyle = lipgloss.NewStyle().
				Border(lipgloss.RoundedBorder()).
				BorderForeground(Primary).
				Background(Surface).
				Padding(1, 2)

	PanelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(Border).
			Background(Surface).
			Padding(0, 1)

	CardStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(Border).
			Background(Surface).
			Padding(1, 2).
			Margin(0, 1)
)

// Help and status bar styles (bottom bar like Supabase)
var (
	HelpStyle = lipgloss.NewStyle().
			Foreground(Muted).
			Padding(1, 0)

	HelpKeyStyle = lipgloss.NewStyle().
			Foreground(Primary).
			Bold(true)

	HelpDescStyle = lipgloss.NewStyle().
			Foreground(Muted)

	HelpSeparatorStyle = lipgloss.NewStyle().
				Foreground(Border)

	StatusBarStyle = lipgloss.NewStyle().
			Background(Surface).
			Foreground(Foreground).
			Padding(0, 1)

	StatusModeStyle = lipgloss.NewStyle().
			Background(Primary).
			Foreground(Background).
			Bold(true).
			Padding(0, 1)
)

// Metric styles
var (
	MetricLabelStyle = lipgloss.NewStyle().
				Foreground(Muted).
				Width(12)

	MetricValueStyle = lipgloss.NewStyle().
				Foreground(Foreground).
				Bold(true)

	MetricHighStyle = lipgloss.NewStyle().
			Foreground(Success).
			Bold(true)

	MetricMedStyle = lipgloss.NewStyle().
			Foreground(Warning).
			Bold(true)

	MetricLowStyle = lipgloss.NewStyle().
			Foreground(Error).
			Bold(true)
)

// Progress bar styles
var (
	ProgressBarStyle = lipgloss.NewStyle().
				Foreground(Primary)

	ProgressBarBgStyle = lipgloss.NewStyle().
				Foreground(Border)

	ProgressBarCompleteStyle = lipgloss.NewStyle().
					Foreground(Success)

	ProgressTextStyle = lipgloss.NewStyle().
				Foreground(Muted)
)

// Badge styles for evaluation modes
var (
	ModeDaatStyle = lipgloss.NewStyle().
			Background(lipgloss.Color("#6366F1")). // Indigo
			Foreground(Foreground).
			Bold(true).
			Padding(0, 1)

	ModeMtebStyle = lipgloss.NewStyle().
			Background(Primary). // Green (Supabase)
			Foreground(Background).
			Bold(true).
			Padding(0, 1)

	BadgeStyle = lipgloss.NewStyle().
			Background(SurfaceLight).
			Foreground(ForegroundDim).
			Padding(0, 1)

	BadgeActiveStyle = lipgloss.NewStyle().
				Background(Primary).
				Foreground(Background).
				Bold(true).
				Padding(0, 1)
)

// Input styles
var (
	InputStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(Border).
			Padding(0, 1)

	InputFocusedStyle = lipgloss.NewStyle().
				Border(lipgloss.RoundedBorder()).
				BorderForeground(Primary).
				Padding(0, 1)

	InputPlaceholderStyle = lipgloss.NewStyle().
				Foreground(Muted)
)

// Spinner characters
var SpinnerFrames = []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}

// Helper function to style rank
func StyleRank(rank int) lipgloss.Style {
	switch rank {
	case 1:
		return TableRankFirstStyle
	case 2:
		return TableRankSecondStyle
	case 3:
		return TableRankThirdStyle
	default:
		return BaseStyle
	}
}

// Helper function to style metric value based on score
func StyleMetric(value float64) lipgloss.Style {
	switch {
	case value >= 0.8:
		return MetricHighStyle
	case value >= 0.5:
		return MetricMedStyle
	default:
		return MetricLowStyle
	}
}

// FormatScore formats a score with appropriate styling
func FormatScore(score float64) string {
	style := StyleMetric(score)
	return style.Render(FormatFloat(score))
}

// FormatFloat formats a float to 3 decimal places
func FormatFloat(f float64) string {
	// Format to 3 decimal places
	intPart := int(f)
	fracPart := int((f - float64(intPart)) * 1000)
	if fracPart < 0 {
		fracPart = -fracPart
	}
	return intToString(intPart) + "." + padLeft(intToString(fracPart), 3, '0')
}

func intToString(i int) string {
	if i == 0 {
		return "0"
	}
	negative := i < 0
	if negative {
		i = -i
	}
	var digits []byte
	for i > 0 {
		digits = append([]byte{byte('0' + i%10)}, digits...)
		i /= 10
	}
	if negative {
		return "-" + string(digits)
	}
	return string(digits)
}

func padLeft(s string, length int, pad byte) string {
	for len(s) < length {
		s = string(pad) + s
	}
	return s
}

// RenderHelpItem renders a single help item
func RenderHelpItem(key, desc string) string {
	return HelpKeyStyle.Render(key) + " " + HelpDescStyle.Render(desc)
}

// RenderHelp renders the help bar
func RenderHelp(items [][]string) string {
	var rendered []string
	for _, item := range items {
		if len(item) >= 2 {
			rendered = append(rendered, RenderHelpItem(item[0], item[1]))
		}
	}
	separator := HelpSeparatorStyle.Render(" | ")
	result := ""
	for i, r := range rendered {
		if i > 0 {
			result += separator
		}
		result += r
	}
	return HelpStyle.Render(result)
}
