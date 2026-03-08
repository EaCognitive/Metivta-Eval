// Package cmd implements the MetivtaEval CLI commands.
package cmd

import (
	"bufio"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/metivta/metivta-eval/internal/tui"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

const (
	serverPIDFile = ".metivta-server.pid"
)

var (
	cfgFile string
	verbose bool
	output  string

	version   = "dev"
	commitSHA = "unknown"
	buildDate = "unknown"
)

var rootCmd = &cobra.Command{
	Use:   "metivta",
	Short: "MetivitaEval - Enterprise AI Benchmarking Platform",
	Long: `MetivitaEval is an enterprise-grade AI evaluation platform for Torah scholarship.

It provides comprehensive benchmarking tools including:
  - DAAT (Deterministic Attribution & Agentic Traceability) scoring
  - MTEB (Massive Text Embedding Benchmark) metrics
  - Multi-tier evaluation pipeline
  - Real-time leaderboard`,
	SilenceUsage:  true,
	SilenceErrors: true,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		return initConfig()
	},
}

func Execute() error {
	return rootCmd.Execute()
}

func SetVersionInfo(v, sha, date string) {
	version = v
	commitSHA = sha
	buildDate = date
}

func init() {
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file path")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "verbose output")
	rootCmd.PersistentFlags().StringVarP(&output, "output", "o", "table", "output format (table|json|yaml)")

	rootCmd.AddCommand(evalCmd)
	rootCmd.AddCommand(leaderboardCmd)
	rootCmd.AddCommand(datasetCmd)
	rootCmd.AddCommand(serverCmd)
	rootCmd.AddCommand(configCmd)
	rootCmd.AddCommand(logsCmd)
	rootCmd.AddCommand(versionCmd)
}

func initConfig() error {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			return err
		}

		viper.AddConfigPath(".")
		viper.AddConfigPath(filepath.Join(home, ".metivta"))
		viper.AddConfigPath(filepath.Join(home, ".config", "metivta"))
		viper.SetConfigName("config")
		viper.SetConfigType("toml")
	}

	viper.SetEnvPrefix("METIVTA")
	viper.AutomaticEnv()

	if err := viper.ReadInConfig(); err != nil {
		var notFound viper.ConfigFileNotFoundError
		if errors.As(err, &notFound) || errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return fmt.Errorf("error reading config: %w", err)
	}
	return nil
}

func apiBaseURL() string {
	if value := os.Getenv("METIVTA_API_BASE_URL"); value != "" {
		return strings.TrimSuffix(value, "/")
	}
	if value := viper.GetString("server.api_base_url"); value != "" {
		return strings.TrimSuffix(value, "/")
	}

	host := viper.GetString("server.host")
	if host == "" {
		host = "127.0.0.1"
	}
	port := viper.GetInt("server.fastapi_port")
	if port == 0 {
		port = 8001
	}
	return fmt.Sprintf("http://%s:%d", host, port)
}

func apiKey() string {
	if value := os.Getenv("METIVTA_API_KEY"); value != "" {
		return value
	}
	return viper.GetString("security.api_key")
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Show version information",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("MetivitaEval CLI\n")
		fmt.Printf("  Version:    %s\n", version)
		fmt.Printf("  Commit:     %s\n", commitSHA)
		fmt.Printf("  Built:      %s\n", buildDate)
	},
}

var evalCmd = &cobra.Command{
	Use:   "eval",
	Short: "Run and manage evaluations",
}
var evalRunCmd = &cobra.Command{
	Use:   "run",
	Short: "Start a new evaluation",
	RunE: func(cmd *cobra.Command, args []string) error {
		mode, _ := cmd.Flags().GetString("mode")
		endpoint, _ := cmd.Flags().GetString("endpoint")
		dataset, _ := cmd.Flags().GetString("dataset")
		asyncMode, _ := cmd.Flags().GetBool("async")
		systemName, _ := cmd.Flags().GetString("system-name")
		systemVersion, _ := cmd.Flags().GetString("system-version")

		if systemName == "" {
			systemName = "metivta-cli"
		}

		body := map[string]any{
			"system_name":    systemName,
			"system_version": systemVersion,
			"endpoint_url":   endpoint,
			"mode":           mode,
			"dataset_name":   dataset,
			"async_mode":     asyncMode,
		}

		data, statusCode, err := makeRequest(http.MethodPost, apiBaseURL()+"/api/v2/eval/", body)
		if err != nil {
			printErrorBody(data)
			return fmt.Errorf("failed to create evaluation: %w", err)
		}
		if verbose {
			fmt.Printf("status: %d\n", statusCode)
		}

		return renderValue(mustDecodeJSON(data))
	},
}

var evalStatusCmd = &cobra.Command{
	Use:   "status <eval-id>",
	Short: "Check evaluation status",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		evalID := args[0]
		url := fmt.Sprintf("%s/api/v2/eval/%s", apiBaseURL(), evalID)
		data, _, err := makeRequest(http.MethodGet, url, nil)
		if err != nil {
			printErrorBody(data)
			return fmt.Errorf("failed to fetch evaluation status: %w", err)
		}
		return renderValue(mustDecodeJSON(data))
	},
}

var evalListCmd = &cobra.Command{
	Use:   "list",
	Short: "List evaluations",
	RunE: func(cmd *cobra.Command, args []string) error {
		statusFilter, _ := cmd.Flags().GetString("status")
		limit, _ := cmd.Flags().GetInt("limit")
		modeFilter, _ := cmd.Flags().GetString("mode")

		query := []string{"page=1", fmt.Sprintf("page_size=%d", limit)}
		if statusFilter != "" {
			query = append(query, "status="+statusFilter)
		}
		if modeFilter != "" {
			query = append(query, "mode="+modeFilter)
		}

		url := fmt.Sprintf("%s/api/v2/eval/?%s", apiBaseURL(), strings.Join(query, "&"))
		data, _, err := makeRequest(http.MethodGet, url, nil)
		if err != nil {
			printErrorBody(data)
			return fmt.Errorf("failed to list evaluations: %w", err)
		}
		return renderValue(mustDecodeJSON(data))
	},
}

func init() {
	evalRunCmd.Flags().StringP("mode", "m", "daat", "evaluation mode (daat|mteb)")
	evalRunCmd.Flags().StringP("endpoint", "e", "", "endpoint URL to evaluate")
	evalRunCmd.Flags().StringP("dataset", "d", "default", "dataset to use")
	evalRunCmd.Flags().BoolP("async", "a", true, "run asynchronously")
	evalRunCmd.Flags().String("system-name", "", "system name")
	evalRunCmd.Flags().String("system-version", "", "system version")
	_ = evalRunCmd.MarkFlagRequired("endpoint")

	evalListCmd.Flags().StringP("status", "s", "", "filter by status")
	evalListCmd.Flags().StringP("mode", "m", "", "filter by mode")
	evalListCmd.Flags().IntP("limit", "l", 20, "max results to show")

	evalCmd.AddCommand(evalRunCmd)
	evalCmd.AddCommand(evalStatusCmd)
	evalCmd.AddCommand(evalListCmd)
}

var leaderboardCmd = &cobra.Command{
	Use:   "leaderboard",
	Short: "View and interact with the leaderboard",
	RunE: func(cmd *cobra.Command, args []string) error {
		mode, _ := cmd.Flags().GetString("mode")
		return tui.RunLeaderboardWithMode(mode)
	},
}

var leaderboardShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Show leaderboard without TUI",
	RunE: func(cmd *cobra.Command, args []string) error {
		mode, _ := cmd.Flags().GetString("mode")
		limit, _ := cmd.Flags().GetInt("limit")
		url := fmt.Sprintf("%s/api/v2/leaderboard/?mode=%s&page=1&page_size=%d", apiBaseURL(), mode, limit)
		data, _, err := makeRequest(http.MethodGet, url, nil)
		if err != nil {
			printErrorBody(data)
			return fmt.Errorf("failed to fetch leaderboard: %w", err)
		}
		return renderValue(mustDecodeJSON(data))
	},
}

var leaderboardExportCmd = &cobra.Command{
	Use:   "export",
	Short: "Export leaderboard data",
	RunE: func(cmd *cobra.Command, args []string) error {
		format, _ := cmd.Flags().GetString("format")
		outFile, _ := cmd.Flags().GetString("output")
		mode, _ := cmd.Flags().GetString("mode")

		url := fmt.Sprintf("%s/api/v2/leaderboard/?mode=%s&page=1&page_size=1000", apiBaseURL(), mode)
		data, _, err := makeRequest(http.MethodGet, url, nil)
		if err != nil {
			printErrorBody(data)
			return fmt.Errorf("failed to fetch leaderboard: %w", err)
		}

		payload := mustDecodeJSON(data)
		entries, ok := payload["entries"].([]any)
		if !ok {
			return errors.New("leaderboard response did not include entries")
		}

		switch format {
		case "json":
			return os.WriteFile(outFile, data, 0o644)
		case "csv":
			return writeLeaderboardCSV(outFile, entries)
		default:
			return fmt.Errorf("unsupported format: %s", format)
		}
	},
}

func init() {
	leaderboardCmd.Flags().StringP("mode", "m", "all", "evaluation mode filter (all|daat|mteb)")
	leaderboardShowCmd.Flags().StringP("mode", "m", "daat", "evaluation mode filter")
	leaderboardShowCmd.Flags().IntP("limit", "l", 20, "max entries to show")

	leaderboardExportCmd.Flags().StringP("format", "f", "csv", "export format (csv|json)")
	leaderboardExportCmd.Flags().StringP("output", "o", "leaderboard.csv", "output file")
	leaderboardExportCmd.Flags().StringP("mode", "m", "all", "evaluation mode filter")

	leaderboardCmd.AddCommand(leaderboardShowCmd)
	leaderboardCmd.AddCommand(leaderboardExportCmd)
}

func writeLeaderboardCSV(path string, entries []any) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer func() {
		_ = file.Close()
	}()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	headers := []string{
		"rank", "system_name", "author", "mode", "overall_score",
		"daat_score", "ndcg_10", "map_100", "mrr_10", "submitted_at",
	}
	if err := writer.Write(headers); err != nil {
		return err
	}

	for _, entry := range entries {
		row, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		record := []string{
			fmt.Sprintf("%v", row["rank"]),
			fmt.Sprintf("%v", row["system_name"]),
			fmt.Sprintf("%v", row["author"]),
			fmt.Sprintf("%v", row["mode"]),
			fmt.Sprintf("%v", row["overall_score"]),
			fmt.Sprintf("%v", row["daat_score"]),
			fmt.Sprintf("%v", row["ndcg_10"]),
			fmt.Sprintf("%v", row["map_100"]),
			fmt.Sprintf("%v", row["mrr_10"]),
			fmt.Sprintf("%v", row["submitted_at"]),
		}
		if err := writer.Write(record); err != nil {
			return err
		}
	}

	fmt.Printf("exported leaderboard to %s\n", path)
	return nil
}

var datasetCmd = &cobra.Command{
	Use:   "dataset",
	Short: "Manage evaluation datasets",
}

var datasetListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available datasets",
	RunE: func(cmd *cobra.Command, args []string) error {
		root := viper.GetString("dataset.local_path")
		if root == "" {
			root = "src/metivta_eval/dataset"
		}

		entries, err := os.ReadDir(root)
		if err != nil {
			return fmt.Errorf("failed to read dataset directory: %w", err)
		}

		files := []string{}
		for _, entry := range entries {
			files = append(files, entry.Name())
		}
		sort.Strings(files)

		payload := map[string]any{
			"dataset_root": root,
			"files":        files,
		}
		return renderValue(payload)
	},
}

var datasetValidateCmd = &cobra.Command{
	Use:   "validate <file>",
	Short: "Validate a dataset file",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		file := args[0]
		raw, err := os.ReadFile(file)
		if err != nil {
			return fmt.Errorf("failed to read file: %w", err)
		}

		var parsed any
		if err := json.Unmarshal(raw, &parsed); err != nil {
			return fmt.Errorf("invalid JSON dataset: %w", err)
		}

		total := 1
		if items, ok := parsed.([]any); ok {
			total = len(items)
		}

		payload := map[string]any{
			"valid":     true,
			"file":      file,
			"examples":  total,
			"validated": time.Now().UTC().Format(time.RFC3339),
		}
		return renderValue(payload)
	},
}

func init() {
	datasetCmd.AddCommand(datasetListCmd)
	datasetCmd.AddCommand(datasetValidateCmd)
}

var serverCmd = &cobra.Command{
	Use:   "server",
	Short: "Control local development server",
}

var serverStartCmd = &cobra.Command{
	Use:   "start",
	Short: "Start the server",
	RunE: func(cmd *cobra.Command, args []string) error {
		if isServerRunning() {
			return errors.New("server is already running")
		}

		port, _ := cmd.Flags().GetInt("port")
		host := "0.0.0.0"
		workDir, err := os.Getwd()
		if err != nil {
			return err
		}

		command := exec.Command(
			"uv",
			"run",
			"uvicorn",
			"api.fastapi_app.main:app",
			"--host",
			host,
			"--port",
			strconv.Itoa(port),
		)
		command.Dir = workDir
		command.Stdout = os.Stdout
		command.Stderr = os.Stderr

		if err := command.Start(); err != nil {
			return fmt.Errorf("failed to start server process: %w", err)
		}

		pid := strconv.Itoa(command.Process.Pid)
		if err := os.WriteFile(serverPIDFile, []byte(pid), 0o644); err != nil {
			return err
		}

		fmt.Printf("server started (pid=%s, port=%d)\n", pid, port)
		return nil
	},
}

var serverStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Check server status",
	RunE: func(cmd *cobra.Command, args []string) error {
		if !isServerRunning() {
			fmt.Println("server is not running")
			return nil
		}

		pid, err := readPID()
		if err != nil {
			return err
		}
		fmt.Printf("server is running (pid=%d)\n", pid)
		return nil
	},
}

var serverStopCmd = &cobra.Command{
	Use:   "stop",
	Short: "Stop the server",
	RunE: func(cmd *cobra.Command, args []string) error {
		pid, err := readPID()
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				fmt.Println("server is not running")
				return nil
			}
			return err
		}

		proc, err := os.FindProcess(pid)
		if err != nil {
			return err
		}
		if err := proc.Signal(syscall.SIGTERM); err != nil {
			return err
		}

		if err := os.Remove(serverPIDFile); err != nil && !errors.Is(err, os.ErrNotExist) {
			return err
		}

		fmt.Printf("server stopped (pid=%d)\n", pid)
		return nil
	},
}

func init() {
	serverStartCmd.Flags().IntP("port", "p", 8001, "port to listen on")
	serverCmd.AddCommand(serverStartCmd)
	serverCmd.AddCommand(serverStatusCmd)
	serverCmd.AddCommand(serverStopCmd)
}

func isServerRunning() bool {
	pid, err := readPID()
	if err != nil {
		return false
	}
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	if err := process.Signal(syscall.Signal(0)); err != nil {
		return false
	}
	return true
}

func readPID() (int, error) {
	raw, err := os.ReadFile(serverPIDFile)
	if err != nil {
		return 0, err
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(raw)))
	if err != nil {
		return 0, err
	}
	return pid, nil
}

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Manage configuration",
}

var configInitCmd = &cobra.Command{
	Use:   "init",
	Short: "Initialize configuration file",
	RunE: func(cmd *cobra.Command, args []string) error {
		path := "config.toml"
		if cfgFile != "" {
			path = cfgFile
		}
		if _, err := os.Stat(path); err == nil {
			return fmt.Errorf("config already exists at %s", path)
		}

		content := "[meta]\nversion = \"2.0.0\"\nenvironment = \"development\"\n\n" +
			"[server]\nhost = \"0.0.0.0\"\nport = 8080\nfastapi_port = 8001\n\n" +
			"[database]\nprovider = \"postgresql\"\n\n" +
			"[database.postgresql]\nhost = \"localhost\"\nport = 5432\ndatabase = \"metivta\"\n" +
			"user = \"metivta\"\npassword = \"\"\nssl_mode = \"prefer\"\n"
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			return err
		}

		fmt.Printf("created config at %s\n", path)
		return nil
	},
}

var configGetCmd = &cobra.Command{
	Use:   "get <key>",
	Short: "Get a configuration value",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		key := args[0]
		value := viper.Get(key)
		fmt.Printf("%s = %v\n", key, value)
		return nil
	},
}

var configListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all configuration values",
	RunE: func(cmd *cobra.Command, args []string) error {
		return renderValue(viper.AllSettings())
	},
}

func init() {
	configCmd.AddCommand(configInitCmd)
	configCmd.AddCommand(configGetCmd)
	configCmd.AddCommand(configListCmd)
}

var logsCmd = &cobra.Command{
	Use:   "logs",
	Short: "View and search logs",
	RunE: func(cmd *cobra.Command, args []string) error {
		logPath := viper.GetString("observability.logging.file_path")
		if logPath == "" {
			logPath = "logs/metivta.log"
		}
		fmt.Printf("log file: %s\n", logPath)
		return nil
	},
}

var logsTailCmd = &cobra.Command{
	Use:   "tail",
	Short: "Tail logs",
	RunE: func(cmd *cobra.Command, args []string) error {
		follow, _ := cmd.Flags().GetBool("follow")
		level, _ := cmd.Flags().GetString("level")
		lines, _ := cmd.Flags().GetInt("lines")

		logPath := viper.GetString("observability.logging.file_path")
		if logPath == "" {
			logPath = "logs/metivta.log"
		}

		file, err := os.Open(logPath)
		if err != nil {
			return err
		}
		defer func() {
			_ = file.Close()
		}()

		scanner := bufio.NewScanner(file)
		buffer := []string{}
		for scanner.Scan() {
			line := scanner.Text()
			if level != "" && !strings.Contains(strings.ToLower(line), strings.ToLower(level)) {
				continue
			}
			buffer = append(buffer, line)
			if len(buffer) > lines {
				buffer = buffer[1:]
			}
		}
		if err := scanner.Err(); err != nil {
			return err
		}

		for _, line := range buffer {
			fmt.Println(line)
		}

		if !follow {
			return nil
		}

		for {
			time.Sleep(2 * time.Second)
			next, err := os.ReadFile(logPath)
			if err != nil {
				return err
			}
			fmt.Print(string(next))
		}
	},
}

var logsSearchCmd = &cobra.Command{
	Use:   "search <query>",
	Short: "Search logs",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		query := strings.ToLower(args[0])

		logPath := viper.GetString("observability.logging.file_path")
		if logPath == "" {
			logPath = "logs/metivta.log"
		}

		raw, err := os.ReadFile(logPath)
		if err != nil {
			return err
		}

		for _, line := range strings.Split(string(raw), "\n") {
			if strings.Contains(strings.ToLower(line), query) {
				fmt.Println(line)
			}
		}
		return nil
	},
}

func init() {
	logsTailCmd.Flags().BoolP("follow", "f", false, "follow log output")
	logsTailCmd.Flags().StringP("level", "l", "", "filter by level")
	logsTailCmd.Flags().IntP("lines", "n", 100, "number of lines to show")

	logsCmd.AddCommand(logsTailCmd)
	logsCmd.AddCommand(logsSearchCmd)
}
