import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import DEFAULT_ADMIN_SENHA, DEFAULT_JWT_SECRET, settings
from .routers import (
    agendamentos,
    anamnese,
    atendimentos,
    auth,
    cirurgias,
    cirurgias_cat,
    cobrancas,
    dashboard,
    exames,
    fotos,
    insumos,
    notas,
    pacientes,
    servicos,
    tutores,
    usuarios,
)

logger = logging.getLogger("vettro")

app = FastAPI(title="Vettro API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins] if settings.cors_origins != "*" else ["*"],
    # Autenticação é via Bearer token (não cookies), então não precisamos de credentials
    # e podemos manter allow_origins="*" válido em dev.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _avisa_configuracao_insegura():
    if settings.jwt_secret == DEFAULT_JWT_SECRET:
        logger.warning("JWT_SECRET está com o valor padrão de exemplo — troque-o antes de expor em produção.")
    if settings.admin_senha == DEFAULT_ADMIN_SENHA:
        logger.warning("ADMIN_SENHA está com o valor padrão de exemplo — troque-o antes de expor em produção.")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


for router in (
    auth.router,
    usuarios.router,
    tutores.router,
    pacientes.router,
    servicos.router,
    cirurgias_cat.router,
    insumos.router,
    anamnese.router,
    cirurgias.router,
    notas.router,
    exames.router,
    fotos.router,
    cobrancas.router,
    atendimentos.router,
    agendamentos.router,
    dashboard.router,
):
    app.include_router(router)


# Em produção (imagem Dockerfile.prod) o build do Vue é copiado para /app/static e servido
# pelo próprio FastAPI. Em dev, esse diretório não existe (o frontend roda no Vite separado),
# então o mount é condicional para não quebrar o startup local.
_STATIC_DIR = "/app/static"
if os.path.isdir(_STATIC_DIR):
    _ASSETS_DIR = os.path.join(_STATIC_DIR, "assets")
    if os.path.isdir(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    _INDEX_HTML = os.path.join(_STATIC_DIR, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Um path /api/... que não bateu em nenhum router acima é um endpoint inexistente de
        # verdade — deve virar 404, não a página do SPA (senão erros de API viram 200 mascarados).
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Rota não encontrada.")
        # Serve o arquivo estático se ele existir (favicon, manifest, etc.); caso contrário
        # devolve index.html para o Vue Router (modo history) resolver a rota no cliente —
        # sem isso, recarregar a página em /pacientes/123 daria 404.
        candidato = os.path.join(_STATIC_DIR, full_path)
        if full_path and os.path.isfile(candidato):
            return FileResponse(candidato)
        return FileResponse(_INDEX_HTML)
