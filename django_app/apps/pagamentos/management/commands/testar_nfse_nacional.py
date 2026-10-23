"""Confere, sem emitir nota, se a clínica está pronta pra NFS-e no Emissor
Nacional: dados fiscais preenchidos, certificado válido e conexão autenticada
(TLS mútuo) no ambiente escolhido. Uso:

    python manage.py testar_nfse_nacional --schema=lume"""
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.core.models import ConfiguracaoClinica
from apps.pagamentos.nfse_nacional import NFSeNacionalBackend
from apps.pagamentos.notas import NotaFiscalError


class Command(BaseCommand):
    help = "Testa certificado e conexão da clínica com o Emissor Nacional da NFS-e (não emite nota)."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True, help="Schema da clínica (ex.: lume).")

    def handle(self, *args, schema, **options):
        with schema_context(schema):
            config = ConfiguracaoClinica.atual()
            faltando = [rotulo for campo, rotulo in [
                ("cnpj", "CNPJ"), ("codigo_municipio_ibge", "código IBGE do município"),
                ("nfse_codigo_tributacao_nacional", "código de tributação nacional"),
            ] if not getattr(config, campo)]
            if config.regime_tributario == "simples" and config.nfse_aliquota_simples is None:
                faltando.append("alíquota aproximada do Simples")
            if faltando:
                self.stdout.write(self.style.WARNING("Falta preencher em Clínica: " + ", ".join(faltando)))
            if not config.tem_certificado:
                raise CommandError("Certificado digital não cadastrado (Configurações da clínica).")
            try:
                self.stdout.write(self.style.SUCCESS(NFSeNacionalBackend(config).testar_conexao()))
            except NotaFiscalError as exc:
                raise CommandError(str(exc))
            except Exception as exc:
                raise CommandError(f"Falha na conexão: {exc.__class__.__name__}: {exc}")
