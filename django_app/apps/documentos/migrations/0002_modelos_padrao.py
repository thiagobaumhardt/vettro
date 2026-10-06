"""Modelos de documento com que toda clínica começa (roda em cada schema,
inclusive clínicas provisionadas depois). São pontos de partida — a clínica
deve revisar os textos com o seu responsável técnico; exigências de viagem
internacional, em especial, variam por país de destino."""
from django.db import migrations

MODELOS = {
    "Atestado de saúde para viagem nacional": """Atesto, para os devidos fins, que examinei nesta data o animal abaixo identificado, que se encontra clinicamente sadio, sem sinais de doenças infectocontagiosas ou parasitárias, estando apto a viajar.

Nome: {paciente}
Espécie: {especie} · Raça: {raca}
Idade: {idade} · Peso: {peso}
Sexo: __________ · Pelagem: __________ · Microchip: __________

Tutor(a): {tutor} · CPF: {tutor_cpf}
Endereço: {tutor_endereco}

Vacinação antirrábica: aplicada em __________ (vacina __________, lote __________).

Destino: __________ · Meio de transporte: __________

Este atestado tem validade de 10 (dez) dias a partir da data de emissão.

{data}""",

    "Atestado de saúde para viagem internacional": """Atesto, para fins de solicitação do Certificado Veterinário Internacional (CVI) junto ao Ministério da Agricultura e Pecuária (MAPA/VIGIAGRO), que examinei nesta data o animal abaixo identificado, que se encontra clinicamente sadio, sem sinais de doenças infectocontagiosas ou parasitárias, estando apto a viajar.

Nome: {paciente}
Espécie: {especie} · Raça: {raca}
Data de nascimento: {data_nascimento} · Peso: {peso}
Sexo: __________ · Pelagem: __________
Microchip nº: __________ · Data de implantação: __________

Tutor(a): {tutor} · CPF/Passaporte: {tutor_cpf}
Endereço: {tutor_endereco}

País de destino: __________ · Data prevista do embarque: __________

Vacinação antirrábica: aplicada em __________ (vacina __________, lote __________).
Sorologia antirrábica (quando exigida): __________
Tratamento antiparasitário interno/externo: __________ em __________

Declaro que o animal atende às exigências sanitárias do país de destino, conforme informado pelo tutor e verificado nesta avaliação.

{data}""",

    "Termo de consentimento para cirurgia e anestesia": """Eu, {tutor}, CPF {tutor_cpf}, residente em {tutor_endereco}, tutor(a) responsável pelo animal {paciente} ({especie}, {raca}, {idade}, {peso}), autorizo a equipe da {clinica} a realizar o(s) procedimento(s) de __________, bem como a anestesia necessária.

Declaro que fui informado(a) de forma clara sobre o diagnóstico, os objetivos do procedimento, as alternativas de tratamento e os riscos envolvidos, inclusive os inerentes à anestesia, que podem levar a complicações e, em casos raros, ao óbito, mesmo com todos os cuidados técnicos adotados.

Autorizo ainda procedimentos adicionais que se mostrarem necessários durante a cirurgia para preservar a vida e o bem-estar do animal, comprometendo-me a arcar com os custos correspondentes.

Estou ciente das orientações de jejum e dos cuidados pós-operatórios.

{data}


_______________________________________
{tutor} — Tutor(a) responsável""",

    "Termo de consentimento para eutanásia": """Eu, {tutor}, CPF {tutor_cpf}, residente em {tutor_endereco}, tutor(a) responsável pelo animal {paciente} ({especie}, {raca}, {idade}), declaro que fui esclarecido(a) pelo(a) médico(a) veterinário(a) {veterinario} sobre o estado de saúde do animal, o prognóstico e as alternativas existentes.

De forma livre e consciente, autorizo a realização da eutanásia, a ser realizada conforme as normas do Conselho Federal de Medicina Veterinária, por método que garanta a ausência de dor e sofrimento.

Destinação do corpo: ( ) cremação individual ( ) cremação coletiva ( ) sepultamento pelo tutor ( ) outro: __________

{data}


_______________________________________
{tutor} — Tutor(a) responsável""",

    "Declaração de óbito": """Declaro, para os devidos fins, que o animal abaixo identificado veio a óbito.

Nome: {paciente}
Espécie: {especie} · Raça: {raca}
Idade: {idade}
Tutor(a): {tutor} · CPF: {tutor_cpf}

Data do óbito: __________ · Hora: __________
Local: __________
Causa provável: __________

{data}""",

    "Termo de responsabilidade para internação": """Eu, {tutor}, CPF {tutor_cpf}, telefone {tutor_telefone}, tutor(a) responsável pelo animal {paciente} ({especie}, {raca}, {peso}), autorizo a internação na {clinica} para tratamento de __________.

Estou ciente de que o quadro clínico pode evoluir de forma imprevisível, de que procedimentos e exames adicionais poderão ser necessários, e de que serei informado(a) sobre o estado do animal pelos contatos acima. Comprometo-me a arcar com os custos da internação e do tratamento.

Previsão de alta: __________

{data}


_______________________________________
{tutor} — Tutor(a) responsável""",

    "Atestado de vacinação": """Atesto, para os devidos fins, que o animal abaixo identificado foi vacinado nesta clínica.

Nome: {paciente}
Espécie: {especie} · Raça: {raca} · Idade: {idade}
Tutor(a): {tutor} · CPF: {tutor_cpf}

Vacina: __________ · Laboratório: __________ · Lote: __________
Data de aplicação: __________ · Próxima dose: __________

{data}""",
}


def criar_modelos(apps, schema_editor):
    ModeloDocumento = apps.get_model("documentos", "ModeloDocumento")
    for nome, texto in MODELOS.items():
        ModeloDocumento.objects.get_or_create(nome=nome, defaults={"texto": texto})


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_modelos, migrations.RunPython.noop),
    ]
