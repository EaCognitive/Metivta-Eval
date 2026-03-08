// Package middleware provides HTTP middleware for the MetivitaEval gateway.
package middleware

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"

	"github.com/gofiber/fiber/v2"
	"github.com/metivta/metivta-eval/internal/config"
)

// MTLSConfig holds mTLS configuration for the server.
type MTLSConfig struct {
	CACertPath         string
	ServerCertPath     string
	ServerKeyPath      string
	ClientCertRequired bool
	MinTLSVersion      uint16
}

// NewMTLSConfig creates MTLSConfig from application config.
func NewMTLSConfig(cfg *config.Config) *MTLSConfig {
	var minVersion uint16 = tls.VersionTLS13
	switch cfg.Security.MTLS.MinTLSVersion {
	case "1.2":
		minVersion = tls.VersionTLS12
	case "1.3":
		minVersion = tls.VersionTLS13
	}

	return &MTLSConfig{
		CACertPath:         cfg.Security.MTLS.CACertPath,
		ServerCertPath:     cfg.Security.MTLS.ServerCertPath,
		ServerKeyPath:      cfg.Security.MTLS.ServerKeyPath,
		ClientCertRequired: cfg.Security.MTLS.ClientCertRequired,
		MinTLSVersion:      minVersion,
	}
}

// TLSConfig creates a tls.Config for mTLS.
func (m *MTLSConfig) TLSConfig() (*tls.Config, error) {
	// Load CA certificate
	caCert, err := os.ReadFile(m.CACertPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read CA cert: %w", err)
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, fmt.Errorf("failed to parse CA cert")
	}

	// Load server certificate
	serverCert, err := tls.LoadX509KeyPair(m.ServerCertPath, m.ServerKeyPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load server cert: %w", err)
	}

	// Configure client auth
	clientAuth := tls.NoClientCert
	if m.ClientCertRequired {
		clientAuth = tls.RequireAndVerifyClientCert
	}

	return &tls.Config{
		Certificates: []tls.Certificate{serverCert},
		ClientCAs:    caCertPool,
		ClientAuth:   clientAuth,
		MinVersion:   m.MinTLSVersion,
		CipherSuites: []uint16{
			tls.TLS_AES_256_GCM_SHA384,
			tls.TLS_AES_128_GCM_SHA256,
			tls.TLS_CHACHA20_POLY1305_SHA256,
		},
	}, nil
}

// ClientCertMiddleware extracts and validates client certificate info.
func ClientCertMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		// Get TLS connection state
		tlsState := c.Context().TLSConnectionState()
		if tlsState == nil {
			// Not a TLS connection
			return c.Next()
		}

		// Check for peer certificates (client certs in mTLS)
		if len(tlsState.PeerCertificates) > 0 {
			clientCert := tlsState.PeerCertificates[0]

			// Store cert info in context
			c.Locals("client_cert_subject", clientCert.Subject.String())
			c.Locals("client_cert_issuer", clientCert.Issuer.String())
			c.Locals("client_cert_serial", clientCert.SerialNumber.String())
			c.Locals("client_cert_not_before", clientCert.NotBefore)
			c.Locals("client_cert_not_after", clientCert.NotAfter)

			// Extract CN for logging/authorization
			if len(clientCert.Subject.CommonName) > 0 {
				c.Locals("client_cn", clientCert.Subject.CommonName)
			}

			// Extract organization
			if len(clientCert.Subject.Organization) > 0 {
				c.Locals("client_org", clientCert.Subject.Organization[0])
			}
		}

		return c.Next()
	}
}

// RequireClientCert middleware enforces client certificate presence.
func RequireClientCert() fiber.Handler {
	return func(c *fiber.Ctx) error {
		tlsState := c.Context().TLSConnectionState()
		if tlsState == nil {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{
				"error":   "tls_required",
				"message": "TLS connection required",
			})
		}

		if len(tlsState.PeerCertificates) == 0 {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error":   "client_cert_required",
				"message": "Client certificate required for this endpoint",
			})
		}

		return c.Next()
	}
}

// ValidateClientCertCN middleware validates client CN against allowed list.
func ValidateClientCertCN(allowedCNs []string) fiber.Handler {
	cnSet := make(map[string]bool)
	for _, cn := range allowedCNs {
		cnSet[cn] = true
	}

	return func(c *fiber.Ctx) error {
		clientCN, ok := c.Locals("client_cn").(string)
		if !ok || clientCN == "" {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error":   "invalid_client_cert",
				"message": "Client certificate CN not found",
			})
		}

		if !cnSet[clientCN] {
			return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
				"error":   "unauthorized_client",
				"message": "Client certificate not authorized",
			})
		}

		return c.Next()
	}
}
