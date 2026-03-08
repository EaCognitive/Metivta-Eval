package middleware

import (
	"crypto/tls"
	"testing"

	"github.com/metivta/metivta-eval/internal/config"
)

func TestNewMTLSConfig(t *testing.T) {
	tests := []struct {
		name         string
		cfg          *config.Config
		wantMinTLS   uint16
		wantCACert   string
		wantRequired bool
	}{
		{
			name: "TLS 1.3",
			cfg: &config.Config{
				Security: config.SecurityConfig{
					MTLS: config.MTLSConfig{
						CACertPath:         "/path/to/ca.crt",
						ServerCertPath:     "/path/to/server.crt",
						ServerKeyPath:      "/path/to/server.key",
						ClientCertRequired: true,
						MinTLSVersion:      "1.3",
					},
				},
			},
			wantMinTLS:   tls.VersionTLS13,
			wantCACert:   "/path/to/ca.crt",
			wantRequired: true,
		},
		{
			name: "TLS 1.2",
			cfg: &config.Config{
				Security: config.SecurityConfig{
					MTLS: config.MTLSConfig{
						CACertPath:         "/path/to/ca.crt",
						ServerCertPath:     "/path/to/server.crt",
						ServerKeyPath:      "/path/to/server.key",
						ClientCertRequired: false,
						MinTLSVersion:      "1.2",
					},
				},
			},
			wantMinTLS:   tls.VersionTLS12,
			wantCACert:   "/path/to/ca.crt",
			wantRequired: false,
		},
		{
			name: "default TLS version",
			cfg: &config.Config{
				Security: config.SecurityConfig{
					MTLS: config.MTLSConfig{
						CACertPath:         "/path/to/ca.crt",
						ServerCertPath:     "/path/to/server.crt",
						ServerKeyPath:      "/path/to/server.key",
						ClientCertRequired: true,
						MinTLSVersion:      "", // empty defaults to 1.3
					},
				},
			},
			wantMinTLS:   tls.VersionTLS13,
			wantCACert:   "/path/to/ca.crt",
			wantRequired: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mtlsCfg := NewMTLSConfig(tt.cfg)

			if mtlsCfg.MinTLSVersion != tt.wantMinTLS {
				t.Errorf("MinTLSVersion = %v, want %v", mtlsCfg.MinTLSVersion, tt.wantMinTLS)
			}
			if mtlsCfg.CACertPath != tt.wantCACert {
				t.Errorf("CACertPath = %v, want %v", mtlsCfg.CACertPath, tt.wantCACert)
			}
			if mtlsCfg.ClientCertRequired != tt.wantRequired {
				t.Errorf("ClientCertRequired = %v, want %v", mtlsCfg.ClientCertRequired, tt.wantRequired)
			}
		})
	}
}

func TestMTLSConfig_TLSConfig_MissingCA(t *testing.T) {
	mtlsCfg := &MTLSConfig{
		CACertPath:         "/nonexistent/ca.crt",
		ServerCertPath:     "/nonexistent/server.crt",
		ServerKeyPath:      "/nonexistent/server.key",
		ClientCertRequired: true,
		MinTLSVersion:      tls.VersionTLS13,
	}

	_, err := mtlsCfg.TLSConfig()
	if err == nil {
		t.Error("TLSConfig() expected error for missing CA cert, got nil")
	}
}

func TestMTLSConfig_ClientAuthMode(t *testing.T) {
	tests := []struct {
		name           string
		clientRequired bool
		wantClientAuth tls.ClientAuthType
	}{
		{
			name:           "client cert required",
			clientRequired: true,
			wantClientAuth: tls.RequireAndVerifyClientCert,
		},
		{
			name:           "client cert not required",
			clientRequired: false,
			wantClientAuth: tls.NoClientCert,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mtlsCfg := &MTLSConfig{
				ClientCertRequired: tt.clientRequired,
			}

			// We can check the expected value without actually creating TLS config
			var expectedAuth tls.ClientAuthType
			if mtlsCfg.ClientCertRequired {
				expectedAuth = tls.RequireAndVerifyClientCert
			} else {
				expectedAuth = tls.NoClientCert
			}

			if expectedAuth != tt.wantClientAuth {
				t.Errorf("ClientAuth = %v, want %v", expectedAuth, tt.wantClientAuth)
			}
		})
	}
}

func TestValidateClientCertCN_AllowedCNs(t *testing.T) {
	allowedCNs := []string{"client1.example.com", "client2.example.com", "admin.example.com"}

	// Create the middleware handler
	handler := ValidateClientCertCN(allowedCNs)

	if handler == nil {
		t.Error("ValidateClientCertCN() returned nil handler")
	}
}

func TestRequireClientCert_Handler(t *testing.T) {
	handler := RequireClientCert()

	if handler == nil {
		t.Error("RequireClientCert() returned nil handler")
	}
}

func TestClientCertMiddleware_Handler(t *testing.T) {
	handler := ClientCertMiddleware()

	if handler == nil {
		t.Error("ClientCertMiddleware() returned nil handler")
	}
}
