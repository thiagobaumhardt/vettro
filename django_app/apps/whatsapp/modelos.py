"""Templates (modelos de mensagem) que o Vettro cria na WABA de cada clínica
ao conectar. Fora da janela de 24h (lembrete: a clínica puxa a conversa) a
Meta só aceita template pré-aprovado — texto livre é recusado.

Regras da Meta seguidas aqui: corpo não começa nem termina com variável,
variáveis não ficam coladas umas nas outras, exemplo obrigatório pra cada
variável, e o valor da variável não pode ter quebra de linha/tab nem mais de
4 espaços seguidos (ver `limpar_parametro`).

O aviso pode levar uma imagem: é outro template (`vettro_aviso_imagem`),
com cabeçalho IMAGE. A Meta exige uma imagem de exemplo pra aprovar o
template (EXEMPLO_IMAGEM); a imagem de verdade vai em cada envio.

Negrito/itálico/tachado são a formatação do próprio WhatsApp (*texto*,
_texto_, ~texto~) e funcionam dentro das variáveis.

Categoria define o preço (Brasil, 2026): UTILITY ~US$0,007 por mensagem,
MARKETING ~US$0,06. Lembrete de agenda/vacina/retorno é UTILITY; o aviso
livre do menu Lembretes é MARKETING (texto escolhido pela clínica — campanha,
promoção — a Meta recategoriza se enviar como utility)."""
import re
from dataclasses import dataclass
from pathlib import Path

IDIOMA = "pt_BR"
RODAPE = "Para não receber mais, responda SAIR."
EXEMPLO_IMAGEM = Path(__file__).resolve().parent / "exemplo_aviso.png"


@dataclass(frozen=True)
class Modelo:
    nome: str
    rotulo: str
    categoria: str
    corpo: str
    exemplo: tuple
    cabecalho: str = ""  # "IMAGE" = mensagem com imagem no topo

    def renderizar(self, parametros) -> str:
        texto = self.corpo
        for i, valor in enumerate(parametros, start=1):
            texto = texto.replace(f"{{{{{i}}}}}", str(valor))
        return texto

    def payload_criacao(self, handle_exemplo: str = "") -> dict:
        """`handle_exemplo`: imagem de exemplo já enviada à Meta (meta.subir_exemplo)."""
        componentes = [
            {"type": "BODY", "text": self.corpo, "example": {"body_text": [list(self.exemplo)]}},
            {"type": "FOOTER", "text": RODAPE},
        ]
        if self.cabecalho:
            componentes.insert(0, {"type": "HEADER", "format": self.cabecalho, "example": {"header_handle": [handle_exemplo]}})
        return {"name": self.nome, "language": IDIOMA, "category": self.categoria, "components": componentes}


AGENDAMENTO = Modelo(
    nome="vettro_lembrete_agendamento",
    rotulo="Lembrete de agendamento",
    categoria="UTILITY",
    corpo="Olá, {{1}}! Aqui é da {{2}}. Passando para lembrar do agendamento de {{3}} para {{4}}. Até lá!",
    exemplo=("Ana", "Clínica Lume", "Thor", "amanhã, 20/10, às 14:30"),
)
VACINA = Modelo(
    nome="vettro_lembrete_vacina",
    rotulo="Lembrete de vacina",
    categoria="UTILITY",
    corpo=(
        "Olá, {{1}}! Aqui é da {{2}}. A próxima dose da vacina {{3}} de {{4}} está prevista para {{5}}. "
        "Responda esta mensagem para agendar."
    ),
    exemplo=("Ana", "Clínica Lume", "V10", "Thor", "20/10/2026"),
)
RETORNO = Modelo(
    nome="vettro_lembrete_retorno",
    rotulo="Lembrete de retorno",
    categoria="UTILITY",
    corpo="Olá, {{1}}! Aqui é da {{2}}. O retorno de {{3}} está previsto para {{4}}. Responda esta mensagem para agendar.",
    exemplo=("Ana", "Clínica Lume", "Thor", "20/10/2026"),
)
AVISO = Modelo(
    nome="vettro_aviso",
    rotulo="Aviso (menu Lembretes)",
    categoria="MARKETING",
    corpo="Olá, {{1}}! A {{2}} enviou uma mensagem para você: {{3}} Qualquer dúvida, é só responder.",
    exemplo=("Ana", "Clínica Lume", "A campanha de vacinação antirrábica começa segunda-feira."),
)

AVISO_IMAGEM = Modelo(
    nome="vettro_aviso_imagem",
    rotulo="Aviso com imagem (menu Lembretes)",
    categoria="MARKETING",
    corpo=AVISO.corpo,
    exemplo=AVISO.exemplo,
    cabecalho="IMAGE",
)

MODELOS = {m.nome: m for m in (AGENDAMENTO, VACINA, RETORNO, AVISO, AVISO_IMAGEM)}


def limpar_parametro(valor) -> str:
    texto = re.sub(r"[\r\n\t]+", " ", str(valor or ""))
    return re.sub(r" {4,}", "   ", texto).strip() or "-"


def _primeiro_nome(nome: str) -> str:
    return (nome or "").split(" ")[0] or "tutor(a)"


def parametros_agendamento(agendamento, clinica_nome: str) -> list:
    quando = f"amanhã, {agendamento.data:%d/%m}"
    if agendamento.hora:
        quando += f", às {agendamento.hora:%H:%M}"
    return [_primeiro_nome(agendamento.tutor_nome), clinica_nome, agendamento.pac_nome, quando]


def parametros_vacina(atendimento, clinica_nome: str) -> list:
    tutor = atendimento.paciente.tutor if atendimento.paciente_id else None
    return [
        _primeiro_nome(tutor.nome if tutor else ""), clinica_nome, atendimento.vacina_nome,
        atendimento.pac_nome, f"{atendimento.data_proxima_dose:%d/%m/%Y}",
    ]


def parametros_retorno(atendimento, clinica_nome: str) -> list:
    tutor = atendimento.paciente.tutor if atendimento.paciente_id else None
    return [_primeiro_nome(tutor.nome if tutor else ""), clinica_nome, atendimento.pac_nome, f"{atendimento.data_retorno:%d/%m/%Y}"]


def parametros_aviso(tutor, clinica_nome: str, texto: str) -> list:
    return [_primeiro_nome(tutor.nome), clinica_nome, texto]
