package middleware

import (
	"crypto/rand"
	"crypto/rsa"
	"testing"
	"time"
)

func generateTestKeys(t *testing.T) (*rsa.PrivateKey, *rsa.PublicKey) {
	t.Helper()
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("failed to generate test keys: %v", err)
	}
	return privateKey, &privateKey.PublicKey
}

func newTestJWTManager(t *testing.T) *JWTManager {
	t.Helper()
	privateKey, publicKey := generateTestKeys(t)
	return &JWTManager{
		privateKey:           privateKey,
		publicKey:            publicKey,
		issuer:               "test-issuer",
		audience:             "test-audience",
		accessTokenDuration:  time.Hour,
		refreshTokenDuration: 24 * time.Hour * 30,
	}
}

func TestJWTManager_GenerateAccessToken(t *testing.T) {
	manager := newTestJWTManager(t)

	userID := "user-123"
	email := "test@example.com"
	role := "user"
	scopes := []string{"read", "write"}

	token, err := manager.GenerateAccessToken(userID, email, role, scopes)
	if err != nil {
		t.Fatalf("GenerateAccessToken() error = %v", err)
	}

	if token == "" {
		t.Error("GenerateAccessToken() returned empty token")
	}

	// Token should have 3 parts separated by dots (header.payload.signature)
	parts := 0
	for _, c := range token {
		if c == '.' {
			parts++
		}
	}
	if parts != 2 {
		t.Errorf("GenerateAccessToken() token format invalid, expected 2 dots, got %d", parts)
	}
}

func TestJWTManager_ValidateToken(t *testing.T) {
	manager := newTestJWTManager(t)

	userID := "user-456"
	email := "validate@example.com"
	role := "admin"
	scopes := []string{"read", "write", "admin"}

	token, err := manager.GenerateAccessToken(userID, email, role, scopes)
	if err != nil {
		t.Fatalf("GenerateAccessToken() error = %v", err)
	}

	claims, err := manager.ValidateToken(token)
	if err != nil {
		t.Fatalf("ValidateToken() error = %v", err)
	}

	if claims.UserID != userID {
		t.Errorf("ValidateToken() UserID = %v, want %v", claims.UserID, userID)
	}
	if claims.Email != email {
		t.Errorf("ValidateToken() Email = %v, want %v", claims.Email, email)
	}
	if claims.Role != role {
		t.Errorf("ValidateToken() Role = %v, want %v", claims.Role, role)
	}
	if len(claims.Scopes) != len(scopes) {
		t.Errorf("ValidateToken() Scopes length = %d, want %d", len(claims.Scopes), len(scopes))
	}
	if claims.Issuer != "test-issuer" {
		t.Errorf("ValidateToken() Issuer = %v, want test-issuer", claims.Issuer)
	}
}

func TestJWTManager_ValidateToken_Expired(t *testing.T) {
	privateKey, publicKey := generateTestKeys(t)

	manager := &JWTManager{
		privateKey:           privateKey,
		publicKey:            publicKey,
		issuer:               "test-issuer",
		audience:             "test-audience",
		accessTokenDuration:  -time.Hour, // negative duration = already expired
		refreshTokenDuration: 24 * time.Hour,
	}

	token, err := manager.GenerateAccessToken("user-789", "expired@example.com", "user", []string{"read"})
	if err != nil {
		t.Fatalf("GenerateAccessToken() error = %v", err)
	}

	_, err = manager.ValidateToken(token)
	if err == nil {
		t.Error("ValidateToken() expected error for expired token, got nil")
	}
}

func TestJWTManager_ValidateToken_Invalid(t *testing.T) {
	manager := newTestJWTManager(t)

	invalidTokens := []struct {
		name  string
		token string
	}{
		{"empty", ""},
		{"malformed", "not.a.valid.token"},
		{"random", "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"},
	}

	for _, tt := range invalidTokens {
		t.Run(tt.name, func(t *testing.T) {
			_, err := manager.ValidateToken(tt.token)
			if err == nil {
				t.Errorf("ValidateToken(%s) expected error, got nil", tt.name)
			}
		})
	}
}

func TestJWTManager_ValidateToken_WrongIssuer(t *testing.T) {
	// Create token with one manager
	manager1 := newTestJWTManager(t)
	token, err := manager1.GenerateAccessToken("user-123", "test@example.com", "user", []string{"read"})
	if err != nil {
		t.Fatalf("GenerateAccessToken() error = %v", err)
	}

	// Validate with a manager that has different issuer but same keys
	manager2 := &JWTManager{
		privateKey:           manager1.privateKey,
		publicKey:            manager1.publicKey,
		issuer:               "different-issuer",
		audience:             "test-audience",
		accessTokenDuration:  time.Hour,
		refreshTokenDuration: 24 * time.Hour,
	}

	_, err = manager2.ValidateToken(token)
	if err == nil {
		t.Error("ValidateToken() expected error for wrong issuer, got nil")
	}
}

func TestJWTManager_ValidateToken_WrongAudience(t *testing.T) {
	manager1 := newTestJWTManager(t)
	token, err := manager1.GenerateAccessToken("user-123", "test@example.com", "user", []string{"read"})
	if err != nil {
		t.Fatalf("GenerateAccessToken() error = %v", err)
	}

	manager2 := &JWTManager{
		privateKey:           manager1.privateKey,
		publicKey:            manager1.publicKey,
		issuer:               "test-issuer",
		audience:             "different-audience",
		accessTokenDuration:  time.Hour,
		refreshTokenDuration: 24 * time.Hour,
	}

	_, err = manager2.ValidateToken(token)
	if err == nil {
		t.Error("ValidateToken() expected error for wrong audience, got nil")
	}
}

func TestJWTManager_GenerateRefreshToken(t *testing.T) {
	manager := newTestJWTManager(t)

	userID := "user-refresh"

	token, err := manager.GenerateRefreshToken(userID)
	if err != nil {
		t.Fatalf("GenerateRefreshToken() error = %v", err)
	}

	if token == "" {
		t.Error("GenerateRefreshToken() returned empty token")
	}

	// Verify it's a valid JWT format
	parts := 0
	for _, c := range token {
		if c == '.' {
			parts++
		}
	}
	if parts != 2 {
		t.Errorf("GenerateRefreshToken() token format invalid, expected 2 dots, got %d", parts)
	}
}

func TestJWTManager_GenerateAPIKeyToken(t *testing.T) {
	manager := newTestJWTManager(t)

	userID := "user-api"
	apiKeyID := "key-123"
	scopes := []string{"eval:read", "eval:write"}

	token, err := manager.GenerateAPIKeyToken(userID, apiKeyID, scopes)
	if err != nil {
		t.Fatalf("GenerateAPIKeyToken() error = %v", err)
	}

	if token == "" {
		t.Error("GenerateAPIKeyToken() returned empty token")
	}

	// Validate and check claims
	claims, err := manager.ValidateToken(token)
	if err != nil {
		t.Fatalf("ValidateToken() error = %v", err)
	}

	if claims.UserID != userID {
		t.Errorf("ValidateToken() UserID = %v, want %v", claims.UserID, userID)
	}
	if claims.APIKeyID != apiKeyID {
		t.Errorf("ValidateToken() APIKeyID = %v, want %v", claims.APIKeyID, apiKeyID)
	}
	if len(claims.Scopes) != len(scopes) {
		t.Errorf("ValidateToken() Scopes length = %d, want %d", len(claims.Scopes), len(scopes))
	}
}

func TestJWTManager_ValidateToken_WrongSigningKey(t *testing.T) {
	manager1 := newTestJWTManager(t)
	token, err := manager1.GenerateAccessToken("user-123", "test@example.com", "user", []string{"read"})
	if err != nil {
		t.Fatalf("GenerateAccessToken() error = %v", err)
	}

	// Create another manager with different keys
	manager2 := newTestJWTManager(t)

	_, err = manager2.ValidateToken(token)
	if err == nil {
		t.Error("ValidateToken() expected error for wrong signing key, got nil")
	}
}

func TestSetGetJWTManager(t *testing.T) {
	// Clear any existing manager
	originalManager := jwtManager
	defer func() { jwtManager = originalManager }()

	manager := newTestJWTManager(t)

	SetJWTManager(manager)

	got := GetJWTManager()
	if got != manager {
		t.Error("GetJWTManager() did not return the set manager")
	}
}

func BenchmarkJWTManager_GenerateAccessToken(b *testing.B) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		b.Fatalf("failed to generate keys: %v", err)
	}

	manager := &JWTManager{
		privateKey:           privateKey,
		publicKey:            &privateKey.PublicKey,
		issuer:               "bench-issuer",
		audience:             "bench-audience",
		accessTokenDuration:  time.Hour,
		refreshTokenDuration: 24 * time.Hour,
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = manager.GenerateAccessToken("user-bench", "bench@example.com", "user", []string{"read"})
	}
}

func BenchmarkJWTManager_ValidateToken(b *testing.B) {
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		b.Fatalf("failed to generate keys: %v", err)
	}

	manager := &JWTManager{
		privateKey:           privateKey,
		publicKey:            &privateKey.PublicKey,
		issuer:               "bench-issuer",
		audience:             "bench-audience",
		accessTokenDuration:  time.Hour,
		refreshTokenDuration: 24 * time.Hour,
	}

	token, err := manager.GenerateAccessToken("user-bench", "bench@example.com", "user", []string{"read"})
	if err != nil {
		b.Fatalf("failed to generate token: %v", err)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = manager.ValidateToken(token)
	}
}
