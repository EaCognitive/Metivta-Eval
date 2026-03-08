// Package config provides centralized configuration management for MetivitaEval.
//
// It reads from config.toml as the single source of truth, with environment
// variable overrides following the pattern: METIVTA_SECTION_KEY
//
// Usage:
//
//	cfg, err := config.Load()
//	if err != nil {
//	    log.Fatal(err)
//	}
//	port := cfg.Server.Port
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/spf13/viper"
)

// Environment represents the deployment environment.
type Environment string

const (
	EnvDevelopment Environment = "development"
	EnvStaging     Environment = "staging"
	EnvProduction  Environment = "production"
)

// Config is the root configuration structure.
type Config struct {
	Meta          MetaConfig          `mapstructure:"meta"`
	Server        ServerConfig        `mapstructure:"server"`
	Security      SecurityConfig      `mapstructure:"security"`
	Database      DatabaseConfig      `mapstructure:"database"`
	Cache         CacheConfig         `mapstructure:"cache"`
	Models        ModelsConfig        `mapstructure:"models"`
	Evaluation    EvaluationConfig    `mapstructure:"evaluation"`
	Dataset       DatasetConfig       `mapstructure:"dataset"`
	Storage       StorageConfig       `mapstructure:"storage"`
	Secrets       SecretsConfig       `mapstructure:"secrets"`
	Observability ObservabilityConfig `mapstructure:"observability"`
	Worker        WorkerConfig        `mapstructure:"worker"`
	Notifications NotificationsConfig `mapstructure:"notifications"`
	Features      FeaturesConfig      `mapstructure:"features"`
}

// MetaConfig contains metadata about the configuration.
type MetaConfig struct {
	Version     string      `mapstructure:"version"`
	Environment Environment `mapstructure:"environment"`
}

// CORSConfig defines CORS settings.
type CORSConfig struct {
	AllowedOrigins []string `mapstructure:"allowed_origins"`
	AllowedMethods []string `mapstructure:"allowed_methods"`
	AllowedHeaders []string `mapstructure:"allowed_headers"`
	MaxAgeSeconds  int      `mapstructure:"max_age_seconds"`
}

// ServerConfig contains HTTP server settings.
type ServerConfig struct {
	Host                    string     `mapstructure:"host"`
	Port                    int        `mapstructure:"port"`
	GatewayPort             int        `mapstructure:"gateway_port"`
	FastAPIPort             int        `mapstructure:"fastapi_port"`
	Workers                 int        `mapstructure:"workers"`
	TimeoutSeconds          int        `mapstructure:"timeout_seconds"`
	GracefulShutdownSeconds int        `mapstructure:"graceful_shutdown_seconds"`
	CORS                    CORSConfig `mapstructure:"cors"`
}

// MTLSConfig contains mTLS settings.
type MTLSConfig struct {
	Enabled            bool   `mapstructure:"enabled"`
	CACertPath         string `mapstructure:"ca_cert_path"`
	ServerCertPath     string `mapstructure:"server_cert_path"`
	ServerKeyPath      string `mapstructure:"server_key_path"`
	ClientCertRequired bool   `mapstructure:"client_cert_required"`
	MinTLSVersion      string `mapstructure:"min_tls_version"`
}

// JWTConfig contains JWT settings.
type JWTConfig struct {
	Enabled               bool   `mapstructure:"enabled"`
	Algorithm             string `mapstructure:"algorithm"`
	Issuer                string `mapstructure:"issuer"`
	Audience              string `mapstructure:"audience"`
	AccessTokenTTLMinutes int    `mapstructure:"access_token_ttl_minutes"`
	RefreshTokenTTLDays   int    `mapstructure:"refresh_token_ttl_days"`
	PublicKeyPath         string `mapstructure:"public_key_path"`
	PrivateKeyPath        string `mapstructure:"private_key_path"`
}

// RateLimitingConfig contains rate limiting settings.
type RateLimitingConfig struct {
	Enabled           bool   `mapstructure:"enabled"`
	RequestsPerMinute int    `mapstructure:"requests_per_minute"`
	RequestsPerHour   int    `mapstructure:"requests_per_hour"`
	BurstSize         int    `mapstructure:"burst_size"`
	Storage           string `mapstructure:"storage"` // memory | redis
}

// APIKeysConfig contains API key settings.
type APIKeysConfig struct {
	Prefix        string `mapstructure:"prefix"`
	Length        int    `mapstructure:"length"`
	HashAlgorithm string `mapstructure:"hash_algorithm"`
	RotationDays  int    `mapstructure:"rotation_days"`
}

// SecurityConfig contains security settings.
type SecurityConfig struct {
	Enabled      bool               `mapstructure:"enabled"`
	SecretKey    string             `mapstructure:"secret_key"`
	MTLS         MTLSConfig         `mapstructure:"mtls"`
	JWT          JWTConfig          `mapstructure:"jwt"`
	RateLimiting RateLimitingConfig `mapstructure:"rate_limiting"`
	APIKeys      APIKeysConfig      `mapstructure:"api_keys"`
}

// PostgreSQLConfig contains PostgreSQL settings.
type PostgreSQLConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Database string `mapstructure:"database"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	SSLMode  string `mapstructure:"ssl_mode"`
}

// DSN returns the PostgreSQL connection string.
func (p *PostgreSQLConfig) DSN() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=%s",
		p.User, p.Password, p.Host, p.Port, p.Database, p.SSLMode,
	)
}

// SupabaseConfig contains Supabase settings.
type SupabaseConfig struct {
	URL            string `mapstructure:"url"`
	AnonKey        string `mapstructure:"anon_key"`
	ServiceRoleKey string `mapstructure:"service_role_key"`
}

// MigrationsConfig contains migration settings.
type MigrationsConfig struct {
	AutoMigrate bool   `mapstructure:"auto_migrate"`
	Directory   string `mapstructure:"directory"`
}

// DatabaseConfig contains database settings.
type DatabaseConfig struct {
	Provider           string           `mapstructure:"provider"` // postgresql | supabase | sqlite
	PoolSize           int              `mapstructure:"pool_size"`
	MaxOverflow        int              `mapstructure:"max_overflow"`
	PoolTimeoutSeconds int              `mapstructure:"pool_timeout_seconds"`
	EchoSQL            bool             `mapstructure:"echo_sql"`
	PostgreSQL         PostgreSQLConfig `mapstructure:"postgresql"`
	Supabase           SupabaseConfig   `mapstructure:"supabase"`
	Migrations         MigrationsConfig `mapstructure:"migrations"`
}

// RedisConfig contains Redis settings.
type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	DB       int    `mapstructure:"db"`
	Password string `mapstructure:"password"`
	PoolSize int    `mapstructure:"pool_size"`
	SSL      bool   `mapstructure:"ssl"`
}

// URL returns the Redis connection URL.
func (r *RedisConfig) URL() string {
	auth := ""
	if r.Password != "" {
		auth = ":" + r.Password + "@"
	}
	return fmt.Sprintf("redis://%s%s:%d/%d", auth, r.Host, r.Port, r.DB)
}

// CacheConfig contains cache settings.
type CacheConfig struct {
	Provider          string      `mapstructure:"provider"` // memory | redis | memcached
	DefaultTTLSeconds int         `mapstructure:"default_ttl_seconds"`
	Redis             RedisConfig `mapstructure:"redis"`
}

// AnthropicConfig contains Anthropic API settings.
type AnthropicConfig struct {
	APIKey      string  `mapstructure:"api_key"`
	MaxTokens   int     `mapstructure:"max_tokens"`
	Temperature float64 `mapstructure:"temperature"`
}

// OpenAIConfig contains OpenAI API settings.
type OpenAIConfig struct {
	APIKey       string `mapstructure:"api_key"`
	Organization string `mapstructure:"organization"`
}

// LangSmithConfig contains LangSmith settings.
type LangSmithConfig struct {
	APIKey         string `mapstructure:"api_key"`
	Project        string `mapstructure:"project"`
	TracingEnabled bool   `mapstructure:"tracing_enabled"`
}

// ModelsConfig contains AI model settings.
type ModelsConfig struct {
	Primary   string          `mapstructure:"primary"`
	Fast      string          `mapstructure:"fast"`
	Embedding string          `mapstructure:"embedding"`
	Anthropic AnthropicConfig `mapstructure:"anthropic"`
	OpenAI    OpenAIConfig    `mapstructure:"openai"`
	LangSmith LangSmithConfig `mapstructure:"langsmith"`
}

// DAATWeightsConfig contains DAAT scoring weights.
type DAATWeightsConfig struct {
	DAI float64 `mapstructure:"dai"`
	MLA float64 `mapstructure:"mla"`
}

// DAATConfig contains DAAT evaluation settings.
type DAATConfig struct {
	Enabled bool              `mapstructure:"enabled"`
	Weights DAATWeightsConfig `mapstructure:"weights"`
}

// MTEBConfig contains MTEB evaluation settings.
type MTEBConfig struct {
	Enabled   bool     `mapstructure:"enabled"`
	BatchSize int      `mapstructure:"batch_size"`
	Metrics   []string `mapstructure:"metrics"`
}

// WebValidatorConfig contains web validator settings.
type WebValidatorConfig struct {
	Enabled           bool   `mapstructure:"enabled"`
	TimeoutMS         int    `mapstructure:"timeout_ms"`
	MinKeywordMatches int    `mapstructure:"min_keyword_matches"`
	Concurrency       int    `mapstructure:"concurrency"`
	CacheEnabled      bool   `mapstructure:"cache_enabled"`
	BrowserlessToken  string `mapstructure:"browserless_token"`
}

// EvaluationConfig contains evaluation settings.
type EvaluationConfig struct {
	Target                   string             `mapstructure:"target"`
	EndpointURL              string             `mapstructure:"endpoint_url"`
	DevMode                  bool               `mapstructure:"dev_mode"`
	AsyncEnabled             bool               `mapstructure:"async_enabled"`
	MaxConcurrentEvaluations int                `mapstructure:"max_concurrent_evaluations"`
	DAAT                     DAATConfig         `mapstructure:"daat"`
	MTEB                     MTEBConfig         `mapstructure:"mteb"`
	WebValidator             WebValidatorConfig `mapstructure:"web_validator"`
}

// DatasetFilesConfig contains dataset file paths.
type DatasetFilesConfig struct {
	Questions      string `mapstructure:"questions"`
	QuestionsOnly  string `mapstructure:"questions_only"`
	Holdback       string `mapstructure:"holdback"`
	FormatRubric   string `mapstructure:"format_rubric"`
	MaturityRubric string `mapstructure:"maturity_rubric"`
}

// MTEBDatasetConfig contains MTEB dataset paths.
type MTEBDatasetConfig struct {
	Corpus  string `mapstructure:"corpus"`
	Queries string `mapstructure:"queries"`
	Qrels   string `mapstructure:"qrels"`
}

// DatasetConfig contains dataset settings.
type DatasetConfig struct {
	Name      string             `mapstructure:"name"`
	Version   string             `mapstructure:"version"`
	LocalPath string             `mapstructure:"local_path"`
	Files     DatasetFilesConfig `mapstructure:"files"`
	MTEB      MTEBDatasetConfig  `mapstructure:"mteb"`
}

// S3Config contains S3-compatible storage settings.
type S3Config struct {
	Bucket    string `mapstructure:"bucket"`
	Region    string `mapstructure:"region"`
	Endpoint  string `mapstructure:"endpoint"`
	AccessKey string `mapstructure:"access_key"`
	SecretKey string `mapstructure:"secret_key"`
	CDNURL    string `mapstructure:"cdn_url"`
}

// StorageConfig contains storage settings.
type StorageConfig struct {
	Provider  string   `mapstructure:"provider"` // local | s3 | digitalocean_spaces
	LocalPath string   `mapstructure:"local_path"`
	S3        S3Config `mapstructure:"s3"`
}

// VaultConfig contains HashiCorp Vault settings.
type VaultConfig struct {
	Address    string `mapstructure:"address"`
	Token      string `mapstructure:"token"`
	MountPath  string `mapstructure:"mount_path"`
	SecretPath string `mapstructure:"secret_path"`
}

// OnePasswordConfig contains 1Password settings.
type OnePasswordConfig struct {
	Vault               string `mapstructure:"vault"`
	ServiceAccountToken string `mapstructure:"service_account_token"`
}

// SecretsConfig contains secrets management settings.
type SecretsConfig struct {
	Provider    string            `mapstructure:"provider"` // env | vault | onepassword
	Vault       VaultConfig       `mapstructure:"vault"`
	OnePassword OnePasswordConfig `mapstructure:"onepassword"`
}

// LoggingConfig contains logging settings.
type LoggingConfig struct {
	Level      string `mapstructure:"level"`  // debug | info | warn | error
	Format     string `mapstructure:"format"` // json | text
	Output     string `mapstructure:"output"` // stdout | file | both
	FilePath   string `mapstructure:"file_path"`
	MaxSizeMB  int    `mapstructure:"max_size_mb"`
	MaxBackups int    `mapstructure:"max_backups"`
	MaxAgeDays int    `mapstructure:"max_age_days"`
	Compress   bool   `mapstructure:"compress"`
}

// TracingConfig contains tracing settings.
type TracingConfig struct {
	Enabled    bool    `mapstructure:"enabled"`
	Provider   string  `mapstructure:"provider"` // otlp | jaeger | zipkin
	Endpoint   string  `mapstructure:"endpoint"`
	SampleRate float64 `mapstructure:"sample_rate"`
}

// MetricsConfig contains metrics settings.
type MetricsConfig struct {
	Enabled  bool   `mapstructure:"enabled"`
	Provider string `mapstructure:"provider"`
	Port     int    `mapstructure:"port"`
	Path     string `mapstructure:"path"`
}

// SentryConfig contains Sentry settings.
type SentryConfig struct {
	Enabled          bool    `mapstructure:"enabled"`
	DSN              string  `mapstructure:"dsn"`
	Environment      string  `mapstructure:"environment"`
	TracesSampleRate float64 `mapstructure:"traces_sample_rate"`
}

// ObservabilityConfig contains observability settings.
type ObservabilityConfig struct {
	ServiceName string        `mapstructure:"service_name"`
	Logging     LoggingConfig `mapstructure:"logging"`
	Tracing     TracingConfig `mapstructure:"tracing"`
	Metrics     MetricsConfig `mapstructure:"metrics"`
	Sentry      SentryConfig  `mapstructure:"sentry"`
}

// WorkerQueuesConfig contains worker queue names.
type WorkerQueuesConfig struct {
	Default       string `mapstructure:"default"`
	Evaluation    string `mapstructure:"evaluation"`
	Notifications string `mapstructure:"notifications"`
}

// WorkerConfig contains worker settings.
type WorkerConfig struct {
	Enabled                bool               `mapstructure:"enabled"`
	Broker                 string             `mapstructure:"broker"`
	ResultBackend          string             `mapstructure:"result_backend"`
	Concurrency            int                `mapstructure:"concurrency"`
	PrefetchMultiplier     int                `mapstructure:"prefetch_multiplier"`
	TaskAcksLate           bool               `mapstructure:"task_acks_late"`
	TaskRejectOnWorkerLost bool               `mapstructure:"task_reject_on_worker_lost"`
	Queues                 WorkerQueuesConfig `mapstructure:"queues"`
}

// EmailConfig contains email settings.
type EmailConfig struct {
	Enabled      bool   `mapstructure:"enabled"`
	SMTPHost     string `mapstructure:"smtp_host"`
	SMTPPort     int    `mapstructure:"smtp_port"`
	SMTPUser     string `mapstructure:"smtp_user"`
	SMTPPassword string `mapstructure:"smtp_password"`
	FromAddress  string `mapstructure:"from_address"`
}

// SlackConfig contains Slack settings.
type SlackConfig struct {
	Enabled    bool   `mapstructure:"enabled"`
	WebhookURL string `mapstructure:"webhook_url"`
}

// NotificationsConfig contains notification settings.
type NotificationsConfig struct {
	Enabled bool        `mapstructure:"enabled"`
	Email   EmailConfig `mapstructure:"email"`
	Slack   SlackConfig `mapstructure:"slack"`
}

// FeaturesConfig contains feature flags.
type FeaturesConfig struct {
	MTEBEvaluation    bool `mapstructure:"mteb_evaluation"`
	AsyncEvaluation   bool `mapstructure:"async_evaluation"`
	WebsocketUpdates  bool `mapstructure:"websocket_updates"`
	GraphQLAPI        bool `mapstructure:"graphql_api"`
	LegacyFlaskRoutes bool `mapstructure:"legacy_flask_routes"`
	NewUserManagement bool `mapstructure:"new_user_management"`
}

// IsProduction returns true if running in production environment.
func (c *Config) IsProduction() bool {
	return c.Meta.Environment == EnvProduction
}

// IsDevelopment returns true if running in development environment.
func (c *Config) IsDevelopment() bool {
	return c.Meta.Environment == EnvDevelopment
}

// Timeout returns the server timeout as a Duration.
func (c *Config) Timeout() time.Duration {
	return time.Duration(c.Server.TimeoutSeconds) * time.Second
}

// Global config singleton
var (
	globalConfig *Config
	configMutex  sync.RWMutex
)

// findConfigFile searches for config.toml.
func findConfigFile() (string, error) {
	// Check explicit env var first
	if envPath := os.Getenv("METIVTA_CONFIG_PATH"); envPath != "" {
		if _, err := os.Stat(envPath); err == nil {
			return envPath, nil
		}
		return "", fmt.Errorf("config file not found at METIVTA_CONFIG_PATH: %s", envPath)
	}

	// Search from current directory up
	cwd, err := os.Getwd()
	if err != nil {
		return "", err
	}

	dir := cwd
	for {
		configPath := filepath.Join(dir, "config.toml")
		if _, err := os.Stat(configPath); err == nil {
			return configPath, nil
		}

		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}

	return "", fmt.Errorf("config.toml not found")
}

// Load loads the configuration from config.toml with environment overrides.
func Load() (*Config, error) {
	configPath, err := findConfigFile()
	if err != nil {
		return nil, err
	}

	v := viper.New()
	v.SetConfigFile(configPath)
	v.SetConfigType("toml")

	// Environment variable overrides
	v.SetEnvPrefix("METIVTA")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("failed to read config: %w", err)
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	return &cfg, nil
}

// Get returns the global configuration singleton.
func Get() *Config {
	configMutex.RLock()
	if globalConfig != nil {
		defer configMutex.RUnlock()
		return globalConfig
	}
	configMutex.RUnlock()

	configMutex.Lock()
	defer configMutex.Unlock()

	if globalConfig == nil {
		cfg, err := Load()
		if err != nil {
			// Return defaults if config not found
			return &Config{
				Meta: MetaConfig{
					Version:     "2.0.0",
					Environment: EnvDevelopment,
				},
				Server: ServerConfig{
					Host:        "0.0.0.0",
					Port:        8080,
					GatewayPort: 8000,
				},
			}
		}
		globalConfig = cfg
	}

	return globalConfig
}

// MustLoad loads config and panics on error.
func MustLoad() *Config {
	cfg, err := Load()
	if err != nil {
		panic(fmt.Sprintf("failed to load config: %v", err))
	}
	return cfg
}

// Reload reloads the configuration.
func Reload() (*Config, error) {
	cfg, err := Load()
	if err != nil {
		return nil, err
	}

	configMutex.Lock()
	globalConfig = cfg
	configMutex.Unlock()

	return cfg, nil
}
