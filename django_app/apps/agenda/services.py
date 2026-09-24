"""Porte de backend/app/routers/agendamentos.py:_resolver_paciente — quando
um paciente cadastrado é escolhido, pac_nome/tutor_nome/tutor_tel vêm do
cadastro (sobrescrevendo o que veio no formulário); paciente avulso usa os
campos livres do formulário."""


def resolver_paciente(*, paciente, pac_nome: str, tutor_nome: str, tutor_tel: str) -> dict:
    if paciente:
        return {
            "paciente": paciente,
            "pac_nome": paciente.nome,
            "tutor_nome": paciente.tutor.nome if paciente.tutor else "",
            "tutor_tel": paciente.tutor.tel if paciente.tutor else "",
        }
    return {"paciente": None, "pac_nome": pac_nome, "tutor_nome": tutor_nome, "tutor_tel": tutor_tel}
