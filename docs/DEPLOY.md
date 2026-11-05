# Putting PaperLens online

PaperLens runs as one Python process that serves both the web page and the API, so any host that runs a Docker
container (or Python) can serve it. Nothing in this repository deploys anything by itself: each step below is one you
take in your own account.

## What changes when it is online

Set `PAPERLENS_HOSTED=1` (the Dockerfile does this). Then:

* the upload box says the file is uploaded to the server, instead of "never leaves this computer";
* each browser lists only the papers it uploaded itself (it remembers their ids), so visitors do not see each other's
  papers; the CS comparison "my papers" set and the feedback CSV are limited the same way;
* everything else (analysis, score card, highlights, feedback buttons) works as on a local install.

Optional settings:

| Variable | Effect |
|---|---|
| `PAPERLENS_PASSWORD` | Every visitor must type this password (any user name) before the page opens. Recommended for a class demo. `/api/health` stays open for the host's health check. |
| `PAPERLENS_DATA` | Where uploaded PDFs, results and feedback are stored (`/data` in the container). |
| `PORT` | The port to listen on; Render and Railway set it for you. |
| `PAPERLENS_AI_SECOND_OPINION=1`, `ANTHROPIC_API_KEY` | Turns on the optional AI second opinion (docs/AI_SECOND_OPINION.md). Build the image with `--build-arg INSTALL_AI=1`. Costs money per click and sends text to Anthropic; leave off unless you mean it. |

Limits that stay in place online: 25 MB per PDF, PDFs only, no code from the PDF is ever run. There is no per-visitor
upload quota, so use a password if the link will be shared widely.

## Option 1: Docker on any machine

```bash
docker compose up --build        # then open http://localhost:8000 (or the server's address)
```

`docker-compose.yml` keeps uploads in a named volume, so they survive restarts. Uncomment `PAPERLENS_PASSWORD` in that
file first if the machine is reachable from the internet.

## Option 2: Render (free plan, from GitHub)

1. Push this branch to your GitHub repository.
2. In Render, choose **New > Blueprint**, pick the repository; Render reads `render.yaml`.
3. Enter a value for `PAPERLENS_PASSWORD` when asked, and apply.
4. When the build finishes, open the `onrender.com` address Render shows.

Free Render services sleep after a period without visits (the first visit then takes a little while) and their disk
is wiped on every restart or redeploy, so uploaded papers and feedback votes do not last. Add a paid persistent disk
mounted at `/data` if they must.

## Option 3: Hugging Face Spaces (Docker Space)

Create a new Space of type **Docker**, upload the repository files, and add this block to the top of the Space's own
`README.md` (Spaces read the port from it):

```yaml
---
title: PaperLens AI
sdk: docker
app_port: 8000
---
```

Set `PAPERLENS_PASSWORD` under the Space's **Settings > Variables and secrets**. Space storage is also temporary unless
persistent storage is added.

## Check it after deploying

* `https://<your address>/api/health` returns `{"ok": true, "version": "1.3.0"}`.
* The page header says "online server".
* Load the synthetic demo papers, open the Score card tab and download the PDF.

## What was tested here, and what was not

Tested on this computer: the app started from exactly the files the Dockerfile copies (`tests/test_deploy.py`), the
password check, per-browser paper lists, and the hosted page in a browser. **Not tested:** building the Docker image
(Docker is not installed on this computer) and running on Render or Hugging Face. Treat the first deployment as a trial
and check the points above.
