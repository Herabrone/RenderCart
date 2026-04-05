# RenderCart API Integration Guide (Stockman App)

Welcome to the RenderCart Image Generation API. This API allows external services (like your Stockman Shopify App) to generate high-quality product contextual images using GPU-accelerated Stable Diffusion.

## Base URL
Local Dev: `http://localhost:8000/api/v1`
Production: `https://api.rendercart.io/v1`

## Authentication
Authentication is via `X-API-Key` header.
Example:
```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api.rendercart.io/v1/health
```

## Generation Endpoint
**POST** `/generate`

**Payload:**
```json
{
  "image_url": "https://your-shopify-store.com/images/bag.jpg",
  "prompt": "On a minimal wooden pedestal in a designer boutique with high-end lighting",
  "style": "realistic",
  "num_outputs": 2,
  "callback_url": "https://stockman-app.io/webhooks/images"
}
```

**Fields:**
- `image_url` (Required): Public URL of the product image. The background will be removed automatically.
- `prompt` (Required): Text describing the environment for the product.
- `style` (Optional): One of `realistic`, `cartoon`, `anime`, `watercolor`, `sketch`. Default: `realistic`.
- `num_outputs` (Optional): Number of variations (1-4). Default: 1.
- `callback_url` (Optional): A webhook URL that RenderCart will call when the images are ready.

---

## Webhook Callback Format
When the job is complete, RenderCart sends a **POST** request to your `callback_url` with the following body:

**Success:**
```json
{
  "job_id": "job_business_12345",
  "status": "completed",
  "images": [
    "https://storage.rendercart.io/business_12345/job_abc/image_1.png",
    "https://storage.rendercart.io/business_12345/job_abc/image_2.png"
  ]
}
```

**Failure:**
```json
{
  "job_id": "job_business_12345",
  "status": "failed",
  "error": "Reason for failure..."
}
```

## Status Polling (Fallback)
**GET** `/job/{job_id}`

Retrieve the current status and image URLs manually.

---

## Interactive Documentation
Swagger UI is available at: `/docs`
Redoc is available at: `/redoc`

*Contact darja@rendercart.io for production API access.*
