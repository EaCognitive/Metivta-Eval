// Package middleware provides HTTP middleware for the MetivitaEval gateway.
package middleware

import (
	"crypto/rsa"
	"errors"
	"fmt"
	"os"
	"slices"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/metivta/metivta-eval/internal/config"
)

// JWTClaims represents the claims in a MetivitaEval JWT.
type JWTClaims struct {
	jwt.RegisteredClaims
	UserID   string   `json:"user_id"`
	Email    string   `json:"email"`
	Role     string   `json:"role"`
	Scopes   []string `json:"scopes"`
	APIKeyID string   `json:"api_key_id,omitempty"`
}

// JWTManager handles JWT creation and validation.
type JWTManager struct {
	privateKey           *rsa.PrivateKey
	publicKey            *rsa.PublicKey
	issuer               string
	audience             string
	accessTokenDuration  time.Duration
	refreshTokenDuration time.Duration
}

// NewJWTManager creates a new JWT manager from config.
func NewJWTManager(cfg *config.Config) (*JWTManager, error) {
	// Load private key
	privateKeyPEM, err := os.ReadFile(cfg.Security.JWT.PrivateKeyPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read private key: %w", err)
	}

	privateKey, err := jwt.ParseRSAPrivateKeyFromPEM(privateKeyPEM)
	if err != nil {
		return nil, fmt.Errorf("failed to parse private key: %w", err)
	}

	// Load public key
	publicKeyPEM, err := os.ReadFile(cfg.Security.JWT.PublicKeyPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read public key: %w", err)
	}

	publicKey, err := jwt.ParseRSAPublicKeyFromPEM(publicKeyPEM)
	if err != nil {
		return nil, fmt.Errorf("failed to parse public key: %w", err)
	}

	return &JWTManager{
		privateKey:           privateKey,
		publicKey:            publicKey,
		issuer:               cfg.Security.JWT.Issuer,
		audience:             cfg.Security.JWT.Audience,
		accessTokenDuration:  time.Duration(cfg.Security.JWT.AccessTokenTTLMinutes) * time.Minute,
		refreshTokenDuration: time.Duration(cfg.Security.JWT.RefreshTokenTTLDays) * 24 * time.Hour,
	}, nil
}

// GenerateAccessToken creates a new access token.
func (m *JWTManager) GenerateAccessToken(userID, email, role string, scopes []string) (string, error) {
	now := time.Now()

	claims := JWTClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			ID:        uuid.New().String(),
			Subject:   userID,
			Issuer:    m.issuer,
			Audience:  jwt.ClaimStrings{m.audience},
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(m.accessTokenDuration)),
		},
		UserID: userID,
		Email:  email,
		Role:   role,
		Scopes: scopes,
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	return token.SignedString(m.privateKey)
}

// GenerateRefreshToken creates a new refresh token.
func (m *JWTManager) GenerateRefreshToken(userID string) (string, error) {
	now := time.Now()

	claims := jwt.RegisteredClaims{
		ID:        uuid.New().String(),
		Subject:   userID,
		Issuer:    m.issuer,
		Audience:  jwt.ClaimStrings{m.audience},
		IssuedAt:  jwt.NewNumericDate(now),
		NotBefore: jwt.NewNumericDate(now),
		ExpiresAt: jwt.NewNumericDate(now.Add(m.refreshTokenDuration)),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	return token.SignedString(m.privateKey)
}

// GenerateAPIKeyToken creates a token from an API key (longer lived, limited scopes).
func (m *JWTManager) GenerateAPIKeyToken(userID, apiKeyID string, scopes []string) (string, error) {
	now := time.Now()

	claims := JWTClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			ID:        uuid.New().String(),
			Subject:   userID,
			Issuer:    m.issuer,
			Audience:  jwt.ClaimStrings{m.audience},
			IssuedAt:  jwt.NewNumericDate(now),
			NotBefore: jwt.NewNumericDate(now),
			// API key tokens last 1 hour, then must re-auth
			ExpiresAt: jwt.NewNumericDate(now.Add(time.Hour)),
		},
		UserID:   userID,
		APIKeyID: apiKeyID,
		Scopes:   scopes,
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	return token.SignedString(m.privateKey)
}

// ValidateToken validates a JWT and returns the claims.
func (m *JWTManager) ValidateToken(tokenString string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
		// Validate signing method
		if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return m.publicKey, nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	claims, ok := token.Claims.(*JWTClaims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid token")
	}

	// Validate issuer
	if claims.Issuer != m.issuer {
		return nil, errors.New("invalid issuer")
	}

	// Validate audience
	aud, err := claims.GetAudience()
	if err != nil || !slices.Contains(aud, m.audience) {
		return nil, errors.New("invalid audience")
	}

	return claims, nil
}

// Global JWT manager (set during app init)
var jwtManager *JWTManager

// SetJWTManager sets the global JWT manager.
func SetJWTManager(m *JWTManager) {
	jwtManager = m
}

// GetJWTManager returns the global JWT manager.
func GetJWTManager() *JWTManager {
	return jwtManager
}

// JWTMiddleware validates JWT tokens in Authorization header.
func JWTMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		if jwtManager == nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
				"error":   "jwt_not_configured",
				"message": "JWT authentication not configured",
			})
		}

		// Get Authorization header
		authHeader := c.Get("Authorization")
		if authHeader == "" {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error":   "missing_authorization",
				"message": "Authorization header required",
			})
		}

		// Extract token
		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error":   "invalid_authorization",
				"message": "Authorization header must be 'Bearer <token>'",
			})
		}

		tokenString := parts[1]

		// Validate token
		claims, err := jwtManager.ValidateToken(tokenString)
		if err != nil {
			return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
				"error":   "invalid_token",
				"message": err.Error(),
			})
		}

		// Store claims in context
		c.Locals("user_id", claims.UserID)
		c.Locals("email", claims.Email)
		c.Locals("role", claims.Role)
		c.Locals("scopes", claims.Scopes)
		c.Locals("jwt_claims", claims)

		if claims.APIKeyID != "" {
			c.Locals("api_key_id", claims.APIKeyID)
		}

		return c.Next()
	}
}

// OptionalJWTMiddleware validates JWT if present, but doesn't require it.
func OptionalJWTMiddleware() fiber.Handler {
	return func(c *fiber.Ctx) error {
		authHeader := c.Get("Authorization")
		if authHeader == "" {
			return c.Next()
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" {
			return c.Next()
		}

		if jwtManager != nil {
			if claims, err := jwtManager.ValidateToken(parts[1]); err == nil {
				c.Locals("user_id", claims.UserID)
				c.Locals("email", claims.Email)
				c.Locals("role", claims.Role)
				c.Locals("scopes", claims.Scopes)
				c.Locals("jwt_claims", claims)
			}
		}

		return c.Next()
	}
}

// RequireScope middleware requires specific scopes.
func RequireScope(requiredScopes ...string) fiber.Handler {
	return func(c *fiber.Ctx) error {
		scopesRaw := c.Locals("scopes")
		if scopesRaw == nil {
			return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
				"error":   "no_scopes",
				"message": "No scopes in token",
			})
		}

		scopes, ok := scopesRaw.([]string)
		if !ok {
			return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
				"error":   "invalid_scopes",
				"message": "Invalid scopes format",
			})
		}

		// Check if user has all required scopes
		scopeSet := make(map[string]bool)
		for _, s := range scopes {
			scopeSet[s] = true
		}

		for _, required := range requiredScopes {
			if !scopeSet[required] {
				return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
					"error":   "insufficient_scope",
					"message": fmt.Sprintf("Required scope: %s", required),
				})
			}
		}

		return c.Next()
	}
}

// RequireRole middleware requires specific role.
func RequireRole(allowedRoles ...string) fiber.Handler {
	roleSet := make(map[string]bool)
	for _, r := range allowedRoles {
		roleSet[r] = true
	}

	return func(c *fiber.Ctx) error {
		role, ok := c.Locals("role").(string)
		if !ok || role == "" {
			return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
				"error":   "no_role",
				"message": "No role in token",
			})
		}

		if !roleSet[role] {
			return c.Status(fiber.StatusForbidden).JSON(fiber.Map{
				"error":   "insufficient_role",
				"message": "Insufficient role for this action",
			})
		}

		return c.Next()
	}
}
