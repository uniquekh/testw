# Notes API for Render

Flask API to fetch notes and PYQs with Cloudflare bypass.

## Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `GET /api/notes?batch_id=<id>&topic_id=<id>` - Fetch notes

## Deploy to Render

1. Push code to GitHub
2. Connect repository in Render dashboard
3. Render will auto-detect `render.yaml`
4. Deploy!

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

API runs on `http://localhost:5000`

## Example Usage

```bash
curl "https://your-app.onrender.com/api/notes?batch_id=123&topic_id=456"
```
