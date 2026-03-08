// MetivitaEval CLI - Enterprise AI Benchmarking Platform
//
// Usage:
//
//	metivta [command] [flags]
//
// Commands:
//
//	eval        Run and manage evaluations
//	leaderboard View and export leaderboard data
//	dataset     Manage datasets
//	server      Control local server
//	config      Manage configuration
//	logs        View and search logs
//	version     Show version information
package main

import (
	"os"

	"github.com/metivta/metivta-eval/cmd/metivta/cmd"
)

// Version information (set via ldflags)
var (
	Version   = "dev"
	CommitSHA = "unknown"
	BuildDate = "unknown"
)

func main() {
	// Set version info for commands
	cmd.SetVersionInfo(Version, CommitSHA, BuildDate)

	// Execute root command
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
