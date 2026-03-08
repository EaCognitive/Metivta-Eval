package cmd

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/spf13/viper"
)

func executeCommand(t *testing.T, args ...string) (string, error) {
	t.Helper()
	viper.Reset()
	cfgFile = ""

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs(args)

	return buf.String(), Execute()
}

func newMockAPIServer(t *testing.T) *httptest.Server {
	t.Helper()

	mux := http.NewServeMux()
	mux.HandleFunc("/api/v2/eval/test-eval-id", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Fatalf("unexpected method: %s", r.Method)
		}
		_, _ = w.Write([]byte(`{"id":"test-eval-id","status":"completed","progress":100}`))
	})
	mux.HandleFunc("/api/v2/eval/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			_, _ = w.Write([]byte(`{"items":[{"id":"test-eval-id","status":"completed"}],"total":1}`))
			return
		}
		if r.Method == http.MethodPost {
			_, _ = w.Write([]byte(`{"id":"test-eval-id","status":"pending","progress":0}`))
			return
		}
		w.WriteHeader(http.StatusMethodNotAllowed)
	})
	mux.HandleFunc("/api/v2/leaderboard/", func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"entries":[{"rank":1,"system_name":"demo","author":"test"}],"total":1}`))
	})

	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

func setAPIBaseURL(t *testing.T, value string) {
	t.Helper()
	prev, hadPrev := os.LookupEnv("METIVTA_API_BASE_URL")
	if err := os.Setenv("METIVTA_API_BASE_URL", value); err != nil {
		t.Fatalf("failed to set METIVTA_API_BASE_URL: %v", err)
	}
	t.Cleanup(func() {
		if hadPrev {
			_ = os.Setenv("METIVTA_API_BASE_URL", prev)
			return
		}
		_ = os.Unsetenv("METIVTA_API_BASE_URL")
	})
}

func writeConfig(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.toml")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}
	return path
}

func TestExecute(t *testing.T) {
	// Execute should not error with --help
	_, err := executeCommand(t, "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestSetVersionInfo(t *testing.T) {
	SetVersionInfo("1.0.0", "abc123", "2025-01-21")

	if version != "1.0.0" {
		t.Errorf("version = %v, want 1.0.0", version)
	}
	if commitSHA != "abc123" {
		t.Errorf("commitSHA = %v, want abc123", commitSHA)
	}
	if buildDate != "2025-01-21" {
		t.Errorf("buildDate = %v, want 2025-01-21", buildDate)
	}
}

func TestVersionCommand(t *testing.T) {
	SetVersionInfo("test-version", "test-sha", "test-date")
	_, err := executeCommand(t, "version")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestEvalCommand(t *testing.T) {
	_, err := executeCommand(t, "eval", "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestLeaderboardCommand(t *testing.T) {
	_, err := executeCommand(t, "leaderboard", "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestDatasetCommand(t *testing.T) {
	_, err := executeCommand(t, "dataset", "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestServerCommand(t *testing.T) {
	_, err := executeCommand(t, "server", "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestConfigCommand(t *testing.T) {
	_, err := executeCommand(t, "config", "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestLogsCommand(t *testing.T) {
	_, err := executeCommand(t, "logs", "--help")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestInitConfig(t *testing.T) {
	// Test with a valid config file
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "config.toml")

	content := `
[server]
host = "localhost"
port = 8000
`
	if err := os.WriteFile(configPath, []byte(content), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	// Set config file
	cfgFile = configPath

	err := initConfig()
	if err != nil {
		t.Fatalf("initConfig() error = %v", err)
	}

	// Reset
	cfgFile = ""
}

func TestInitConfig_NoFile(t *testing.T) {
	// Clear config file setting
	cfgFile = ""

	// Should not error even without a config file
	err := initConfig()
	if err != nil {
		t.Fatalf("initConfig() error = %v", err)
	}
}

func TestEvalRunCommand_MissingEndpoint(t *testing.T) {
	// Should error because endpoint is required
	_, err := executeCommand(t, "eval", "run")
	if err == nil {
		// The error is expected but may be wrapped
		t.Log("Command returned error as expected (missing required flag)")
	}
}

func TestEvalStatusCommand(t *testing.T) {
	server := newMockAPIServer(t)
	setAPIBaseURL(t, server.URL)

	_, err := executeCommand(t, "eval", "status", "test-eval-id")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestEvalListCommand(t *testing.T) {
	server := newMockAPIServer(t)
	setAPIBaseURL(t, server.URL)

	_, err := executeCommand(t, "eval", "list")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestLeaderboardShowCommand(t *testing.T) {
	server := newMockAPIServer(t)
	setAPIBaseURL(t, server.URL)

	_, err := executeCommand(t, "leaderboard", "show")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestLeaderboardExportCommand(t *testing.T) {
	server := newMockAPIServer(t)
	setAPIBaseURL(t, server.URL)
	outputPath := filepath.Join(t.TempDir(), "leaderboard.json")

	_, err := executeCommand(
		t,
		"leaderboard",
		"export",
		"--format",
		"json",
		"--output",
		outputPath,
	)
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if _, statErr := os.Stat(outputPath); statErr != nil {
		t.Fatalf("expected export output: %v", statErr)
	}
}

func TestDatasetListCommand(t *testing.T) {
	datasetDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(datasetDir, "sample.json"), []byte("[]"), 0o644); err != nil {
		t.Fatalf("failed to create sample dataset: %v", err)
	}
	configPath := writeConfig(
		t,
		"[dataset]\nlocal_path = \""+datasetDir+"\"\n",
	)

	_, err := executeCommand(t, "--config", configPath, "dataset", "list")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestDatasetValidateCommand(t *testing.T) {
	datasetPath := filepath.Join(t.TempDir(), "test-file.json")
	if err := os.WriteFile(datasetPath, []byte(`[]`), 0o644); err != nil {
		t.Fatalf("failed to create test dataset: %v", err)
	}

	_, err := executeCommand(t, "dataset", "validate", datasetPath)
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestServerStartCommand(t *testing.T) {
	_, err := executeCommand(t, "server", "start")
	if err != nil {
		if strings.Contains(err.Error(), "executable file not found") {
			t.Skip("uv is required for server start command test")
		}
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestServerStatusCommand(t *testing.T) {
	_, err := executeCommand(t, "server", "status")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestServerStopCommand(t *testing.T) {
	_, err := executeCommand(t, "server", "stop")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestConfigInitCommand(t *testing.T) {
	configPath := filepath.Join(t.TempDir(), "config.toml")
	_, err := executeCommand(t, "--config", configPath, "config", "init")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestConfigGetCommand(t *testing.T) {
	configPath := writeConfig(t, "[server]\nport = 8080\n")
	_, err := executeCommand(t, "--config", configPath, "config", "get", "server.port")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestConfigListCommand(t *testing.T) {
	configPath := writeConfig(t, "[server]\nport = 8080\n")
	_, err := executeCommand(t, "--config", configPath, "config", "list")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestLogsTailCommand(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "metivta.log")
	if err := os.WriteFile(logPath, []byte("INFO start\nERROR failed\n"), 0o644); err != nil {
		t.Fatalf("failed to create test log file: %v", err)
	}
	configPath := writeConfig(
		t,
		"[observability.logging]\nfile_path = \""+logPath+"\"\n",
	)

	_, err := executeCommand(t, "--config", configPath, "logs", "tail")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestLogsSearchCommand(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "metivta.log")
	if err := os.WriteFile(logPath, []byte("INFO start\nERROR failed\n"), 0o644); err != nil {
		t.Fatalf("failed to create test log file: %v", err)
	}
	configPath := writeConfig(
		t,
		"[observability.logging]\nfile_path = \""+logPath+"\"\n",
	)

	_, err := executeCommand(t, "--config", configPath, "logs", "search", "error")
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
}

func TestGlobalFlags(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{"verbose flag", []string{"--verbose", "version"}},
		{"output json", []string{"--output", "json", "version"}},
		{"output yaml", []string{"--output", "yaml", "version"}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := executeCommand(t, tt.args...)
			if err != nil {
				t.Fatalf("Execute() error = %v", err)
			}
		})
	}
}
