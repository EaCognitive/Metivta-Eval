package main

import (
	"bytes"
	"embed"
	"io/fs"
	"mime"
	"net/http"
	"path/filepath"
	"time"
)

//go:embed public
var publicSite embed.FS

var publicSiteFS = mustSubFS(publicSite, "public")

func mustSubFS(root embed.FS, path string) fs.FS {
	sub, err := fs.Sub(root, path)
	if err != nil {
		panic(err)
	}
	return sub
}

func publicAssetPath(path string) (string, bool) {
	switch path {
	case "/", "":
		return "index.html", true
	case "/guide", "/guide/":
		return "guide/index.html", true
	case "/signup", "/signup/":
		return "signup/index.html", true
	case "/api/v2/docs", "/api/v2/docs/":
		return "api/v2/docs/index.html", true
	case "/api/v2/openapi.json":
		return "api/v2/openapi.json", true
	default:
		return "", false
	}
}

func servePublicAsset(w http.ResponseWriter, r *http.Request) bool {
	path, ok := publicAssetPath(r.URL.Path)
	if !ok {
		return false
	}
	content, err := fs.ReadFile(publicSiteFS, path)
	if err != nil {
		http.NotFound(w, r)
		return true
	}
	contentType := mime.TypeByExtension(filepath.Ext(path))
	if contentType == "" && filepath.Ext(path) == ".html" {
		contentType = "text/html; charset=utf-8"
	}
	if contentType != "" {
		w.Header().Set("Content-Type", contentType)
	}
	http.ServeContent(w, r, path, time.Time{}, bytes.NewReader(content))
	return true
}
