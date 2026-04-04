from celery import Celery
from diffusers import StableDiffusionXLPipeline
import torch
import os

celery = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# Load model globally to avoid reloading for each task
pipe = None

def get_pipe():
    global pipe
    if pipe is None:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16
        ).to("cuda")
    return pipe

@celery.task(name="worker.generate_image")
def generate_image(prompt):
    model = get_pipe()
    image = model(prompt).images[0]
    # Ensure /tmp exists (using a local path for Windows compatibility if needed, but keeping original logic)
    if not os.path.exists("./outputs"):
        os.makedirs("./outputs")
    
    safe_prompt = "".join([c for c in prompt[:10] if c.isalnum()])
    path = f"./outputs/{safe_prompt}.png"
    image.save(path)
    return path
