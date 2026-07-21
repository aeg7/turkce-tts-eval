# test_w2v2.py — wav2vec2 tek dosya sadakat testi
import sys
import librosa
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

MODEL = "mpoyraz/wav2vec2-xls-r-300m-cv8-turkish"

def transcribe_w2v2(wav_path):
    # 1) sesi 16kHz mono oku (wav2vec2 bunu ister)
    ses, _ = librosa.load(wav_path, sr=16000)
    # 2) modeli + işlemciyi yükle (ilk koşuda ~1.2GB iner)
    processor = Wav2Vec2Processor.from_pretrained(MODEL)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL)
    # 3) sesi modele ver
    girdi = processor(ses, sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        logits = model(girdi).logits
    # 4) CTC çözümü: en olası harf dizisi
    ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(ids)[0]

if __name__ == "__main__":
    wav = sys.argv[1]
    print("DOSYA :", wav)
    print("wav2vec2:", transcribe_w2v2(wav))
