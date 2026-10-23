from django.urls import path

from . import views, views_gestao as g

app_name = "estoque"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("avisos/", views.avisos, name="avisos"),
    path("ncm/busca/", views.ncm_busca, name="ncm_busca"),
    path("ncm/info/", views.ncm_info, name="ncm_info"),
    path("planilha-fiscal/", views.planilha_fiscal, name="planilha_fiscal"),
    path("planilha-fiscal/produtos.csv", views.planilha_fiscal_csv, name="planilha_fiscal_csv"),
    path("novo/", views.form_view, name="novo"),
    path("<uuid:pk>/editar/", views.form_view, name="editar"),
    path("<uuid:pk>/excluir/", views.excluir, name="excluir"),
    path("<uuid:pk>/ajustar/", views.ajustar, name="ajustar"),
    path("<uuid:pk>/movimentos/", views.movimentos, name="movimentos"),
    path("codigo/<str:codigo>/", views.codigo_lookup, name="codigo_lookup"),
    path("entrada-manual/", views.entrada_manual, name="entrada_manual"),
    path("importar-xml/", views.importar_xml, name="importar_xml"),
    # Gestão (estilo SimplesVet)
    path("saidas/", g.saidas, name="saidas"),
    path("saidas/nova/", g.saida_nova, name="saida_nova"),
    path("inventarios/", g.inventarios, name="inventarios"),
    path("inventarios/<uuid:pk>/", g.inventario, name="inventario"),
    path("inventarios/<uuid:pk>/contar/", g.inventario_contar, name="inventario_contar"),
    path("inventarios/<uuid:pk>/finalizar/", g.inventario_finalizar, name="inventario_finalizar"),
    path("analise/", g.analise, name="analise"),
    path("etiquetas/", g.etiquetas_view, name="etiquetas"),
]
