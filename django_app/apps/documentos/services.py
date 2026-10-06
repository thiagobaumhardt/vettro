import re
from datetime import date

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from apps.core.models import ConfiguracaoClinica, PerfilProfissional
from apps.core.pdf import ESTILOS, assinatura_do_usuario, data_por_extenso, gerar_pdf, paragrafos

from .models import DocumentoEmitido

# Variáveis aceitas nos modelos → descrição (mostrada na tela de edição).
VARIAVEIS = {
    "paciente": "Nome do paciente",
    "especie": "Espécie",
    "raca": "Raça",
    "idade": "Idade",
    "data_nascimento": "Data de nascimento",
    "peso": "Peso",
    "tutor": "Nome do tutor",
    "tutor_cpf": "CPF do tutor",
    "tutor_telefone": "WhatsApp do tutor",
    "tutor_endereco": "Endereço do tutor",
    "clinica": "Nome da clínica",
    "veterinario": "Nome do veterinário que emite",
    "crmv": "CRMV do veterinário",
    "data": "Data de hoje por extenso",
    "data_curta": "Data de hoje (dd/mm/aaaa)",
}
LACUNA = "__________"


def valores_variaveis(*, paciente, usuario, clinica_nome: str) -> dict:
    tutor = paciente.tutor
    perfil = PerfilProfissional.de(usuario)
    hoje = date.today()
    valores = {
        "paciente": paciente.nome,
        "especie": paciente.get_especie_display(),
        "raca": paciente.raca,
        "idade": paciente.idade_texto if paciente.data_nascimento else "",
        "data_nascimento": f"{paciente.data_nascimento:%d/%m/%Y}" if paciente.data_nascimento else "",
        "peso": f"{paciente.peso} kg" if paciente.peso else "",
        "tutor": tutor.nome if tutor else "",
        "tutor_cpf": tutor.cpf if tutor else "",
        "tutor_telefone": tutor.tel if tutor else "",
        "tutor_endereco": tutor.endereco_completo if tutor else "",
        "clinica": clinica_nome,
        "veterinario": perfil.nome_completo or usuario.nome,
        "crmv": perfil.crmv_formatado,
        "data": data_por_extenso(hoje),
        "data_curta": f"{hoje:%d/%m/%Y}",
    }
    # Dado que não existe no cadastro vira lacuna pra preencher à mão.
    return {chave: (valor or LACUNA) for chave, valor in valores.items()}


def preencher(texto: str, valores: dict) -> str:
    """Troca só as {variáveis} conhecidas — qualquer outra chave fica como está."""
    return re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), texto)


def emitir(*, paciente, modelo, titulo, texto, usuario) -> DocumentoEmitido:
    perfil = PerfilProfissional.de(usuario)
    return DocumentoEmitido.objects.create(
        paciente=paciente, modelo=modelo, titulo=titulo.strip()[:120], texto=texto,
        pac_nome=paciente.nome, vet_usuario_id=usuario.id,
        vet_nome=perfil.nome_completo or usuario.nome, vet_crmv=perfil.crmv_formatado,
    )


def pdf_documento(documento: DocumentoEmitido, *, clinica_nome: str) -> bytes:
    corpo = [Paragraph(documento.titulo, ESTILOS["titulo"]), Spacer(1, 0.3 * cm)]
    corpo += paragrafos(documento.texto)
    corpo += assinatura_do_usuario(documento.vet_usuario_id, nome=documento.vet_nome, crmv=documento.vet_crmv)
    return gerar_pdf(
        titulo_documento=f"{documento.titulo} · {documento.pac_nome}", clinica_nome=clinica_nome,
        config=ConfiguracaoClinica.atual(), flowables=corpo,
    )
