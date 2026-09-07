# Operations Console Deployment

The React operations console is deployed as the `frontend` Compose service.
Nginx serves the production build and proxies `/api/` to the internal FastAPI
container, so the browser uses one origin and no local Vite server is needed.

## Server update

Run from the server project directory:

```bash
git pull origin main
docker compose build api frontend
docker compose up -d postgres api frontend
docker compose ps
```

Verify the API and the page from the server:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:5173/
curl --fail http://127.0.0.1:5173/api/operations/stages
```

## Access from Windows

Keep this SSH tunnel open:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 5173:127.0.0.1:5173 <SSH_USER>@<SERVER_IP>
```

Open `http://127.0.0.1:5173/`. The page and API both come from the server.

The local Vite development server must be stopped first if it already uses
port 5173.
