# FaceClock Review API

Detecção de rosto, embeddings, propostas de identificação e revisão humana antes do registro de presença, com templates cifrados e trilha autenticada.

## Executar

Requisitos: Python 3.11+, FastAPI, YOLO e ONNX.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

## Funcionamento

Defina `FACECLOCK_API_KEY` com pelo menos 32 caracteres. `FACECLOCK_ENCRYPTION_KEY` e `FACECLOCK_AUDIT_KEY` recebem chaves aleatórias de 32 bytes em base64. Para visão, instale `requirements-vision.txt` e forneça modelos compatíveis em `FACECLOCK_DETECTOR` e `FACECLOCK_ENCODER`. Pesos e validação de acurácia não estão incluídos. Cadastro exige consentimento e 3 a 8 imagens. `/v1/export` gera o relatório. Revogação exclui templates.

## Persistência de resultados

O arquivo de operações está em [vercel-home-telemetry-api.vercel.app](https://vercel-home-telemetry-api.vercel.app/laboratory.html?project=faceclock-yolo). As migrações Supabase estão no [repositório da API](https://github.com/brunnojob/vercel-home-telemetry-api/tree/main/supabase/migrations).

```sh
python cloud/sync.py enqueue resultado.json --project faceclock-yolo
python cloud/sync.py sync
```

Defina `BRUNNODEV_ACCESS_TOKEN` com sua sessão. A fila SQLite conserva os relatórios até confirmação do servidor; o mesmo conteúdo não gera registros duplicados. Tokens não são gravados no código.
