package config

import (
	"os"
	"path/filepath"
	"testing"
)

func setupTestConfig(t *testing.T, content string) string {
	t.Helper()
	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "config.toml")
	if err := os.WriteFile(configPath, []byte(content), 0644); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}
	os.Setenv("METIVTA_CONFIG_PATH", configPath)
	t.Cleanup(func() {
		os.Unsetenv("METIVTA_CONFIG_PATH")
	})
	return configPath
}

func TestLoad(t *testing.T) {
	configContent := `
[meta]
version = "1.0.0"
environment = "test"

[server]
host = "localhost"
port = 9000
gateway_port = 8000
timeout_seconds = 30

[security]
enabled = true
secret_key = "test-secret"

[security.jwt]
enabled = true
algorithm = "RS256"
access_token_ttl_minutes = 60

[security.mtls]
enabled = false

[database]
provider = "postgresql"
pool_size = 5

[database.postgresql]
host = "localhost"
port = 5432
database = "test_db"
user = "test_user"
password = "test_pass"
ssl_mode = "disable"
`
	setupTestConfig(t, configContent)

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	// Test meta config
	if cfg.Meta.Version != "1.0.0" {
		t.Errorf("Meta.Version = %v, want 1.0.0", cfg.Meta.Version)
	}

	// Test server config
	if cfg.Server.Host != "localhost" {
		t.Errorf("Server.Host = %v, want localhost", cfg.Server.Host)
	}
	if cfg.Server.Port != 9000 {
		t.Errorf("Server.Port = %v, want 9000", cfg.Server.Port)
	}

	// Test security config
	if !cfg.Security.Enabled {
		t.Error("Security.Enabled = false, want true")
	}
	if cfg.Security.JWT.Algorithm != "RS256" {
		t.Errorf("Security.JWT.Algorithm = %v, want RS256", cfg.Security.JWT.Algorithm)
	}

	// Test database config
	if cfg.Database.PostgreSQL.Host != "localhost" {
		t.Errorf("Database.PostgreSQL.Host = %v, want localhost", cfg.Database.PostgreSQL.Host)
	}
	if cfg.Database.PostgreSQL.Port != 5432 {
		t.Errorf("Database.PostgreSQL.Port = %v, want 5432", cfg.Database.PostgreSQL.Port)
	}
}

func TestLoadNonExistent(t *testing.T) {
	os.Setenv("METIVTA_CONFIG_PATH", "/nonexistent/path/config.toml")
	defer os.Unsetenv("METIVTA_CONFIG_PATH")

	_, err := Load()
	if err == nil {
		t.Error("Load() expected error for nonexistent file, got nil")
	}
}

func TestEnvironmentVariableOverride(t *testing.T) {
	configContent := `
[server]
host = "localhost"
port = 8000
`
	setupTestConfig(t, configContent)

	// Set environment variable override
	os.Setenv("METIVTA_SERVER_PORT", "9999")
	defer os.Unsetenv("METIVTA_SERVER_PORT")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	// Environment variable should override config file
	if cfg.Server.Port != 9999 {
		t.Errorf("Server.Port = %v, want 9999 (from env override)", cfg.Server.Port)
	}
}

func TestMustLoadPanics(t *testing.T) {
	os.Setenv("METIVTA_CONFIG_PATH", "/nonexistent/config.toml")
	defer os.Unsetenv("METIVTA_CONFIG_PATH")

	defer func() {
		if r := recover(); r == nil {
			t.Error("MustLoad() should panic for invalid config path")
		}
	}()

	MustLoad()
}

func TestPostgreSQLConfigDSN(t *testing.T) {
	tests := []struct {
		name     string
		config   PostgreSQLConfig
		expected string
	}{
		{
			name: "basic connection",
			config: PostgreSQLConfig{
				Host:     "localhost",
				Port:     5432,
				Database: "testdb",
				User:     "testuser",
				Password: "testpass",
				SSLMode:  "disable",
			},
			expected: "postgres://testuser:testpass@localhost:5432/testdb?sslmode=disable",
		},
		{
			name: "with ssl require",
			config: PostgreSQLConfig{
				Host:     "db.example.com",
				Port:     5432,
				Database: "proddb",
				User:     "produser",
				Password: "prodpass",
				SSLMode:  "require",
			},
			expected: "postgres://produser:prodpass@db.example.com:5432/proddb?sslmode=require",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			dsn := tt.config.DSN()
			if dsn != tt.expected {
				t.Errorf("DSN() = %v, want %v", dsn, tt.expected)
			}
		})
	}
}

func TestRedisConfigURL(t *testing.T) {
	tests := []struct {
		name     string
		config   RedisConfig
		expected string
	}{
		{
			name: "without password",
			config: RedisConfig{
				Host:     "localhost",
				Port:     6379,
				DB:       0,
				Password: "",
			},
			expected: "redis://localhost:6379/0",
		},
		{
			name: "with password",
			config: RedisConfig{
				Host:     "redis.example.com",
				Port:     6379,
				DB:       1,
				Password: "secret",
			},
			expected: "redis://:secret@redis.example.com:6379/1",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			url := tt.config.URL()
			if url != tt.expected {
				t.Errorf("URL() = %v, want %v", url, tt.expected)
			}
		})
	}
}

func TestIsProduction(t *testing.T) {
	tests := []struct {
		name        string
		environment Environment
		expected    bool
	}{
		{
			name:        "production",
			environment: EnvProduction,
			expected:    true,
		},
		{
			name:        "development",
			environment: EnvDevelopment,
			expected:    false,
		},
		{
			name:        "staging",
			environment: EnvStaging,
			expected:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := &Config{
				Meta: MetaConfig{
					Environment: tt.environment,
				},
			}
			if got := cfg.IsProduction(); got != tt.expected {
				t.Errorf("IsProduction() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestIsDevelopment(t *testing.T) {
	tests := []struct {
		name        string
		environment Environment
		expected    bool
	}{
		{
			name:        "production",
			environment: EnvProduction,
			expected:    false,
		},
		{
			name:        "development",
			environment: EnvDevelopment,
			expected:    true,
		},
		{
			name:        "staging",
			environment: EnvStaging,
			expected:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := &Config{
				Meta: MetaConfig{
					Environment: tt.environment,
				},
			}
			if got := cfg.IsDevelopment(); got != tt.expected {
				t.Errorf("IsDevelopment() = %v, want %v", got, tt.expected)
			}
		})
	}
}

func TestTimeout(t *testing.T) {
	cfg := &Config{
		Server: ServerConfig{
			TimeoutSeconds: 30,
		},
	}

	timeout := cfg.Timeout()
	if timeout.Seconds() != 30 {
		t.Errorf("Timeout() = %v, want 30s", timeout)
	}
}

func TestGet(t *testing.T) {
	configContent := `
[server]
host = "testhost"
port = 8080
`
	setupTestConfig(t, configContent)

	// Clear any cached config
	configMutex.Lock()
	globalConfig = nil
	configMutex.Unlock()

	cfg := Get()
	if cfg == nil {
		t.Fatal("Get() returned nil")
	}

	if cfg.Server.Host != "testhost" {
		t.Errorf("Get().Server.Host = %v, want testhost", cfg.Server.Host)
	}
}

func TestGetReturnsDefaults(t *testing.T) {
	os.Setenv("METIVTA_CONFIG_PATH", "/nonexistent/config.toml")
	defer os.Unsetenv("METIVTA_CONFIG_PATH")

	// Clear any cached config
	configMutex.Lock()
	globalConfig = nil
	configMutex.Unlock()

	cfg := Get()
	if cfg == nil {
		t.Fatal("Get() returned nil")
	}

	// Should return defaults
	if cfg.Meta.Version != "2.0.0" {
		t.Errorf("Get().Meta.Version = %v, want 2.0.0 (default)", cfg.Meta.Version)
	}
}
