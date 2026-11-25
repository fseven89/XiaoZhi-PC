import io
import torch
from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="XiaoZhi Silero TTS v4_ru")

device = torch.device("cpu")
torch.set_num_threads(4)
importer = torch.package.PackageImporter("/app/models/v4_ru.pt")
model = importer.load_pickle("tts_models", "model")
model.to(device)

class TTSRequest(BaseModel):
    text: str
    speaker: str = "eugene"
    sample_rate: int = 24000

@app.get("/health")
def health():
    return {"status": "ok", "model": "v4_ru", "speakers": ["aidar", "baya", "kseniya", "xenia", "eugene"]}

@app.post("/tts")
def synthesize(req: TTSRequest):
    speaker = req.speaker if req.speaker in ("aidar", "baya", "kseniya", "xenia", "eugene") else "eugene"
    sr = req.sample_rate if req.sample_rate in (8000, 24000, 48000) else 24000
    buf = io.BytesIO()
    audio_path = model.save_wav(text=req.text, speaker=speaker, sample_rate=sr, audio_path="/tmp/out.wav")
    with open(audio_path, "rb") as f:
        wav_bytes = f.read()
    return Response(content=wav_bytes, media_type="audio/wav")