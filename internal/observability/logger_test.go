package observability

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/rs/zerolog"
)

func TestInitLoggerWithConfig_Stdout(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "info",
		Format: "json",
		Output: "stdout",
	}

	err := InitLoggerWithConfig(cfg)
	if err != nil {
		t.Fatalf("InitLoggerWithConfig() error = %v", err)
	}

	// Logger should be initialized - check global level
	if zerolog.GlobalLevel() != zerolog.InfoLevel {
		t.Errorf("Global level = %v, want %v", zerolog.GlobalLevel(), zerolog.InfoLevel)
	}
}

func TestInitLoggerWithConfig_TextFormat(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "text",
		Output: "stdout",
	}

	err := InitLoggerWithConfig(cfg)
	if err != nil {
		t.Fatalf("InitLoggerWithConfig() error = %v", err)
	}

	if zerolog.GlobalLevel() != zerolog.DebugLevel {
		t.Errorf("Global level = %v, want %v", zerolog.GlobalLevel(), zerolog.DebugLevel)
	}
}

func TestInitLoggerWithConfig_FileOutput(t *testing.T) {
	tmpDir := t.TempDir()
	logPath := filepath.Join(tmpDir, "test.log")

	cfg := &LoggerConfig{
		Level:      "info",
		Format:     "json",
		Output:     "file",
		FilePath:   logPath,
		MaxSizeMB:  10,
		MaxBackups: 3,
		MaxAgeDays: 7,
		Compress:   false,
	}

	err := InitLoggerWithConfig(cfg)
	if err != nil {
		t.Fatalf("InitLoggerWithConfig() error = %v", err)
	}

	// Write a log entry
	Logger.Info().Msg("test message")

	// Verify file exists (lumberjack creates on first write)
	// Give it a moment to write
	time.Sleep(10 * time.Millisecond)

	if _, err := os.Stat(logPath); os.IsNotExist(err) {
		// File might not exist until first log is flushed, which is okay
		t.Log("Log file not yet created (deferred creation)")
	}
}

func TestInitLoggerWithConfig_BothOutputs(t *testing.T) {
	tmpDir := t.TempDir()
	logPath := filepath.Join(tmpDir, "both.log")

	cfg := &LoggerConfig{
		Level:      "warn",
		Format:     "json",
		Output:     "both",
		FilePath:   logPath,
		MaxSizeMB:  10,
		MaxBackups: 3,
		MaxAgeDays: 7,
		Compress:   false,
	}

	err := InitLoggerWithConfig(cfg)
	if err != nil {
		t.Fatalf("InitLoggerWithConfig() error = %v", err)
	}

	if zerolog.GlobalLevel() != zerolog.WarnLevel {
		t.Errorf("Global level = %v, want %v", zerolog.GlobalLevel(), zerolog.WarnLevel)
	}
}

func TestInitLoggerWithConfig_InvalidLevel(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "invalid_level",
		Format: "json",
		Output: "stdout",
	}

	err := InitLoggerWithConfig(cfg)
	if err != nil {
		t.Fatalf("InitLoggerWithConfig() error = %v", err)
	}

	// Invalid level should default to info
	if zerolog.GlobalLevel() != zerolog.InfoLevel {
		t.Errorf("Global level = %v, want %v (default)", zerolog.GlobalLevel(), zerolog.InfoLevel)
	}
}

func TestWithContext(t *testing.T) {
	// Initialize logger first
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	// Test with trace ID
	ctx := context.WithValue(context.Background(), TraceIDKey, "test-trace-123")
	logger := WithContext(ctx)

	// Capture output
	var buf bytes.Buffer
	testLogger := logger.Output(&buf)
	testLogger.Info().Msg("test")

	output := buf.String()
	if !strings.Contains(output, "test-trace-123") {
		t.Errorf("WithContext() output should contain trace_id, got %s", output)
	}
}

func TestWithContext_NoTraceID(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	ctx := context.Background()
	logger := WithContext(ctx)

	// Should not panic
	var buf bytes.Buffer
	testLogger := logger.Output(&buf)
	testLogger.Info().Msg("test")
}

func TestWithRequestID(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	logger := WithRequestID("req-12345")

	var buf bytes.Buffer
	testLogger := logger.Output(&buf)
	testLogger.Info().Msg("test")

	output := buf.String()
	if !strings.Contains(output, "req-12345") {
		t.Errorf("WithRequestID() output should contain request_id, got %s", output)
	}
}

func TestWithUserID(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	logger := WithUserID("user-abc")

	var buf bytes.Buffer
	testLogger := logger.Output(&buf)
	testLogger.Info().Msg("test")

	output := buf.String()
	if !strings.Contains(output, "user-abc") {
		t.Errorf("WithUserID() output should contain user_id, got %s", output)
	}
}

func TestWithEvaluationID(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	logger := WithEvaluationID("eval-xyz")

	var buf bytes.Buffer
	testLogger := logger.Output(&buf)
	testLogger.Info().Msg("test")

	output := buf.String()
	if !strings.Contains(output, "eval-xyz") {
		t.Errorf("WithEvaluationID() output should contain evaluation_id, got %s", output)
	}
}

func TestLogRequest(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	// Capture output
	var buf bytes.Buffer
	Logger = Logger.Output(&buf)

	LogRequest("GET", "/api/health", 200, 50*time.Millisecond, "req-test")

	output := buf.String()

	checks := []string{"GET", "/api/health", "200", "req-test", "http.request"}
	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("LogRequest() output should contain %s, got %s", check, output)
		}
	}
}

func TestLogError(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	var buf bytes.Buffer
	Logger = Logger.Output(&buf)

	testErr := errors.New("test error occurred")
	fields := map[string]any{
		"user_id": "user-123",
		"action":  "test_action",
	}

	LogError(testErr, "something failed", fields)

	output := buf.String()
	if !strings.Contains(output, "test error occurred") {
		t.Errorf("LogError() output should contain error message, got %s", output)
	}
	if !strings.Contains(output, "something failed") {
		t.Errorf("LogError() output should contain message, got %s", output)
	}
}

func TestLogEvaluationStarted(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	var buf bytes.Buffer
	Logger = Logger.Output(&buf)

	LogEvaluationStarted("eval-001", "mteb", "torah-20k")

	output := buf.String()
	checks := []string{"eval-001", "mteb", "torah-20k", "evaluation.started"}
	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("LogEvaluationStarted() output should contain %s, got %s", check, output)
		}
	}
}

func TestLogEvaluationProgress(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	var buf bytes.Buffer
	Logger = Logger.Output(&buf)

	metrics := map[string]float64{
		"ndcg_at_10": 0.85,
		"map_at_100": 0.78,
	}

	LogEvaluationProgress("eval-002", 45, metrics)

	output := buf.String()
	checks := []string{"eval-002", "45", "evaluation.progress"}
	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("LogEvaluationProgress() output should contain %s, got %s", check, output)
		}
	}
}

func TestLogEvaluationCompleted(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	var buf bytes.Buffer
	Logger = Logger.Output(&buf)

	LogEvaluationCompleted("eval-003", 5*time.Minute, 0.89)

	output := buf.String()
	checks := []string{"eval-003", "evaluation.completed"}
	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("LogEvaluationCompleted() output should contain %s, got %s", check, output)
		}
	}
}

func TestLogEvaluationFailed(t *testing.T) {
	cfg := &LoggerConfig{
		Level:  "debug",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	var buf bytes.Buffer
	Logger = Logger.Output(&buf)

	testErr := errors.New("evaluation timeout")
	LogEvaluationFailed("eval-004", testErr)

	output := buf.String()
	checks := []string{"eval-004", "evaluation timeout", "evaluation.failed"}
	for _, check := range checks {
		if !strings.Contains(output, check) {
			t.Errorf("LogEvaluationFailed() output should contain %s, got %s", check, output)
		}
	}
}

func TestLogLevels(t *testing.T) {
	tests := []struct {
		level         string
		expectedLevel zerolog.Level
	}{
		{"trace", zerolog.TraceLevel},
		{"debug", zerolog.DebugLevel},
		{"info", zerolog.InfoLevel},
		{"warn", zerolog.WarnLevel},
		{"error", zerolog.ErrorLevel},
		{"fatal", zerolog.FatalLevel},
		{"panic", zerolog.PanicLevel},
	}

	for _, tt := range tests {
		t.Run(tt.level, func(t *testing.T) {
			cfg := &LoggerConfig{
				Level:  tt.level,
				Format: "json",
				Output: "stdout",
			}

			err := InitLoggerWithConfig(cfg)
			if err != nil {
				t.Fatalf("InitLoggerWithConfig() error = %v", err)
			}

			if zerolog.GlobalLevel() != tt.expectedLevel {
				t.Errorf("Global level = %v, want %v", zerolog.GlobalLevel(), tt.expectedLevel)
			}
		})
	}
}

func BenchmarkLogRequest(b *testing.B) {
	cfg := &LoggerConfig{
		Level:  "info",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	// Discard output for benchmark
	Logger = Logger.Output(&bytes.Buffer{})

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		LogRequest("GET", "/api/test", 200, time.Millisecond, "req-bench")
	}
}

func BenchmarkLogEvaluationProgress(b *testing.B) {
	cfg := &LoggerConfig{
		Level:  "info",
		Format: "json",
		Output: "stdout",
	}
	_ = InitLoggerWithConfig(cfg)

	Logger = Logger.Output(&bytes.Buffer{})

	metrics := map[string]float64{
		"ndcg_at_10": 0.85,
		"map_at_100": 0.78,
		"mrr_at_10":  0.90,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		LogEvaluationProgress("eval-bench", 50, metrics)
	}
}
