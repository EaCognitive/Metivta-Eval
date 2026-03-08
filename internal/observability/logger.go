// Package observability provides logging, tracing, and metrics for MetivitaEval.
package observability

import (
	"context"
	"io"
	"os"
	"path/filepath"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"gopkg.in/natefinch/lumberjack.v2"

	"github.com/metivta/metivta-eval/internal/config"
)

// Logger is the global structured logger.
var Logger zerolog.Logger

// ContextKey is a custom type for context keys to avoid collisions.
type ContextKey string

// Context key constants.
const (
	TraceIDKey ContextKey = "trace_id"
)

// LoggerConfig holds logger configuration.
type LoggerConfig struct {
	Level      string
	Format     string // json | text
	Output     string // stdout | file | both
	FilePath   string
	MaxSizeMB  int
	MaxBackups int
	MaxAgeDays int
	Compress   bool
}

// InitLogger initializes the global logger.
func InitLogger(cfg *config.Config) error {
	logCfg := &LoggerConfig{
		Level:      cfg.Observability.Logging.Level,
		Format:     cfg.Observability.Logging.Format,
		Output:     cfg.Observability.Logging.Output,
		FilePath:   cfg.Observability.Logging.FilePath,
		MaxSizeMB:  cfg.Observability.Logging.MaxSizeMB,
		MaxBackups: cfg.Observability.Logging.MaxBackups,
		MaxAgeDays: cfg.Observability.Logging.MaxAgeDays,
		Compress:   cfg.Observability.Logging.Compress,
	}

	return InitLoggerWithConfig(logCfg)
}

// InitLoggerWithConfig initializes the logger with explicit config.
func InitLoggerWithConfig(cfg *LoggerConfig) error {
	// Parse level
	level, err := zerolog.ParseLevel(cfg.Level)
	if err != nil {
		level = zerolog.InfoLevel
	}
	zerolog.SetGlobalLevel(level)

	// Configure output writers
	var writers []io.Writer

	// Console/stdout output
	if cfg.Output == "stdout" || cfg.Output == "both" {
		if cfg.Format == "text" {
			// Human-readable output for development
			writers = append(writers, zerolog.ConsoleWriter{
				Out:        os.Stdout,
				TimeFormat: time.RFC3339,
			})
		} else {
			writers = append(writers, os.Stdout)
		}
	}

	// File output
	if cfg.Output == "file" || cfg.Output == "both" {
		// Ensure directory exists
		dir := filepath.Dir(cfg.FilePath)
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}

		// Use lumberjack for rotation
		fileWriter := &lumberjack.Logger{
			Filename:   cfg.FilePath,
			MaxSize:    cfg.MaxSizeMB,
			MaxBackups: cfg.MaxBackups,
			MaxAge:     cfg.MaxAgeDays,
			Compress:   cfg.Compress,
		}
		writers = append(writers, fileWriter)
	}

	// Create multi-writer
	var output io.Writer
	switch len(writers) {
	case 0:
		output = os.Stdout
	case 1:
		output = writers[0]
	default:
		output = zerolog.MultiLevelWriter(writers...)
	}

	// Create logger
	Logger = zerolog.New(output).
		With().
		Timestamp().
		Caller().
		Str("service", "metivta-eval").
		Logger()

	// Set global logger
	log.Logger = Logger

	return nil
}

// WithContext returns a logger with context fields.
func WithContext(ctx context.Context) zerolog.Logger {
	// Extract trace ID if available
	if traceID := ctx.Value(TraceIDKey); traceID != nil {
		traceIDValue, ok := traceID.(string)
		if ok && traceIDValue != "" {
			return Logger.With().Str("trace_id", traceIDValue).Logger()
		}
	}
	return Logger
}

// WithRequestID returns a logger with request ID.
func WithRequestID(requestID string) zerolog.Logger {
	return Logger.With().Str("request_id", requestID).Logger()
}

// WithUserID returns a logger with user ID.
func WithUserID(userID string) zerolog.Logger {
	return Logger.With().Str("user_id", userID).Logger()
}

// WithEvaluationID returns a logger with evaluation ID.
func WithEvaluationID(evalID string) zerolog.Logger {
	return Logger.With().Str("evaluation_id", evalID).Logger()
}

// LogRequest logs an HTTP request.
func LogRequest(method, path string, statusCode int, duration time.Duration, requestID string) {
	Logger.Info().
		Str("request_id", requestID).
		Str("method", method).
		Str("path", path).
		Int("status", statusCode).
		Dur("duration", duration).
		Msg("http.request")
}

// LogError logs an error with context.
func LogError(err error, msg string, fields map[string]any) {
	event := Logger.Error().Err(err)
	for k, v := range fields {
		event = event.Interface(k, v)
	}
	event.Msg(msg)
}

// LogEvaluationStarted logs evaluation start.
func LogEvaluationStarted(evalID, mode, dataset string) {
	Logger.Info().
		Str("evaluation_id", evalID).
		Str("mode", mode).
		Str("dataset", dataset).
		Msg("evaluation.started")
}

// LogEvaluationProgress logs evaluation progress.
func LogEvaluationProgress(evalID string, progress int, metrics map[string]float64) {
	event := Logger.Info().
		Str("evaluation_id", evalID).
		Int("progress", progress)

	for k, v := range metrics {
		event = event.Float64(k, v)
	}

	event.Msg("evaluation.progress")
}

// LogEvaluationCompleted logs evaluation completion.
func LogEvaluationCompleted(evalID string, duration time.Duration, overallScore float64) {
	Logger.Info().
		Str("evaluation_id", evalID).
		Dur("duration", duration).
		Float64("overall_score", overallScore).
		Msg("evaluation.completed")
}

// LogEvaluationFailed logs evaluation failure.
func LogEvaluationFailed(evalID string, err error) {
	Logger.Error().
		Str("evaluation_id", evalID).
		Err(err).
		Msg("evaluation.failed")
}
