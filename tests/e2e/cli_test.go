// Package e2e provides end-to-end tests for the MetivitaEval CLI.
package e2e

import (
	"bytes"
	"os"
	"os/exec"
	"strings"
	"testing"
)

// TestCLIHelp verifies the help command works correctly.
func TestCLIHelp(t *testing.T) {
	cmd := exec.Command("go", "run", "../../cmd/metivta/main.go", "--help")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("CLI help command failed: %v\nstderr: %s", err, stderr.String())
	}

	output := stdout.String()

	// Check for expected help content
	expectedStrings := []string{
		"MetivitaEval",
		"eval",
		"leaderboard",
		"dataset",
		"server",
		"config",
		"version",
	}

	for _, expected := range expectedStrings {
		if !strings.Contains(output, expected) {
			t.Errorf("Help output should contain %q, got:\n%s", expected, output)
		}
	}
}

// TestCLIVersion verifies the version command works correctly.
func TestCLIVersion(t *testing.T) {
	cmd := exec.Command("go", "run", "../../cmd/metivta/main.go", "version")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("CLI version command failed: %v\nstderr: %s", err, stderr.String())
	}

	output := stdout.String()

	// Check for expected version content
	expectedStrings := []string{
		"MetivitaEval CLI",
		"Version:",
		"Commit:",
		"Built:",
	}

	for _, expected := range expectedStrings {
		if !strings.Contains(output, expected) {
			t.Errorf("Version output should contain %q, got:\n%s", expected, output)
		}
	}
}

// TestCLIEvalHelp verifies the eval help command works correctly.
func TestCLIEvalHelp(t *testing.T) {
	cmd := exec.Command("go", "run", "../../cmd/metivta/main.go", "eval", "--help")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("CLI eval help command failed: %v\nstderr: %s", err, stderr.String())
	}

	output := stdout.String()

	// Check for expected eval help content
	expectedStrings := []string{
		"Run and manage evaluations",
		"run",
		"status",
		"list",
	}

	for _, expected := range expectedStrings {
		if !strings.Contains(output, expected) {
			t.Errorf("Eval help output should contain %q, got:\n%s", expected, output)
		}
	}
}

// TestCLILeaderboardHelp verifies the leaderboard help command works correctly.
func TestCLILeaderboardHelp(t *testing.T) {
	cmd := exec.Command("go", "run", "../../cmd/metivta/main.go", "leaderboard", "--help")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("CLI leaderboard help command failed: %v\nstderr: %s", err, stderr.String())
	}

	output := stdout.String()

	// Check for expected leaderboard help content
	expectedStrings := []string{
		"leaderboard",
		"--mode",
	}

	for _, expected := range expectedStrings {
		if !strings.Contains(output, expected) {
			t.Errorf("Leaderboard help output should contain %q, got:\n%s", expected, output)
		}
	}
}

// TestCLIDatasetHelp verifies the dataset help command works correctly.
func TestCLIDatasetHelp(t *testing.T) {
	cmd := exec.Command("go", "run", "../../cmd/metivta/main.go", "dataset", "--help")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("CLI dataset help command failed: %v\nstderr: %s", err, stderr.String())
	}

	output := stdout.String()

	// Check for expected dataset help content
	expectedStrings := []string{
		"dataset",
		"list",
		"validate",
	}

	for _, expected := range expectedStrings {
		if !strings.Contains(output, expected) {
			t.Errorf("Dataset help output should contain %q, got:\n%s", expected, output)
		}
	}
}

// TestCLIConfigList verifies the config list command works correctly.
func TestCLIConfigList(t *testing.T) {
	// Create a temporary config file
	tmpDir := t.TempDir()
	configPath := tmpDir + "/config.toml"
	configContent := `
[server]
port = 8080

[logging]
level = "info"
`
	if err := os.WriteFile(configPath, []byte(configContent), 0644); err != nil {
		t.Fatalf("Failed to create test config: %v", err)
	}

	cmd := exec.Command("go", "run", "../../cmd/metivta/main.go", "--config", configPath, "config", "list")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("CLI config list command failed: %v\nstderr: %s", err, stderr.String())
	}

	output := stdout.String()
	if !strings.Contains(output, "\"server\"") {
		t.Errorf("Config list output should include server section, got:\n%s", output)
	}
}

// TestCLIBinaryBuild verifies the binary can be built.
func TestCLIBinaryBuild(t *testing.T) {
	tmpDir := t.TempDir()
	binaryPath := tmpDir + "/metivta"

	cmd := exec.Command("go", "build", "-o", binaryPath, "../../cmd/metivta")
	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		t.Fatalf("Failed to build binary: %v\nstderr: %s", err, stderr.String())
	}

	// Verify binary exists
	if _, err := os.Stat(binaryPath); os.IsNotExist(err) {
		t.Error("Binary was not created")
	}

	// Test the built binary works
	testCmd := exec.Command(binaryPath, "--help")
	var testStdout bytes.Buffer
	testCmd.Stdout = &testStdout

	if err := testCmd.Run(); err != nil {
		t.Errorf("Built binary failed to run: %v", err)
	}

	if !strings.Contains(testStdout.String(), "MetivitaEval") {
		t.Error("Built binary help output doesn't contain expected content")
	}
}
