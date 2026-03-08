package main

import (
	"crypto/tls"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

var (
	Version   = "dev"
	CommitSHA = "unknown"
)

const homepageHTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Metivta Evaluation Kit</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&family=JetBrains+Mono:wght@500&display=swap"
    rel="stylesheet"
  />
  <style>
    :root {
      color-scheme: dark;
      --bg: #05070b;
      --bg-soft: #0a0f16;
      --surface: #0b1118;
      --surface-2: #0d141e;
      --line: #1f2936;
      --text: #e6edf7;
      --muted: #9fb0c6;
      --green: #3ecf8e;
      --green-deep: #2ea06f;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Manrope", sans-serif;
      color: var(--text);
      background:
        radial-gradient(44vw 36vw at 10% -2%, #132234 0%, transparent 72%),
        radial-gradient(52vw 44vw at 112% 108%, #0b2c1d 0%, transparent 74%),
        linear-gradient(180deg, var(--bg) 0%, var(--bg-soft) 100%);
      display: grid;
      place-items: center;
      padding: 22px;
    }
    .shell {
      width: min(1120px, 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: linear-gradient(180deg, #090d14 0%, #0b1118 100%);
      box-shadow: 0 28px 68px rgba(0, 0, 0, 0.55);
    }
    .nav {
      height: 62px;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: rgba(8, 12, 18, 0.95);
    }
    .brand {
      font-family: "JetBrains Mono", monospace;
      font-size: 0.72rem;
      color: #a3b5cc;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }
    .repo {
      color: #c6d5e8;
      text-decoration: none;
      font-size: 0.86rem;
      border: 1px solid #273445;
      border-radius: 999px;
      padding: 8px 12px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      background: #0e1621;
    }
    .repo:hover {
      border-color: #3b4d65;
      background: #121d2c;
    }
    .github-icon {
      width: 15px;
      height: 15px;
      flex: 0 0 auto;
      display: block;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      min-height: 560px;
    }
    .hero {
      padding: clamp(20px, 4vw, 56px);
      border-right: 1px solid var(--line);
      display: grid;
      align-content: start;
      gap: 18px;
    }
    h1 {
      margin: 0;
      font-size: clamp(2.2rem, 6.1vw, 4.7rem);
      line-height: 0.93;
      letter-spacing: -0.045em;
      max-width: 10ch;
      text-wrap: balance;
    }
    .copy {
      margin: 0;
      color: var(--muted);
      max-width: 63ch;
      font-size: clamp(0.97rem, 1.5vw, 1.08rem);
      line-height: 1.52;
    }
    .identity {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .chip {
      border: 1px solid #263445;
      border-radius: 999px;
      padding: 8px 12px;
      color: #cfdbeb;
      background: #0f1825;
      font-size: 0.88rem;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .chip:hover {
      border-color: #3b4e66;
      background: #142133;
    }
    .cta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .btn {
      border: 1px solid #2a394a;
      border-radius: 11px;
      padding: 12px 14px;
      color: #d7e3f3;
      font-size: 0.94rem;
      font-weight: 700;
      text-decoration: none;
      background: linear-gradient(180deg, #141e2b 0%, #0f1823 100%);
      transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    .btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 9px 18px rgba(0, 0, 0, 0.32);
    }
    .btn.primary {
      color: #02180d;
      border-color: #45dc9b;
      background: linear-gradient(180deg, #53e3a5 0%, #35c383 100%);
    }
    .cards {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .card {
      border: 1px solid #233142;
      border-radius: 12px;
      padding: 12px;
      background: #101824;
    }
    .card strong {
      display: block;
      font-size: 0.9rem;
      letter-spacing: -0.01em;
      color: #dbe7f8;
    }
    .card span {
      display: block;
      margin-top: 6px;
      color: #9fb1c8;
      font-size: 0.8rem;
      line-height: 1.42;
    }
    .side {
      padding: clamp(20px, 3.5vw, 36px);
      display: grid;
      align-content: start;
      gap: 12px;
      background: linear-gradient(180deg, #0c131d 0%, #0b1118 100%);
    }
    .side h2 {
      margin: 0;
      font-size: 1.07rem;
      letter-spacing: -0.02em;
    }
    .side p {
      margin: 0;
      color: #93a8c2;
      font-size: 0.9rem;
      line-height: 1.45;
    }
    .link-list {
      margin: 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 8px;
    }
    .link-list a {
      color: #c6d7ed;
      text-decoration: none;
      border: 1px solid #27384d;
      border-radius: 10px;
      padding: 10px 11px;
      background: #111b29;
      display: block;
      font-size: 0.85rem;
    }
    .link-list a:hover {
      border-color: #406081;
      background: #152234;
    }
    @media (max-width: 960px) {
      .layout {
        grid-template-columns: 1fr;
      }
      .hero {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .cards {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 560px) {
      body {
        padding: 12px;
      }
      .nav {
        padding: 0 12px;
      }
      .hero,
      .side {
        padding: 16px;
      }
      .cta {
        flex-direction: column;
      }
      .btn {
        width: 100%;
        text-align: center;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="nav">
      <span class="brand">metivta.co</span>
      <a
        class="repo"
        href="https://github.com/EaCognitive/Metivta-Eval"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="GitHub Repository"
      >
        <svg class="github-icon" viewBox="0 0 16 16" aria-hidden="true">
          <path
            fill="currentColor"
            d="M8 0C3.58 0 0 3.67 0 8.2c0 3.62 2.29 6.68 5.47 7.76.4.08.55-.18.55-.39 0-.19-.01-.82-.01-1.49-2.01.38-2.53-.51-2.69-.98-.09-.24-.48-.98-.82-1.17-.28-.16-.68-.55-.01-.56.63-.01 1.08.59 1.23.83.72 1.23 1.87.88 2.33.67.07-.53.28-.88.5-1.08-1.78-.21-3.64-.91-3.64-4.04 0-.89.31-1.62.82-2.19-.08-.21-.36-1.05.08-2.18 0 0 .67-.22 2.2.84a7.38 7.38 0 0 1 4 0c1.53-1.06 2.2-.84 2.2-.84.44 1.13.16 1.97.08 2.18.51.57.82 1.29.82 2.19 0 3.14-1.87 3.83-3.65 4.04.29.25.54.73.54 1.47 0 1.06-.01 1.92-.01 2.18 0 .21.15.47.55.39A8.24 8.24 0 0 0 16 8.2C16 3.67 12.42 0 8 0Z"
          />
        </svg>
        GitHub
      </a>
    </header>
    <section class="layout">
      <article class="hero">
        <h1>Metivta Evaluation Kit</h1>
        <p class="copy">
          Deterministic evaluation harness for AI systems with hosted docs and reproducible
          benchmark scoring.
        </p>
        <section class="identity" aria-label="Author information">
          <span class="chip">Erick Aleman | AI Architect</span>
          <a class="chip" href="mailto:dev@eacognitive.com">dev@eacognitive.com</a>
        </section>
        <div class="cta">
          <a class="btn primary" href="/api/v2/docs">API Documentation</a>
          <a class="btn" href="/signup">Get an API Key</a>
        </div>
        <section class="cards" aria-label="Platform highlights">
          <article class="card">
            <strong>Hosted Gateway</strong>
            <span>Production-grade Azure container gateway with docs-first routing.</span>
          </article>
          <article class="card">
            <strong>Deterministic Scoring</strong>
            <span>DAAT and MTEB tracks optimized for reproducible benchmark output.</span>
          </article>
          <article class="card">
            <strong>Self-Hostable Harness</strong>
            <span>Use it as the baseline to run and publish your own leaderboard.</span>
          </article>
        </section>
      </article>
      <aside class="side">
        <h2>Open API Surface</h2>
        <p>Browse the Scalar reference and request credentials to start evaluating.</p>
        <ul class="link-list">
          <li><a href="/api/v2/docs">Public docs: /api/v2/docs</a></li>
          <li><a href="/api/v2/openapi.json">OpenAPI JSON: /api/v2/openapi.json</a></li>
          <li><a href="/signup">Credential flow: /signup</a></li>
        </ul>
      </aside>
    </section>
  </main>
</body>
</html>`

func main() {
	healthcheck := flag.Bool("healthcheck", false, "run healthcheck and exit")
	flag.Parse()

	listenPort := envInt("GATEWAY_PORT", 8000)
	fastAPIURL := envString("FASTAPI_URL", "http://fastapi:8001")
	flaskURL := envString("FLASK_URL", "http://flask:8080")
	publicDocsOnly := envBool("PUBLIC_DOCS_ONLY", false)

	if *healthcheck {
		if err := checkHealth(listenPort); err != nil {
			log.Fatal(err)
		}
		return
	}

	target, err := url.Parse(fastAPIURL)
	if err != nil {
		log.Fatalf("invalid FASTAPI_URL: %v", err)
	}
	flaskTarget, err := url.Parse(flaskURL)
	if err != nil {
		log.Fatalf("invalid FLASK_URL: %v", err)
	}

	fastAPIProxy := httputil.NewSingleHostReverseProxy(target)
	fastAPIDirector := fastAPIProxy.Director
	fastAPIProxy.Director = func(req *http.Request) {
		fastAPIDirector(req)
		req.Host = target.Host
	}
	proxyTransport := &http.Transport{
		ForceAttemptHTTP2:   false,
		MaxIdleConns:        100,
		IdleConnTimeout:     90 * time.Second,
		TLSHandshakeTimeout: 10 * time.Second,
		TLSNextProto:        map[string]func(string, *tls.Conn) http.RoundTripper{},
	}
	fastAPIProxy.Transport = proxyTransport
	fastAPIProxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, proxyErr error) {
		http.Error(w, proxyErr.Error(), http.StatusBadGateway)
	}
	flaskProxy := httputil.NewSingleHostReverseProxy(flaskTarget)
	flaskDirector := flaskProxy.Director
	flaskProxy.Director = func(req *http.Request) {
		flaskDirector(req)
		req.Host = flaskTarget.Host
	}
	flaskProxy.Transport = proxyTransport
	flaskProxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, proxyErr error) {
		http.Error(w, proxyErr.Error(), http.StatusBadGateway)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(
			w,
			fmt.Sprintf(
				`{"status":"healthy","service":"metivta-gateway","fastapi_target":"%s","flask_target":"%s","public_docs_only":%t}`,
				fastAPIURL,
				flaskURL,
				publicDocsOnly,
			),
		)
	})
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		if publicDocsOnly {
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(
				w,
				`{"ready":true,"checks":{"gateway":true},"details":{"mode":"public-docs-only"}}`,
			)
			return
		}
		fastAPIProxy.ServeHTTP(w, r)
	})
	mux.HandleFunc("/signup", func(w http.ResponseWriter, r *http.Request) {
		if publicDocsOnly && servePublicAsset(w, r) {
			return
		}
		http.Redirect(w, r, "/api/v2/docs", http.StatusTemporaryRedirect)
	})
	mux.HandleFunc("/leaderboard", func(w http.ResponseWriter, r *http.Request) {
		if publicDocsOnly {
			http.Redirect(w, r, "/api/v2/docs", http.StatusTemporaryRedirect)
			return
		}
		http.Redirect(w, r, "/api/v2/leaderboard/", http.StatusTemporaryRedirect)
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if publicDocsOnly && servePublicAsset(w, r) {
			return
		}
		if r.URL.Path == "/" {
			if servePublicAsset(w, r) {
				return
			}
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = io.WriteString(w, homepageHTML)
			return
		}
		if strings.HasPrefix(r.URL.Path, "/api/") {
			fastAPIProxy.ServeHTTP(w, r)
			return
		}
		http.NotFound(w, r)
	})

	address := fmt.Sprintf(":%d", listenPort)
	server := &http.Server{
		Addr:              address,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}

	log.Printf(
		"gateway listening on %s -> fastapi=%s flask=%s public_docs_only=%t",
		address,
		fastAPIURL,
		flaskURL,
		publicDocsOnly,
	)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}

func checkHealth(port int) error {
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/health", port))
	if err != nil {
		return err
	}
	defer func() {
		_ = resp.Body.Close()
	}()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("healthcheck failed with status %d", resp.StatusCode)
	}
	return nil
}

func envInt(key string, fallback int) int {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return fallback
	}
	return parsed
}

func envString(key, fallback string) string {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}
	return value
}

func envBool(key string, fallback bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(key)))
	if value == "" {
		return fallback
	}
	switch value {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}
