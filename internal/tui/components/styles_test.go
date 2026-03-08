package components

import (
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestStyleRank(t *testing.T) {
	tests := []struct {
		rank     int
		expected lipgloss.Style
	}{
		{1, TableRankFirstStyle},
		{2, TableRankSecondStyle},
		{3, TableRankThirdStyle},
		{4, BaseStyle},
		{10, BaseStyle},
		{0, BaseStyle},
	}

	for _, tt := range tests {
		result := StyleRank(tt.rank)
		if result.GetForeground() != tt.expected.GetForeground() {
			t.Errorf("StyleRank(%d) foreground mismatch", tt.rank)
		}
	}
}

func TestStyleMetric(t *testing.T) {
	tests := []struct {
		value    float64
		expected lipgloss.Style
	}{
		{0.9, MetricHighStyle}, // >= 0.8
		{0.8, MetricHighStyle}, // >= 0.8
		{0.79, MetricMedStyle}, // >= 0.5, < 0.8
		{0.5, MetricMedStyle},  // >= 0.5
		{0.49, MetricLowStyle}, // < 0.5
		{0.0, MetricLowStyle},  // < 0.5
	}

	for _, tt := range tests {
		result := StyleMetric(tt.value)
		if result.GetForeground() != tt.expected.GetForeground() {
			t.Errorf("StyleMetric(%f) foreground mismatch", tt.value)
		}
	}
}

func TestFormatFloat(t *testing.T) {
	tests := []struct {
		value    float64
		expected string
	}{
		{0.892, "0.892"},
		{0.0, "0.000"},
		{1.0, "1.000"},
		{0.5, "0.500"},
		{0.123, "0.123"},
	}

	for _, tt := range tests {
		result := FormatFloat(tt.value)
		if result != tt.expected {
			t.Errorf("FormatFloat(%f) = %q, want %q", tt.value, result, tt.expected)
		}
	}
}

func TestFormatScore(t *testing.T) {
	// FormatScore returns styled string, so we just check it doesn't panic
	result := FormatScore(0.85)
	if result == "" {
		t.Error("FormatScore should not return empty string")
	}
}

func TestRenderHelpItem(t *testing.T) {
	result := RenderHelpItem("j/k", "navigate")
	if result == "" {
		t.Error("RenderHelpItem should not return empty string")
	}
	// Should contain both key and description
	if len(result) < 5 {
		t.Error("RenderHelpItem should include both key and description")
	}
}

func TestRenderHelp(t *testing.T) {
	items := [][]string{
		{"j/k", "navigate"},
		{"m", "mode"},
		{"q", "quit"},
	}

	result := RenderHelp(items)
	if result == "" {
		t.Error("RenderHelp should not return empty string")
	}
}

func TestRenderHelp_Empty(t *testing.T) {
	result := RenderHelp([][]string{})
	// Should not panic, just return styled empty string
	_ = result
}

func TestRenderHelp_InvalidItems(t *testing.T) {
	items := [][]string{
		{"only_one"}, // Invalid - needs 2 elements
		{"key", "desc"},
	}

	result := RenderHelp(items)
	// Should skip invalid items but not panic
	_ = result
}

func TestIntToString(t *testing.T) {
	tests := []struct {
		input    int
		expected string
	}{
		{0, "0"},
		{1, "1"},
		{10, "10"},
		{123, "123"},
		{-5, "-5"},
	}

	for _, tt := range tests {
		result := intToString(tt.input)
		if result != tt.expected {
			t.Errorf("intToString(%d) = %q, want %q", tt.input, result, tt.expected)
		}
	}
}

func TestPadLeft(t *testing.T) {
	tests := []struct {
		input    string
		length   int
		pad      byte
		expected string
	}{
		{"5", 3, '0', "005"},
		{"12", 3, '0', "012"},
		{"123", 3, '0', "123"},
		{"1234", 3, '0', "1234"},
		{"", 3, '0', "000"},
	}

	for _, tt := range tests {
		result := padLeft(tt.input, tt.length, tt.pad)
		if result != tt.expected {
			t.Errorf("padLeft(%q, %d, %c) = %q, want %q", tt.input, tt.length, tt.pad, result, tt.expected)
		}
	}
}

func TestColorPalette(t *testing.T) {
	// Verify colors are defined
	colors := []lipgloss.Color{
		Primary,
		Secondary,
		Accent,
		Success,
		Warning,
		Error,
		Background,
		Surface,
		Border,
		Muted,
		Foreground,
	}

	for i, c := range colors {
		if c == "" {
			t.Errorf("Color at index %d is empty", i)
		}
	}
}

func TestStylesNotNil(t *testing.T) {
	// Verify key styles are initialized
	styles := []lipgloss.Style{
		BaseStyle,
		BoldStyle,
		MutedStyle,
		SuccessStyle,
		WarningStyle,
		ErrorStyle,
		TitleStyle,
		TableHeaderStyle,
		TableCellStyle,
		TableSelectedStyle,
		BoxStyle,
		HelpStyle,
	}

	for i, s := range styles {
		// Just verify they don't panic when rendering
		result := s.Render("test")
		if result == "" {
			t.Errorf("Style at index %d renders empty", i)
		}
	}
}

func TestSpinnerFrames(t *testing.T) {
	if len(SpinnerFrames) == 0 {
		t.Error("SpinnerFrames should not be empty")
	}

	for i, frame := range SpinnerFrames {
		if frame == "" {
			t.Errorf("SpinnerFrames[%d] is empty", i)
		}
	}
}
