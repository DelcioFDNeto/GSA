"""Cálculo e gravação de ciclos semafóricos (RF06–RF13).

Faz a ponte entre o banco e o motor de cálculo: monta as entradas a partir da última leitura e
do semáforo de cada via, chama o motor e grava o ciclo com o tempo de cada semáforo.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.eventos import canal
from app.core.exceptions import RecursoNaoEncontrado, RegraDeNegocioViolada
from app.db.types import agora_utc
from app.models import (
    CicloSemaforico,
    Cruzamento,
    ModoOperacao,
    OrigemCiclo,
    StatusCruzamento,
    StatusSemaforo,
    TempoSemaforico,
    Via,
)
from app.motor import EntradaVia, PlanoFixo, ResultadoCalculo, calcular_ciclo
from app.repositories.ciclo_repository import CicloRepository
from app.repositories.leitura_repository import LeituraRepository
from app.repositories.via_repository import ViaRepository
from app.schemas.ciclo import CicloGeradoRead, CicloRead, TempoRead, ViaIgnorada
from app.services.cruzamento_service import CruzamentoService
from app.services.parametro_service import ParametroService


@dataclass
class CalculoPreparado:
    cruzamento: Cruzamento
    resultado: ResultadoCalculo
    vias: dict[int, Via]
    ignoradas: list[ViaIgnorada]
    modo: ModoOperacao
    motivo_contingencia: str | None


class CicloService:
    def __init__(self, db: Session) -> None:
        self.repo = CicloRepository(db)
        self.cruzamentos = CruzamentoService(db)
        self.vias = ViaRepository(db)
        self.leituras = LeituraRepository(db)
        self.parametros = ParametroService(db)

    def calcular(self, cruzamento_id: int, momento: datetime | None = None) -> CalculoPreparado:
        """Monta as entradas e escolhe a regra: a do cruzamento ou, se alguma via estiver sem
        leitura recente, o plano fixo do modo de segurança."""
        cruzamento = self.cruzamentos.obter(cruzamento_id)
        if cruzamento.status != StatusCruzamento.ATIVO:
            raise RegraDeNegocioViolada(f"Cruzamento {cruzamento_id} está inativo")

        todas = self.vias.listar_por_cruzamento(cruzamento_id)
        ultimas = self.leituras.ultimas_por_via([via.id for via in todas])
        entradas: list[EntradaVia] = []
        calculaveis: dict[int, Via] = {}
        ignoradas: list[ViaIgnorada] = []
        parametros = self.parametros.obter()
        referencia = momento or agora_utc()
        limite = timedelta(seconds=parametros.tempo_maximo_sem_leitura)
        sem_leitura_recente: list[str] = []
        for via in todas:
            semaforo = via.semaforo
            if semaforo is None:
                ignoradas.append(ViaIgnorada(via_id=via.id, motivo="via sem semáforo cadastrado"))
                continue
            if semaforo.status != StatusSemaforo.ATIVO:
                ignoradas.append(
                    ViaIgnorada(via_id=via.id, motivo=f"semáforo com status '{semaforo.status}'")
                )
                continue
            ultima = ultimas.get(via.id)
            if ultima is None or referencia - ultima.data_hora > limite:
                sem_leitura_recente.append(via.nome)
            entradas.append(
                EntradaVia(
                    via_id=via.id,
                    quantidade_veiculos=ultima.quantidade_veiculos if ultima else 0,
                    quantidade_faixas=via.quantidade_faixas,
                    tempo_minimo_verde=semaforo.tempo_minimo_verde,
                    tempo_maximo_verde=semaforo.tempo_maximo_verde,
                    tempo_amarelo=semaforo.tempo_amarelo,
                    tempo_vermelho=semaforo.tempo_vermelho,
                    estagio=via.estagio,
                )
            )
            calculaveis[via.id] = via

        if not entradas:
            raise RegraDeNegocioViolada(
                f"Cruzamento {cruzamento_id} não possui vias com semáforo ativo para calcular"
            )
        duracao = cruzamento.duracao_ciclo or parametros.duracao_ciclo
        if sem_leitura_recente:
            modo = ModoOperacao.CONTINGENCIA
            regra = PlanoFixo()
            motivo = (
                f"Sem leitura nos últimos {parametros.tempo_maximo_sem_leitura} s: "
                + ", ".join(sem_leitura_recente)
                + ". Aplicado o plano fixo até as leituras voltarem."
            )
        else:
            modo, regra, motivo = (
                ModoOperacao.ADAPTATIVO,
                self.parametros.regra_para(cruzamento),
                None,
            )
        resultado = calcular_ciclo(entradas, duracao, self.parametros.faixas(), regra)
        return CalculoPreparado(cruzamento, resultado, calculaveis, ignoradas, modo, motivo)

    def gerar(
        self,
        cruzamento_id: int,
        origem: OrigemCiclo,
        persistir: bool = True,
        momento: datetime | None = None,
    ) -> CicloGeradoRead:
        """Calcula o ciclo e, se `persistir`, grava no histórico (RF12/RF13)."""
        preparado = self.calcular(cruzamento_id, momento)
        r = preparado.resultado
        ciclo = CicloSemaforico(
            cruzamento_id=cruzamento_id,
            data_hora_inicio=momento or agora_utc(),
            origem=origem,
            modo_operacao=preparado.modo,
            regra_aplicada=r.regra,
            duracao_ciclo_configurada=r.duracao_ciclo_configurada,
            verde_disponivel=r.verde_disponivel,
            duracao_total=r.duracao_total,
            total_veiculos=sum(t.quantidade_veiculos for t in r.tempos),
            grau_saturacao=r.grau_saturacao,
            tempos=[
                TempoSemaforico(
                    semaforo_id=preparado.vias[t.via_id].semaforo.id,
                    via_id=t.via_id,
                    via=preparado.vias[t.via_id],
                    quantidade_veiculos=t.quantidade_veiculos,
                    demanda_percentual=round(t.demanda * 100, 1),
                    classificacao_fluxo=t.classificacao.value,
                    tempo_verde=t.tempo_verde,
                    tempo_amarelo=t.tempo_amarelo,
                    tempo_vermelho=t.tempo_vermelho,
                    ajuste_aplicado=t.ajuste.value,
                )
                for t in r.tempos
            ],
        )
        if persistir:
            ciclo = self.repo.adicionar(ciclo)
        else:
            # Prévia: o objeto não entra na sessão, então nada é gravado
            ciclo.id = None
        base = self.para_schema(ciclo, persistido=persistir)
        gerado = CicloGeradoRead(
            **base.model_dump(),
            vias_ignoradas=preparado.ignoradas,
            motivo_contingencia=preparado.motivo_contingencia,
        )
        if persistir:
            canal.publicar("ciclo", gerado.model_dump(mode="json", by_alias=True))
        return gerado

    def listar(
        self,
        cruzamento_id: int,
        inicio: datetime | None,
        fim: datetime | None,
        limite: int,
    ) -> list[CicloRead]:
        self.cruzamentos.obter(cruzamento_id)
        if inicio and fim and inicio > fim:
            raise RegraDeNegocioViolada("O parâmetro 'inicio' deve ser anterior a 'fim'")
        return [self.para_schema(c) for c in self.repo.listar(cruzamento_id, inicio, fim, limite)]

    def obter(self, ciclo_id: int) -> CicloRead:
        ciclo = self.repo.obter(ciclo_id)
        if ciclo is None:
            raise RecursoNaoEncontrado("Ciclo", ciclo_id)
        return self.para_schema(ciclo)

    @staticmethod
    def para_schema(ciclo: CicloSemaforico, persistido: bool = True) -> CicloRead:
        return CicloRead(
            id=ciclo.id,
            cruzamento_id=ciclo.cruzamento_id,
            data_hora_inicio=ciclo.data_hora_inicio,
            origem=ciclo.origem,
            modo_operacao=ciclo.modo_operacao,
            regra_aplicada=ciclo.regra_aplicada,
            duracao_ciclo_configurada=ciclo.duracao_ciclo_configurada,
            verde_disponivel=ciclo.verde_disponivel,
            duracao_total=ciclo.duracao_total,
            total_veiculos=ciclo.total_veiculos,
            grau_saturacao=ciclo.grau_saturacao,
            persistido=persistido,
            tempos=[
                TempoRead(
                    via_id=t.via_id,
                    nome_via=t.via.nome,
                    semaforo_id=t.semaforo_id,
                    quantidade_veiculos=t.quantidade_veiculos,
                    demanda_percentual=t.demanda_percentual,
                    classificacao_fluxo=t.classificacao_fluxo,
                    tempo_verde=t.tempo_verde,
                    tempo_amarelo=t.tempo_amarelo,
                    tempo_vermelho=t.tempo_vermelho,
                    ajuste_aplicado=t.ajuste_aplicado,
                )
                for t in ciclo.tempos
            ],
        )
