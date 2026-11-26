"""RF14/RF15 — situação atual e histórico de trânsito de um cruzamento."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import RegraDeNegocioViolada
from app.db.types import agora_utc
from app.models import ModoOperacao, StatusSemaforo
from app.repositories.ciclo_repository import CicloRepository
from app.repositories.falha_repository import FalhaRepository
from app.repositories.leitura_repository import LeituraRepository
from app.repositories.via_repository import ViaRepository
from app.schemas.consulta import (
    EstatisticaVia,
    HistoricoRead,
    ResumoCiclo,
    SituacaoRead,
    UltimaLeitura,
    ViaSituacao,
)
from app.services.cruzamento_service import CruzamentoService
from app.services.parametro_service import ParametroService

PERIODO_PADRAO = timedelta(hours=24)


class ConsultaService:
    def __init__(self, db: Session) -> None:
        self.cruzamentos = CruzamentoService(db)
        self.vias = ViaRepository(db)
        self.leituras = LeituraRepository(db)
        self.ciclos = CicloRepository(db)
        self.falhas = FalhaRepository(db)
        self.parametros = ParametroService(db)

    def situacao(self, cruzamento_id: int) -> SituacaoRead:
        cruzamento = self.cruzamentos.obter(cruzamento_id)
        agora = agora_utc()
        parametros = self.parametros.obter()
        limite = timedelta(seconds=parametros.tempo_maximo_sem_leitura)
        faixas = self.parametros.faixas()

        vias = self.vias.listar_por_cruzamento(cruzamento_id)
        ultimas = self.leituras.ultimas_por_via([via.id for via in vias])
        ultimo_ciclo = self.ciclos.ultimo(cruzamento_id)
        verdes = {t.via_id: t.tempo_verde for t in ultimo_ciclo.tempos} if ultimo_ciclo else {}

        itens = []
        for via in vias:
            ultima = ultimas.get(via.id)
            desatualizada = ultima is None or agora - ultima.data_hora > limite
            itens.append(
                ViaSituacao(
                    via_id=via.id,
                    nome=via.nome,
                    direcao=via.direcao,
                    quantidade_faixas=via.quantidade_faixas,
                    estagio=via.estagio,
                    semaforo_id=via.semaforo.id if via.semaforo else None,
                    status_semaforo=via.semaforo.status if via.semaforo else None,
                    ultima_leitura=(
                        UltimaLeitura(
                            quantidade_veiculos=ultima.quantidade_veiculos,
                            data_hora=ultima.data_hora,
                        )
                        if ultima
                        else None
                    ),
                    leitura_desatualizada=desatualizada,
                    classificacao_fluxo=(
                        faixas.classificar(ultima.quantidade_veiculos, via.quantidade_faixas)
                        if ultima
                        else None
                    ),
                    tempo_verde_recomendado=verdes.get(via.id),
                )
            )
        # Mesmo critério do cálculo: alguma via com semáforo ativo sem leitura recente
        monitoradas = [
            item
            for item, via in zip(itens, vias, strict=True)
            if via.semaforo and via.semaforo.status == StatusSemaforo.ATIVO
        ]
        contingencia = any(item.leitura_desatualizada for item in monitoradas)
        return SituacaoRead(
            cruzamento_id=cruzamento.id,
            nome=cruzamento.nome,
            status=cruzamento.status,
            regra_temporizacao=cruzamento.regra_temporizacao,
            modo_operacao=ModoOperacao.CONTINGENCIA if contingencia else ModoOperacao.ADAPTATIVO,
            consultado_em=agora,
            total_veiculos=sum(leitura.quantidade_veiculos for leitura in ultimas.values()),
            ultimo_ciclo=(
                ResumoCiclo(
                    id=ultimo_ciclo.id,
                    data_hora_inicio=ultimo_ciclo.data_hora_inicio,
                    origem=ultimo_ciclo.origem,
                    duracao_total=ultimo_ciclo.duracao_total,
                    total_veiculos=ultimo_ciclo.total_veiculos,
                )
                if ultimo_ciclo
                else None
            ),
            falhas_abertas=self.falhas.contar_abertas(cruzamento_id),
            vias=itens,
        )

    def historico(
        self, cruzamento_id: int, inicio: datetime | None, fim: datetime | None
    ) -> HistoricoRead:
        self.cruzamentos.obter(cruzamento_id)
        fim = fim or agora_utc()
        inicio = inicio or fim - PERIODO_PADRAO
        if inicio > fim:
            raise RegraDeNegocioViolada("O parâmetro 'inicio' deve ser anterior a 'fim'")

        vias = self.vias.listar_por_cruzamento(cruzamento_id)
        estatisticas = self.leituras.estatisticas_por_via([via.id for via in vias], inicio, fim)
        itens = []
        for via in vias:
            quantidade, media, minimo, maximo, ultima = estatisticas.get(
                via.id, (0, None, None, None, None)
            )
            itens.append(
                EstatisticaVia(
                    via_id=via.id,
                    nome=via.nome,
                    quantidade_leituras=quantidade,
                    media_veiculos=round(float(media), 2) if media is not None else None,
                    minimo_veiculos=minimo,
                    maximo_veiculos=maximo,
                    ultima_leitura_em=ultima,
                )
            )
        quantidade_ciclos, duracao_media = self.ciclos.resumo_periodo(cruzamento_id, inicio, fim)
        return HistoricoRead(
            cruzamento_id=cruzamento_id,
            inicio=inicio,
            fim=fim,
            quantidade_leituras=sum(item.quantidade_leituras for item in itens),
            quantidade_ciclos=quantidade_ciclos,
            duracao_media_ciclo=round(duracao_media, 2) if duracao_media is not None else None,
            vias=itens,
        )
