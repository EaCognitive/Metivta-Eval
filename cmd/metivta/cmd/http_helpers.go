package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

func makeRequest(method, url string, body any) ([]byte, int, error) {
	var requestBody io.Reader
	if body != nil {
		payload, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to marshal payload: %w", err)
		}
		requestBody = bytes.NewBuffer(payload)
	}

	req, err := http.NewRequest(method, url, requestBody)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Content-Type", "application/json")

	if key := apiKey(); key != "" {
		req.Header.Set("X-API-Key", key)
	}

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer func() {
		_ = resp.Body.Close()
	}()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, err
	}

	if resp.StatusCode >= 400 {
		return data, resp.StatusCode, fmt.Errorf("request failed with status %d", resp.StatusCode)
	}
	return data, resp.StatusCode, nil
}

func renderValue(value any) error {
	switch output {
	case "json":
		payload, err := json.MarshalIndent(value, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(payload))
	case "yaml":
		payload, err := yaml.Marshal(value)
		if err != nil {
			return err
		}
		fmt.Println(string(payload))
	default:
		payload, err := json.MarshalIndent(value, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(payload))
	}
	return nil
}

func decodeMap(data []byte) (map[string]any, error) {
	payload := map[string]any{}
	if err := json.Unmarshal(data, &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func printErrorBody(body []byte) {
	if len(body) == 0 {
		return
	}
	fmt.Fprintf(os.Stderr, "response: %s\n", string(body))
}

func mustDecodeJSON(data []byte) map[string]any {
	payload, err := decodeMap(data)
	if err != nil {
		return map[string]any{"raw": string(data)}
	}
	return payload
}
