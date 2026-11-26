"""RF16 — parâmetros do algoritmo guardados no banco (registro único)."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import Cruzamento, ParametrosAlgoritmo, RegraTemporizacao
from app.motor import DistribuicaoProporcional, FaixasFluxo, Webster
from app.motor import RegraTemporizacao as Regra
from app.schemas.parametros import ParametrosUpdate

ID_PARAMETROS = 1


class ParametroService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()

    def obter(self) -> ParametrosAlgoritmo:
        parametros = self.db.get(ParametrosAlgoritmo, ID_PARAMETROS)
        if parametros is not None:
            return parametros
        s = self.settings
        parametros = ParametrosAlgoritmo(
            id=ID_PARAMETROS,
            duracao_ciclo=s.duracao_ciclo_padrao,
            limite_fluxo_baixo=s.limite_fluxo_baixo,
            limite_fluxo_moderado=s.limite_fluxo_moderado,
            limite_fluxo_alto=s.limite_fluxo_alto,
            verde_minimo_padrao=s.verde_minimo_padrao,
            verde_maximo_padrao=s.verde_maximo_padrao,
            tempo_maximo_sem_leitura=s.tempo_maximo_sem_leitura,
            fluxo_saturacao_por_faixa=s.fluxo_saturacao_por_faixa,
            intervalo_contagem=s.intervalo_contagem,
            ciclo_minimo=s.ciclo_minimo,
            ciclo_maximo=s.ciclo_maximo,
        )
        self.db.add(parametros)
        try:
            self.db.commit()
        except IntegrityError:  # outra requisição criou o registro ao mesmo tempo
            self.db.rollback()
            return self.db.get(ParametrosAlgoritmo, ID_PARAMETROS)
        self.db.refresh(parametros)
        return parametros

    def atualizar(self, dados: ParametrosUpdate) -> ParametrosAlgoritmo:
        parametros = self.obter()
        for campo, valor in dados.model_dump().items():
            setattr(parametros, campo, valor)
        self.db.commit()
        self.db.refresh(parametros)
        return parametros

    def regra_para(self, cruzamento: Cruzamento) -> Regra:
        if cruzamento.regra_temporizacao == RegraTemporizacao.WEBSTER:
            p = self.obter()
            return Webster(
                fluxo_saturacao_por_faixa=p.fluxo_saturacao_por_faixa,
                intervalo_contagem=p.intervalo_contagem,
                ciclo_minimo=p.ciclo_minimo,
                ciclo_maximo=p.ciclo_maximo,
            )
        return DistribuicaoProporcional()

    def faixas(self) -> FaixasFluxo:
        p = self.obter()
        return FaixasFluxo(
            baixo=p.limite_fluxo_baixo, moderado=p.limite_fluxo_moderado, alto=p.limite_fluxo_alto
        )
